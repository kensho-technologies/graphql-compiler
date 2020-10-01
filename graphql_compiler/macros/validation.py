# Copyright 2019-present Kensho Technologies, LLC.
from graphql.language.printer import print_ast

from ..exceptions import GraphQLInvalidMacroError
from .macro_edge.reversal import make_reverse_macro_edge_name


def _find_any_macro_edge_name_at_subclass(macro_registry, class_name, macro_edge_name):
    """Return any descriptor for a given macro edge name defined on a subclass, if it exists."""
    subclasses = macro_registry.subclass_sets[class_name]
    if class_name not in subclasses:
        raise AssertionError(
            "Found a class that is not a subclass of itself, this means that the "
            "subclass_sets value is incorrectly constructed: {} {} {}".format(
                class_name, subclasses, macro_registry.subclass_sets
            )
        )

    for subclass_name in subclasses:
        existing_descriptor = macro_registry.macro_edges_at_class.get(subclass_name, dict()).get(
            macro_edge_name, None
        )

        if existing_descriptor is not None:
            return existing_descriptor

    return None


def _find_any_macro_edge_name_to_subclass(macro_registry, class_name, macro_edge_name):
    """Return any descriptor for a given macro edge name that points to a subclass, if it exists."""
    subclasses = macro_registry.subclass_sets[class_name]
    if class_name not in subclasses:
        raise AssertionError(
            "Found a class that is not a subclass of itself, this means that the "
            "subclass_sets value is incorrectly constructed: {} {} {}".format(
                class_name, subclasses, macro_registry.subclass_sets
            )
        )

    for subclass_name in subclasses:
        existing_descriptor = macro_registry.macro_edges_to_class.get(subclass_name, dict()).get(
            macro_edge_name, None
        )

        if existing_descriptor is not None:
            return existing_descriptor

    return None


def _get_type_relationship_error_description_text(subclass_sets, current_type, other_type):
    """Get a suitable description of the relationship of the two types for use in error messages."""
    if current_type == other_type:
        return ""

    if current_type in subclass_sets[other_type]:
        relationship = "supertype"
    elif other_type in subclass_sets[current_type]:
        relationship = "subtype"
    else:
        raise AssertionError(
            "Conflict between two types that "
            "are not each other's supertype: {} {} {}".format(
                current_type, other_type, subclass_sets
            )
        )

    return (" (a {relationship} of {current_type})").format(
        relationship=relationship,
        current_type=current_type,
    )


def _raise_macro_reversal_conflict_error(
    new_macro_descriptor, existing_descriptor, specific_resolution_advice
):
    """Raise a macro validation error related to the inability to reverse the given macro edge."""
    if not specific_resolution_advice:
        raise AssertionError(
            "No specific error resolution advice given, this should never happen: {} {} {}".format(
                new_macro_descriptor, existing_descriptor, specific_resolution_advice
            )
        )

    raise GraphQLInvalidMacroError(
        "The given macro edge with name {edge_name} defined on type {base_class_name} and "
        "pointing to type {target_class_name} is invalid due to a reversibility conflict. "
        "Macro edges are required to be reversible, but the corresponding reversed macro "
        "edge {reverse_edge_name} from {target_class_name} to {base_class_name} would be "
        "impossible to define because of a conflict with an existing macro edge: "
        "{reverse_edge_name} from {conflicting_base} to {conflicting_target}. To resolve "
        "the issue, either choose a new name for your macro edge, or "
        "{specific_advice}."
        "Conflicting macro edge definition: {macro_graphql} with args {macro_args}".format(
            edge_name=new_macro_descriptor.macro_edge_name,
            base_class_name=new_macro_descriptor.base_class_name,
            target_class_name=new_macro_descriptor.target_class_name,
            reverse_edge_name=existing_descriptor.macro_edge_name,
            conflicting_base=existing_descriptor.base_class_name,
            conflicting_target=existing_descriptor.target_class_name,
            specific_advice=specific_resolution_advice,
            macro_graphql=print_ast(existing_descriptor.expansion_ast),
            macro_args=existing_descriptor.macro_args,
        )
    )


def _get_macro_edge_reversal_conflicts_with_existing_descriptor(
    reverse_base_class_name, reverse_target_class_name, existing_descriptor
):
    """Return a (possibly empty) list of reversal conflicts relative to an existing macro edge."""
    errors = []
    if reverse_base_class_name != existing_descriptor.base_class_name:
        errors.append(
            "change your macro edge's target class to {}".format(
                existing_descriptor.base_class_name
            )
        )

    if reverse_target_class_name != existing_descriptor.target_class_name:
        errors.append(
            "define your macro edge on class {} instead".format(
                existing_descriptor.target_class_name
            )
        )

    return errors


# ############
# Public API #
# ############


