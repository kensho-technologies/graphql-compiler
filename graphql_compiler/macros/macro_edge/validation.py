# Copyright 2019-present Kensho Technologies, LLC.
from copy import copy

from graphql.language.ast import (
    ArgumentNode,
    DirectiveNode,
    DocumentNode,
    FieldNode,
    InlineFragmentNode,
    NameNode,
    OperationDefinitionNode,
    SelectionSetNode,
    StringValueNode,
)
from graphql.validation import validate

from ...ast_manipulation import (
    get_ast_field_name,
    get_human_friendly_ast_field_name,
    get_only_selection_from_ast,
)
from ...compiler.compiler_frontend import ast_to_ir
from ...compiler.helpers import get_only_element_from_collection
from ...exceptions import GraphQLInvalidMacroError
from ...query_formatting.common import validate_arguments
from ...schema import VERTEX_FIELD_PREFIXES, FoldDirective, OptionalDirective, is_vertex_field_name
from .ast_rewriting import remove_directives_from_ast
from .ast_traversal import get_directives_for_ast, get_type_at_macro_edge_target
from .descriptor import create_descriptor_from_ast_and_args
from .directives import (
    DIRECTIVES_ALLOWED_IN_MACRO_EDGE_DEFINITION,
    DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION,
    MacroEdgeDefinitionDirective,
    MacroEdgeTargetDirective,
    get_schema_for_macro_edge_definitions,
)
from .reversal import make_reverse_macro_edge_name


def _validate_query_definition(ast):
    """Raise errors if the query operation definition contains directives or variables."""
    if ast.directives:
        directive_names = [directive.name.value for directive in ast.directives]
        raise GraphQLInvalidMacroError(
            "Unexpectedly found directives at the top level of the GraphQL input. "
            "This is not supported. Directives: {}".format(directive_names)
        )

    if ast.variable_definitions:
        raise GraphQLInvalidMacroError(
            "Unexpectedly found variable definitions at the top level of the GraphQL input. "
            "This is not supported. Variable definitions: {}".format(ast.variable_definitions)
        )


def _validate_ast_with_builtin_graphql_validation(schema, ast):
    """Validate the ast against the schema with macro directives using GraphQL validate function."""
    schema_with_macro_edge_directives = get_schema_for_macro_edge_definitions(schema)

    validation_errors = validate(schema_with_macro_edge_directives, ast)
    if validation_errors:
        raise GraphQLInvalidMacroError("Macro edge failed validation: {}".format(validation_errors))


def _validate_that_macro_edge_definition_and_target_directives_appear_once(macro_directives):
    """Validate that macro definition and target directives appear once in the ast."""
    for directive_name in DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION:
        macro_data = macro_directives.get(directive_name, None)
        if not macro_data:
            raise GraphQLInvalidMacroError(
                'Required macro edge directive "@{}" was not found anywhere within the supplied '
                "macro edge definition GraphQL.".format(directive_name)
            )

        if len(macro_data) > 1:
            raise GraphQLInvalidMacroError(
                'Required macro edge directive "@{}" was unexpectedly present more than once in '
                "the supplied macro edge definition GraphQL. It was found {} times.".format(
                    directive_name, len(macro_data)
                )
            )


def _validate_non_required_macro_definition_directives(
    ast, inside_optional_scope=False, inside_fold_scope=False
):
    """Check that the macro is using non-required macro edge definition directives properly.

    Restrictions on use of directives:
    - @macro_edge, @output and @output_source are disallowed
    - @macro_edge_target is not allowed to be inside a @fold scope
    - @macro_edge_target is not allowed to begin with a coercion

    Args:
        ast: GraphQL AST describing a subtree of the macro
        inside_optional_scope: bool, whether the subtree is within an @optional scope
        inside_fold_scope: bool, whether the subtree is within a @fold scope
    """
    names_of_directives_at_ast = frozenset({directive.name.value for directive in ast.directives})

    subselection_inside_optional_scope = inside_optional_scope
    subselection_inside_fold_scope = inside_fold_scope

    for directive in ast.directives:
        name = directive.name.value
        if name not in DIRECTIVES_ALLOWED_IN_MACRO_EDGE_DEFINITION:
            raise GraphQLInvalidMacroError(
                "Unexpected directive name found: {} {}".format(name, directive)
            )

        if name == OptionalDirective.name:
            subselection_inside_optional_scope = True
        elif name == FoldDirective.name:
            subselection_inside_fold_scope = True
        elif name == MacroEdgeTargetDirective.name:
            if inside_optional_scope:
                raise GraphQLInvalidMacroError(
                    "The @macro_edge_target cannot be inside an @optional scope."
                )
            if OptionalDirective.name in names_of_directives_at_ast:
                raise GraphQLInvalidMacroError(
                    "The @macro_edge_target cannot be placed at a field marked @optional."
                )

            if inside_fold_scope:
                raise GraphQLInvalidMacroError(
                    "The @macro_edge_target cannot be inside a @fold scope."
                )
            if FoldDirective.name in names_of_directives_at_ast:
                raise GraphQLInvalidMacroError(
                    "The @macro_edge_target cannot be placed at a field marked @fold."
                )

            # Check that the target doesn't begin with a coercion. This also implicitly
            # checks that the macro is not on a union type, because union types always
            # start with a coercion.
            for selection in ast.selection_set.selections:
                if isinstance(selection, InlineFragmentNode):
                    raise GraphQLInvalidMacroError(
                        "The @macro_edge_target cannot begin directly"
                        "with a coercion. Please put the directive on"
                        "the coercion block itself."
                    )

    if isinstance(ast, (FieldNode, InlineFragmentNode, OperationDefinitionNode)):
        if ast.selection_set is not None:
            for selection in ast.selection_set.selections:
                _validate_non_required_macro_definition_directives(
                    selection,
                    inside_optional_scope=subselection_inside_optional_scope,
                    inside_fold_scope=subselection_inside_fold_scope,
                )
    else:
        raise AssertionError("Unexpected AST type received: {} {}".format(type(ast), ast))


