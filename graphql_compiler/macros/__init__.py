# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import copy

from graphql import parse
from graphql.language.ast import (
    Directive, FieldDefinition, InterfaceTypeDefinition, ListType, Name, NamedType,
    ObjectTypeDefinition
)
from graphql.language.printer import print_ast
from graphql.utils.build_ast_schema import build_ast_schema
from graphql.utils.schema_printer import print_schema
import six

from ..ast_manipulation import safe_parse_graphql
from ..compiler.subclass import compute_subclass_sets
from ..compiler.validation import validate_schema_and_query_ast
from ..exceptions import GraphQLInvalidMacroError, GraphQLValidationError
from ..schema import check_for_nondefault_directive_names
from .macro_edge import make_macro_edge_descriptor
from .macro_edge.directives import (
    DIRECTIVES_ALLOWED_IN_MACRO_EDGE_DEFINITION, DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION,
    MacroEdgeDirective
)
from .macro_edge.reversal import make_reverse_macro_edge_name
from .macro_expansion import expand_macros_in_query_ast


MacroRegistry = namedtuple(
    'MacroRegistry', (
        # GraphQLSchema, created using the GraphQL library
        'schema_without_macros',

        # Optional dict of GraphQL interface or type -> GraphQL union.
        # Used as a workaround for GraphQL's lack of support for
        # inheritance across "types" (i.e. non-interfaces), as well as a
        # workaround for Gremlin's total lack of inheritance-awareness.
        # The key-value pairs in the dict specify that the "key" type
        # is equivalent to the "value" type, i.e. that the GraphQL type or
        # interface in the key is the most-derived common supertype
        # of every GraphQL type in the "value" GraphQL union.
        # Recursive expansion of type equivalence hints is not performed,
        # and only type-level correctness of this argument is enforced.
        # See README.md for more details on everything this parameter does.
        # *****
        # Be very careful with this option, as bad input here will
        # lead to incorrect output queries being generated.
        # *****
        'type_equivalence_hints',

        # Dict[str, Set[str]] mapping class names to the set of its subclass names.
        # A class in this context means the name of a GraphQLObjectType,
        # GraphQLUnionType or GraphQLInterface.
        'subclass_sets',

        # #################
        # Macro edge info #
        # #################
        # List[MacroEdgeDescriptor] containing all defined macro edges
        'macro_edges',

        # Dict[str, Dict[str, MacroEdgeDescriptor]] mapping:
        # class name -> (macro edge name -> MacroEdgeDescriptor)
        # If a given macro edge is defined on a class X which has subclasses A and B,
        # then this dict will contain entries for that macro edge for all of [X, A, B].
        'macro_edges_at_class',

        # Dict[str, Dict[str, MacroEdgeDescriptor]] mapping:
        # class name -> (macro edge name -> MacroEdgeDescriptor)
        # If a given macro edge has class X as a target, which has subclasses A and B,
        # then this dict will contain entries for that macro edge for all of [X, A, B].
        'macro_edges_to_class',

        # ############################################################
        # Any other macro types we may add in the future under this. #
        # ############################################################
    )
)


def create_macro_registry(schema, type_equivalence_hints=None, subclass_sets=None):
    """Create and return a new empty macro registry."""
    if subclass_sets is None:
        subclass_sets = compute_subclass_sets(schema, type_equivalence_hints=type_equivalence_hints)

    return MacroRegistry(
        schema_without_macros=schema,
        type_equivalence_hints=type_equivalence_hints,
        subclass_sets=subclass_sets,
        macro_edges=list(),
        macro_edges_at_class=dict(),
        macro_edges_to_class=dict())


def _find_macro_edge_name_at_subclass(macro_registry, class_name, macro_edge_name):
    """Return the descriptor for a given macro edge defined on a subclass, if it exists."""
    subclasses = macro_registry.subclass_sets[class_name]
    if class_name not in subclasses:
        raise AssertionError(u'Found a class that is not a subclass of itself, this means that the '
                             u'subclass_sets value is incorrectly constructed: {} {} {}'
                             .format(class_name, subclasses, macro_registry.subclass_sets))

    for subclass_name in subclasses:
        existing_descriptor = macro_registry.macro_edges_at_class.get(
            subclass_name, dict()).get(macro_edge_name, None)

        if existing_descriptor is not None:
            return existing_descriptor

    return None


def _find_macro_edge_name_to_subclass(macro_registry, class_name, macro_edge_name):
    """Return the descriptor for a given macro edge that points to a subclass, if it exists."""
    subclasses = macro_registry.subclass_sets[class_name]
    if class_name not in subclasses:
        raise AssertionError(u'Found a class that is not a subclass of itself, this means that the '
                             u'subclass_sets value is incorrectly constructed: {} {} {}'
                             .format(class_name, subclasses, macro_registry.subclass_sets))

    for subclass_name in subclasses:
        existing_descriptor = macro_registry.macro_edges_to_class.get(
            subclass_name, dict()).get(macro_edge_name, None)

        if existing_descriptor is not None:
            return existing_descriptor

    return None


