# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
import six

from graphql.language.ast import FieldDefinition, Name, NamedType, ObjectTypeDefinition, Directive, ListType
from graphql import parse
from graphql.language.printer import print_ast
from graphql.type import GraphQLList
from graphql.utils.build_ast_schema import build_ast_schema
from graphql.utils.schema_printer import print_schema

from ..compiler.compiler_frontend import validate_schema_and_ast
from ..ast_manipulation import safe_parse_graphql
from .macro_edge import make_macro_edge_descriptor
from .macro_edge.helpers import get_type_at_macro_edge_target
from .macro_edge.directives import MacroEdgeDirective
from .macro_expansion import expand_macros_in_query_ast
from ..exceptions import GraphQLValidationError


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

        # Optional dict mapping class names to the set of its subclass names.
        # A class in this context means the name of a GraphQLObjectType,
        # GraphQLUnionType or GraphQLInterface.
        'subclass_sets',

        # Dict[str, Dict[str, MacroEdgeDescriptor]] mapping:
        # class name -> (macro edge name -> MacroEdgeDescriptor)
        'macro_edges',

        # Any other macro types we may add in the future go here.
    )
)


def create_macro_registry(schema, type_equivalence_hints=None, subclass_sets=None):
    """Create and return a new empty macro registry."""
    return MacroRegistry(
        schema_without_macros=schema,
        type_equivalence_hints=type_equivalence_hints,
        subclass_sets=subclass_sets,
        macro_edges=dict())


def register_macro_edge(macro_registry, macro_edge_graphql, macro_edge_args):
    """Add the new macro edge descriptor to the provided MacroRegistry object, mutating it.

    Args:
        macro_registry: MacroRegistry object containing macro descriptors, where the new
                        macro edge descriptor should be added.
        macro_edge_graphql: string, GraphQL defining how the new macro edge should be expanded
        macro_edge_args: dict mapping strings to any type, containing any arguments the macro edge
                         requires in order to function.
    """
    class_name, macro_edge_name, macro_descriptor = make_macro_edge_descriptor(
        macro_registry.schema_without_macros, macro_edge_graphql, macro_edge_args,
        type_equivalence_hints=macro_registry.type_equivalence_hints)

    # Ensure this new macro edge does not conflict with any previous descriptor.
    macro_edges_for_class = macro_registry.macro_edges.get(class_name, dict())
    existing_descriptor = macro_edges_for_class.get(macro_edge_name, None)

    if existing_descriptor is not None:
        raise AssertionError(
            u'Attempting to redefine an already registered macro edge: '
            u'class {}, macro edge {}, new GraphQL descriptor {}, new args {}.'
            .format(class_name, macro_edge_name, macro_edge_graphql, macro_edge_args))

    # TODO(predrag): Write a more stringent check that makes sure that two types A and B,
    #                where A is a superclass of B, cannot define the same macro edge.
    #                Right now, both A and B can independently define a macro edge out_Foo,
    #                which would result in an illegal schema as B would be required to have
    #                two different descriptors for the same out_Foo edge.

    macro_registry.macro_edges.setdefault(class_name, dict())[macro_edge_name] = macro_descriptor


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

    for definition in schema_ast.definitions:
        if isinstance(definition, ObjectTypeDefinition):
            if definition.name.value in macro_registry.macro_edges:
                macro_edges = macro_registry.macro_edges[definition.name.value]
                for macro_edge_name, macro_edge_descriptor in six.iteritems(macro_edges):
                    type_at_target = get_type_at_macro_edge_target(
                        macro_registry.schema_without_macros,
                        macro_edge_descriptor.expansion_ast)
                    list_type_at_target = ListType(NamedType(Name(type_at_target.name)))
                    arguments = []
                    directives = [Directive(Name(MacroEdgeDirective.name))]
                    definition.fields.append(FieldDefinition(
                        Name(macro_edge_name), arguments,
                        list_type_at_target, directives=directives))
    return build_ast_schema(schema_ast)


def get_schema_for_macro_definition(schema):
    """Returns a schema with macro directives.

    This returned schema can be used to validate macro definitions, and support GraphQL
    macro editors, enabling them to autocomplete one the @macro_edge_definition and
    @macro_edge_target directives.

    Args:
        schema: GraphQLSchema over which we want to write macros

    Returns:
        GraphQLSchema usable for writing macros
    """
    raise NotImplementedError()  # TODO(bojanserafimov): Implement


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
    validation_errors = validate_schema_and_ast(schema_with_macros, query_ast)
    if validation_errors:
        raise GraphQLValidationError(u'The provided GraphQL input does not validate: {} {}'
                                     .format(graphql_with_macro, validation_errors))

    new_query_ast, new_args = expand_macros_in_query_ast(macro_registry, query_ast, graphql_args)
    new_graphql_string = print_ast(new_query_ast)

    return new_graphql_string, new_args