def _validate_that_macro_edge_definition_is_only_top_level_field_directive(ast, macro_defn_ast):
    """Ensure that @macro_edge_definition is the only directive in the top level field."""
    directive_names = [directive.name.value for directive in ast.directives]
    unexpected_directives = [
        directive_name
        for directive_name in directive_names
        if directive_name != MacroEdgeDefinitionDirective.name
    ]
    if unexpected_directives:
        raise GraphQLInvalidMacroError(
            "Found unexpected directives at the top level of the macro definition GraphQL: "
            "{}".format(unexpected_directives)
        )

    if ast is not macro_defn_ast:
        raise GraphQLInvalidMacroError(
            'Expected to find the "@{}" directive at the top level of the macro definition '
            'GraphQL (on the "{}" field), but instead found it on the "{}" field. This is '
            "not allowed.".format(
                MacroEdgeDefinitionDirective.name,
                get_human_friendly_ast_field_name(ast),
                get_human_friendly_ast_field_name(macro_defn_ast),
            )
        )


def _find_subclass_with_field_name(schema, subclass_sets, parent_class_name, field_name):
    """Find a subclass that has a field with a given name, or return None if none exists."""
    subclasses = subclass_sets[parent_class_name]
    if parent_class_name not in subclasses:
        raise AssertionError(
            "Found a class that is not a subclass of itself, this means that the "
            "subclass_sets value is incorrectly constructed: {} {} {}".format(
                parent_class_name, subclasses, subclass_sets
            )
        )

    for subclass_name in subclasses:
        class_object = schema.get_type(subclass_name)
        if field_name in class_object.fields:
            # Found a match!
            return subclass_name

    # No match.
    return None


def _validate_macro_edge_name_for_class_name(schema, subclass_sets, class_name, macro_edge_name):
    """Ensure that the provided macro edge name is valid for the given class name."""
    # The macro edge must be a valid edge name.
    if not is_vertex_field_name(macro_edge_name):
        raise GraphQLInvalidMacroError(
            'The provided macro edge name "{}" is not valid, since it does not start with '
            "the expected prefixes for vertex fields: {}".format(
                macro_edge_name, list(VERTEX_FIELD_PREFIXES)
            )
        )

    # The macro edge must not have the same name as an existing edge on the class where it exists,
    # or any of its subclasses.
    conflicting_subclass_name = _find_subclass_with_field_name(
        schema, subclass_sets, class_name, macro_edge_name
    )
    if conflicting_subclass_name is not None:
        extra_error_text = ""
        if conflicting_subclass_name != class_name:
            extra_error_text = (
                "{} is a subclass of {}, which is where you attempted to "
                "define a macro edge".format(conflicting_subclass_name, class_name)
            )
        raise GraphQLInvalidMacroError(
            'The provided macro edge name "{edge_name}" has the same name as '
            'an existing field on the "{subclass_name}" GraphQL type or interface. '
            "{extra_error_text}"
            "This is not allowed, please choose a different name.".format(
                edge_name=macro_edge_name,
                subclass_name=conflicting_subclass_name,
                extra_error_text=extra_error_text,
            )
        )


def _validate_reversed_macro_edge(schema, subclass_sets, reverse_start_class_name, macro_edge_name):
    """Ensure that the provided macro does not conflict when its direction is reversed."""
    reversed_macro_edge_name = make_reverse_macro_edge_name(macro_edge_name)

    # The reversed macro edge must not have the same name as an existing edge on the target class
    # it points to, or any of its subclasses. If such an edge exists, then the macro edge is not
    # reversible since the reversed macro edge would conflict with the existing edge on that class.
    conflicting_subclass_name = _find_subclass_with_field_name(
        schema, subclass_sets, reverse_start_class_name, reversed_macro_edge_name
    )
    if conflicting_subclass_name is not None:
        extra_error_text = ""
        if conflicting_subclass_name != reverse_start_class_name:
            extra_error_text = (
                "{} is a subclass of {}, which is where your "
                "macro edge definition points to. ".format(
                    conflicting_subclass_name, reverse_start_class_name
                )
            )
        raise GraphQLInvalidMacroError(
            'The provided macro edge name "{edge_name}" is invalid: if the edge direction were '
            'reversed, it would conflict with an existing field on the "{subclass_name}" GraphQL '
            "type or interface. {extra_error_text}"
            "This is not allowed, please choose a different name.".format(
                edge_name=macro_edge_name,
                subclass_name=conflicting_subclass_name,
                extra_error_text=extra_error_text,
            )
        )