def _check_macro_edge_for_definition_conflicts(macro_registry, macro_edge_descriptor):
    """Ensure that the macro edge on the specified class does not cause any definition conflicts."""
    # There are two kinds of conflicts that we check for:
    # - defining this macro edge would not conflict with any macro edges that already exist
    #   at the same type or at a superclass of the base class of the macro; and
    # - defining this macro edge would not cause any subclass of the base class of the macro
    #   to have a conflicting definition for any of its fields originating from prior
    #   macro edge definitions.
    # We check for both of them simultaneously, by ensuring that none of the subclasses of the
    # base class name have a macro edge by the specified name.
    base_class_name = macro_edge_descriptor.base_class_name
    macro_edge_name = macro_edge_descriptor.macro_edge_name

    existing_descriptor = _find_macro_edge_name_at_subclass(
        macro_registry, base_class_name, macro_edge_name)

    if existing_descriptor is not None:
        extra_error_text = u''
        conflict_on_class_name = existing_descriptor.base_class_name
        if conflict_on_class_name != base_class_name:
            # The existing descriptor is defined elsewhere. Let's figure out if it's a subclass
            # or a superclass conflict.
            if base_class_name in macro_registry.subclass_sets[conflict_on_class_name]:
                relationship = 'supertype'
            elif conflict_on_class_name in macro_registry.subclass_sets[base_class_name]:
                relationship = 'subtype'
            else:
                raise AssertionError(u'Conflict between two macro edges defined on types that '
                                     u'are not each other\'s supertype: {} {} {}'
                                     .format(base_class_name, macro_edge_name, macro_registry))

            extra_error_text = (
                u' (a {relationship} of {current_type})'
            ).format(
                relationship=relationship,
                current_type=base_class_name,
            )

        raise GraphQLInvalidMacroError(
            u'A macro edge with name {edge_name} cannot be defined on type {current_type} due '
            u'to a conflict with another macro edge with the same name defined '
            u'on type {original_type}{extra_error_text}.'
            u'Cannot define this conflicting macro, please verify '
            u'if the existing macro edge does what you want, or rename your macro '
            u'edge to avoid the conflict. Existing macro definition and args: '
            u'{macro_graphql} {macro_args}'
            .format(edge_name=macro_edge_name,
                    current_type=base_class_name,
                    original_type=conflict_on_class_name,
                    extra_error_text=extra_error_text,
                    macro_graphql=print_ast(existing_descriptor.expansion_ast),
                    macro_args=existing_descriptor.macro_args))


def _check_macro_edge_for_reversal_definition_conflicts(macro_registry, macro_descriptor):
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

    existing_descriptor = _find_macro_edge_name_at_subclass(
        macro_registry, reverse_base_class_name, reverse_macro_edge_name)

    if existing_descriptor is not None:
        # There is already a reverse macro edge of the same name that starts at the same type.
        # Let's make sure its endpoint types are an exact match compared to the endpoint types
        # of the macro edge being defined.
        if reverse_base_class_name != existing_descriptor.base_class_name:
            raise GraphQLInvalidMacroError()

        if reverse_target_class_name != existing_descriptor.target_class_name:
            raise GraphQLInvalidMacroError()

    existing_descriptor = _find_macro_edge_name_to_subclass(
        macro_registry, reverse_target_class_name, reverse_macro_edge_name)
    if existing_descriptor is not None:
        # There is already a macro edge of the same name that points to the same type.
        # Let's make sure its endpoint types are an exact match compared to the endpoint types
        # of the macro edge being defined.
        if reverse_base_class_name != existing_descriptor.base_class_name:
            raise GraphQLInvalidMacroError()

        if reverse_target_class_name != existing_descriptor.target_class_name:
            raise GraphQLInvalidMacroError()


def register_macro_edge(macro_registry, macro_edge_graphql, macro_edge_args):
    """Add the new macro edge descriptor to the provided MacroRegistry object, mutating it.

    Args:
        macro_registry: MacroRegistry object containing macro descriptors, where the new
                        macro edge descriptor should be added.
        macro_edge_graphql: string, GraphQL defining how the new macro edge should be expanded
        macro_edge_args: dict mapping strings to any type, containing any arguments the macro edge
                         requires in order to function.
    """
    # The below function will validate that the macro edge in question is valid in isolation,
    # when considered only against the macro-less schema. After geting this result,
    # we simply need to check the macro edge descriptor against other artifacts in the macro system
    # that might also cause conflicts.
    macro_descriptor = make_macro_edge_descriptor(
        macro_registry.schema_without_macros, macro_registry.subclass_sets,
        macro_edge_graphql, macro_edge_args,
        type_equivalence_hints=macro_registry.type_equivalence_hints)

    # Ensure there's no conflict with macro edges defined on subclasses and superclasses.
    _check_macro_edge_for_definition_conflicts(macro_registry, macro_descriptor)

    # Ensure there's no conflict between existing macro edges and the (hypothetical) reversed
    # macro edge of the one being defined.
    _check_macro_edge_for_reversal_definition_conflicts(macro_registry, macro_descriptor)

    for subclass_name in macro_registry.subclass_sets[macro_descriptor.base_class_name]:
        macro_registry.macro_edges_at_class.setdefault(
            subclass_name, dict())[macro_descriptor.macro_edge_name] = macro_descriptor

    for subclass_name in macro_registry.subclass_sets[macro_descriptor.target_class_name]:
        macro_registry.macro_edges_to_class.setdefault(
            subclass_name, dict())[macro_descriptor.macro_edge_name] = macro_descriptor

    macro_registry.macro_edges.append(macro_descriptor)