def check_macro_edge_for_definition_conflicts(macro_registry, macro_edge_descriptor):
    """Ensure that the macro edge on the specified class does not cause any definition conflicts."""
    # There are two kinds of conflicts that we check for:
    # - defining this macro edge would not conflict with any macro edges that already exist
    #   at the same type or at a superclass of the base class of the macro; and
    # - defining this macro edge would not cause any subclass of the base class of the macro
    #   to have a conflicting definition for any of its fields originating from prior
    #   macro edge definitions.
    # We check for both of them simultaneously, by ensuring that none of the subclasses of the
    # base class name have a macro edge by the specified name.
    macro_edge_name = macro_edge_descriptor.macro_edge_name
    base_class_name = macro_edge_descriptor.base_class_name
    target_class_name = macro_edge_descriptor.target_class_name

    existing_descriptor = _find_any_macro_edge_name_at_subclass(
        macro_registry, base_class_name, macro_edge_name
    )
    if existing_descriptor is not None:
        conflict_on_class_name = existing_descriptor.base_class_name
        extra_error_text = _get_type_relationship_error_description_text(
            macro_registry.subclass_sets, base_class_name, conflict_on_class_name
        )
        raise GraphQLInvalidMacroError(
            "A macro edge with name {edge_name} cannot be defined on type {current_type} due "
            "to a conflict with another macro edge with the same name defined "
            "on type {original_type}{extra_error_text}."
            "Cannot define this conflicting macro, please verify "
            "if the existing macro edge does what you want, or rename your macro "
            "edge to avoid the conflict. Existing macro definition and args: "
            "{macro_graphql} {macro_args}".format(
                edge_name=macro_edge_name,
                current_type=base_class_name,
                original_type=conflict_on_class_name,
                extra_error_text=extra_error_text,
                macro_graphql=print_ast(existing_descriptor.expansion_ast),
                macro_args=existing_descriptor.macro_args,
            )
        )

    existing_descriptor = _find_any_macro_edge_name_to_subclass(
        macro_registry, target_class_name, macro_edge_name
    )
    if existing_descriptor is not None:
        conflict_on_class_name = existing_descriptor.target_class_name
        extra_error_text = _get_type_relationship_error_description_text(
            macro_registry.subclass_sets, target_class_name, conflict_on_class_name
        )
        raise GraphQLInvalidMacroError(
            "A macro edge with name {edge_name} cannot be defined to point to {target_type} due "
            "to a conflict with another macro edge with the same name that points to "
            "type {original_type}{extra_error_text}."
            "Cannot define this conflicting macro, please verify "
            "if the existing macro edge does what you want, or rename your macro "
            "edge to avoid the conflict. Existing macro definition and args: "
            "{macro_graphql} {macro_args}".format(
                edge_name=macro_edge_name,
                target_type=target_class_name,
                original_type=conflict_on_class_name,
                extra_error_text=extra_error_text,
                macro_graphql=print_ast(existing_descriptor.expansion_ast),
                macro_args=existing_descriptor.macro_args,
            )
        )


def check_macro_edge_for_reversal_definition_conflicts(macro_registry, macro_descriptor):
    """Ensure that the macro edge, when reversed, does not conflict with any existing macro edges.

    This function ensures that for any macro edge being defined, if a corresponding macro edge were
    to be later defined in the opposite direction (whether manually or automatically), this new
    reversed macro edge would not conflict with any existing macro edges. To check this, we generate
    the name of the reversed macro edge, and then check the types the macro edge connects. If a
    macro edge by the same name exists on either of those types, or any of their subtypes, then
    the reversed macro edge is deemed in conflict, and the original macro edge definition is
    considered invalid.

    Args:
        macro_registry: MacroRegistry object containing macro descriptors, where the new
                        macro edge descriptor would be added.
        macro_descriptor: MacroEdgeDescriptor describing the macro edge being added
    """
    reverse_macro_edge_name = make_reverse_macro_edge_name(macro_descriptor.macro_edge_name)
    reverse_base_class_name = macro_descriptor.target_class_name
    reverse_target_class_name = macro_descriptor.base_class_name

    existing_descriptor = _find_any_macro_edge_name_at_subclass(
        macro_registry, reverse_base_class_name, reverse_macro_edge_name
    )
    if existing_descriptor is not None:
        # There is already a reverse macro edge of the same name that starts at the same type.
        # Let's make sure its endpoint types are an exact match compared to the endpoint types
        # of the macro edge being defined.
        errors = _get_macro_edge_reversal_conflicts_with_existing_descriptor(
            reverse_base_class_name, reverse_target_class_name, existing_descriptor
        )
        if errors:
            _raise_macro_reversal_conflict_error(
                macro_descriptor, existing_descriptor, " and ".join(errors)
            )

    existing_descriptor = _find_any_macro_edge_name_to_subclass(
        macro_registry, reverse_target_class_name, reverse_macro_edge_name
    )
    if existing_descriptor is not None:
        # There is already a macro edge of the same name that points to the same type.
        # Let's make sure its endpoint types are an exact match compared to the endpoint types
        # of the macro edge being defined.
        errors = _get_macro_edge_reversal_conflicts_with_existing_descriptor(
            reverse_base_class_name, reverse_target_class_name, existing_descriptor
        )
        if errors:
            _raise_macro_reversal_conflict_error(
                macro_descriptor, existing_descriptor, " and ".join(errors)
            )