def _get_minimal_query_ast_from_macro_ast(macro_ast):
    """Get a query that should successfully compile to IR if the macro is valid."""
    ast_without_macro_directives = remove_directives_from_ast(
        macro_ast, DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION
    )

    # We will add this output directive to make the ast a valid query
    output_directive = DirectiveNode(
        name=NameNode(value="output"),
        arguments=[
            ArgumentNode(
                name=NameNode(value="out_name"), value=StringValueNode(value="dummy_output_name")
            )
        ],
    )

    # Shallow copy everything on the path to the first level selection list
    query_ast = copy(ast_without_macro_directives)
    root_level_selection = copy(get_only_selection_from_ast(query_ast, GraphQLInvalidMacroError))
    first_level_selections = list(root_level_selection.selection_set.selections)

    # Add an output to a new or existing __typename field
    existing_typename_field = None
    for idx, selection in enumerate(first_level_selections):
        if isinstance(selection, FieldNode):
            if selection.name.value == "__typename":
                # We have a copy of the list, but the elements are references to objects
                # in macro_ast that we don't want to mutate. So the following copy is necessary.
                existing_typename_field = copy(selection)
                existing_typename_field.directives = copy(existing_typename_field.directives)
                existing_typename_field.directives.append(output_directive)
                first_level_selections[idx] = existing_typename_field
    if existing_typename_field is None:
        first_level_selections.insert(
            0, FieldNode(name=NameNode(value="__typename"), directives=[output_directive])
        )

    # Propagate the changes back to the result_ast
    root_level_selection.selection_set = SelectionSetNode(selections=first_level_selections)
    query_ast.selection_set = SelectionSetNode(selections=[root_level_selection])
    return DocumentNode(definitions=[query_ast])


# ############
# Public API #
# ############


def get_and_validate_macro_edge_info(
    schema, subclass_sets, ast, macro_edge_args, type_equivalence_hints=None
):
    """Return a MacroEdgeDescriptor for the specified macro edge, after ensuring its validity.

    Args:
        schema: GraphQL schema object, created using the GraphQL library
        subclass_sets: Dict[str, Set[str]] mapping class names to the set of its subclass names.
                       A class in this context means the name of a GraphQLObjectType,
                       GraphQLUnionType or GraphQLInterface.
        ast: GraphQL library AST OperationDefinition object, describing the GraphQL that is defining
             the macro edge.
        macro_edge_args: dict mapping strings to any type, containing any arguments the macro edge
                         requires in order to function.
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces), as well as a
                                workaround for Gremlin's total lack of inheritance-awareness.
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union.
                                Recursive expansion of type equivalence hints is not performed,
                                and only type-level correctness of this argument is enforced.
                                See README.md for more details on everything this parameter does.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****

    Returns:
        MacroEdgeDescriptor containing the base type name where the macro edge is defined, the name
        of the macro edge, and the macro AST and arguments.
    """
    macro_directives = get_directives_for_ast(ast)

    _validate_query_definition(ast)
    _validate_ast_with_builtin_graphql_validation(schema, DocumentNode(definitions=[ast]))
    _validate_that_macro_edge_definition_and_target_directives_appear_once(macro_directives)
    _validate_non_required_macro_definition_directives(ast)

    # Guaranteed to only have one macro definition directive,
    # otherwise validation should have failed in the previous steps.
    macro_defn_ast, macro_defn_directive = get_only_element_from_collection(
        macro_directives[MacroEdgeDefinitionDirective.name]
    )

    # Ensure that the macro successfully compiles to IR.
    input_metadata = ast_to_ir(
        schema,
        _get_minimal_query_ast_from_macro_ast(ast),
        type_equivalence_hints=type_equivalence_hints,
    ).input_metadata
    validate_arguments(input_metadata, macro_edge_args)

    _validate_that_macro_edge_definition_is_only_top_level_field_directive(
        get_only_selection_from_ast(ast, GraphQLInvalidMacroError), macro_defn_ast
    )
    class_name = get_ast_field_name(macro_defn_ast)
    macro_edge_name = get_only_element_from_collection(macro_defn_directive.arguments).value.value

    _validate_macro_edge_name_for_class_name(schema, subclass_sets, class_name, macro_edge_name)

    target_class_name = get_type_at_macro_edge_target(schema, macro_defn_ast).name
    _validate_reversed_macro_edge(schema, subclass_sets, target_class_name, macro_edge_name)

    descriptor = create_descriptor_from_ast_and_args(
        class_name, target_class_name, macro_edge_name, macro_defn_ast, macro_edge_args
    )

    return descriptor