def get_schema_with_macros(macro_registry):
    """Get a new GraphQLSchema with fields where macro edges can be used.

    Preconditions:
    1. No macro in the registry has the same name as a field on the vertex where it applies.
    2. Members of a union type do not have outgoing macros with the same name.

    An easy way to satisfy the preconditions is to create the macro_registry using
    create_macro_registry, and only update it with register_macro_edge, which does all
    the necessary validation.

    Postconditions:
    1. Every GraphQLQuery that uses macros from this registry appropriately should
       successfully type-check against the schema generated from this function.
    2. A GraphQLQuery that uses macros not present in the registry, or uses valid
       macros but on types they are not defined at should fail schema validation with
       the schema generated from this function.
    3. This function is total -- A valid macro registry should not fail to create a
       GraphQL schema with macros.

    Args:
        macro_registry: MacroRegistry object containing a schema and macro descriptors
                        we want to add to the schema.

    Returns:
        GraphQLSchema with additional fields where macroe edges can be used.
    """
    # The easiest way to manipulate the schema is through its AST. The easiest
    # way to get an AST is to print it and parse it.
    schema_ast = parse(print_schema(macro_registry.schema_without_macros))

    definitions_by_name = {}
    for definition in schema_ast.definitions:
        if isinstance(definition, (ObjectTypeDefinition, InterfaceTypeDefinition)):
            definitions_by_name[definition.name.value] = definition

    for class_name, macros_for_class in six.iteritems(macro_registry.macro_edges_at_class):
        for macro_edge_name, macro_edge_descriptor in six.iteritems(macros_for_class):
            list_type_at_target = ListType(NamedType(Name(macro_edge_descriptor.target_class_name)))
            arguments = []
            directives = [Directive(Name(MacroEdgeDirective.name))]
            definitions_by_name[class_name].fields.append(FieldDefinition(
                Name(macro_edge_name), arguments, list_type_at_target, directives=directives))

    return build_ast_schema(schema_ast)


def get_schema_for_macro_definition(schema):
    """Returns a schema with macro directives.

    Preconditions:
    1. All compiler-supported and graphql-default directives have their default behavior.

    This returned schema can be used to validate macro definitions, and support GraphQL
    macro editors, enabling them to autocomplete on the @macro_edge_definition and
    @macro_edge_target directives. Some directives that are disallowed in macro edge definitions,
    like @output and @output_source, will be removed from the directives list.

    Args:
        schema: GraphQLSchema over which we want to write macros

    Returns:
        GraphQLSchema usable for writing macros. Modifying this schema is undefined behavior.

    Raises:
        AssertionError, if the schema contains directive names that are non-default.
    """
    macro_definition_schema = copy(schema)
    macro_definition_schema_directives = schema.get_directives()
    check_for_nondefault_directive_names(macro_definition_schema_directives)
    macro_definition_schema_directives += DIRECTIVES_REQUIRED_IN_MACRO_EDGE_DEFINITION
    # Remove disallowed directives from directives list
    macro_definition_schema_directives = list(set(macro_definition_schema_directives) &
                                              set(DIRECTIVES_ALLOWED_IN_MACRO_EDGE_DEFINITION))

    # pylint: disable=protected-access
    macro_definition_schema._directives = macro_definition_schema_directives
    # pylint: enable=protected-access
    return macro_definition_schema


def perform_macro_expansion(macro_registry, graphql_with_macro, graphql_args):
    """Return a new GraphQL query string and args, after expanding any encountered macros.

    Args:
        macro_registry: MacroRegistry, the registry of macro descriptors used for expansion
        graphql_with_macro: string, GraphQL query that potentially requires macro expansion
        graphql_args: dict mapping strings to any type, containing the arguments for the query

    Returns:
        tuple (new_graphql_string, new_graphql_args) containing the rewritten GraphQL query and
        its new args, after macro expansion. If the input GraphQL query contained no macros,
        the returned values are guaranteed to be identical to the input query and args.
    """
    query_ast = safe_parse_graphql(graphql_with_macro)
    schema_with_macros = get_schema_with_macros(macro_registry)
    validation_errors = validate_schema_and_query_ast(schema_with_macros, query_ast)
    if validation_errors:
        raise GraphQLValidationError(u'The provided GraphQL input does not validate: {} {}'
                                     .format(graphql_with_macro, validation_errors))

    new_query_ast, new_args = expand_macros_in_query_ast(macro_registry, query_ast, graphql_args)
    new_graphql_string = print_ast(new_query_ast)

    return new_graphql_string, new_args
