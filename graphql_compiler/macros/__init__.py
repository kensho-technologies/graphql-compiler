# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql.language.printer import print_ast

from ..ast_manipulation import safe_parse_graphql
from .macro_edge import make_macro_edge_descriptor
from .macro_expansion import expand_macros_in_query_ast


MacroRegistry = namedtuple(
    'MacroRegistry', (
        'macro_edges',  # Dict[str, Dict[str, MacroEdgeDescriptor]] mapping:
                        # class name -> (macro edge name -> MacroEdgeDescriptor)
        # Any other macro types we may add in the future go here.
    )
)


def create_macro_registry():
    """Create and return a new empty macro registry."""
    return MacroRegistry(macro_edges=dict())


def register_macro_edge(macro_registry, schema, macro_edge_graphql, macro_edge_args,
                        type_equivalence_hints=None):
    """Add the new macro edge descriptor to the provided MacroRegistry object, mutating it.

    Args:
        macro_registry: MacroRegistry object containing macro descriptors, where the new
                        macro edge descriptor should be added.
        schema: GraphQL schema object, created using the GraphQL library
        macro_edge_graphql: string, GraphQL defining how the new macro edge should be expanded
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
    """
    class_name, macro_edge_name, macro_descriptor = make_macro_edge_descriptor(
        schema, macro_edge_graphql, macro_edge_args,
        type_equivalence_hints=type_equivalence_hints)

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


def perform_macro_expansion(schema, macro_registry, graphql_with_macro,
                            graphql_args, subclass_sets=None):
    """Return a new GraphQL query string and args, after expanding any encountered macros.

    Args:
        schema: GraphQL schema object, created using the GraphQL library
        macro_registry: MacroRegistry, the registry of macro descriptors used for expansion
        graphql_with_macro: string, GraphQL query that potentially requires macro expansion
        graphql_args: dict mapping strings to any type, containing the arguments for the query
        subclass_sets: optional dict mapping class names to the set of its subclass names

    Returns:
        tuple (new_graphql_string, new_graphql_args) containing the rewritten GraphQL query and
        its new args, after macro expansion. If the input GraphQL query contained no macros,
        the returned values are guaranteed to be identical to the input query and args.
    """
    query_ast = safe_parse_graphql(graphql_with_macro)

    new_query_ast, new_args = expand_macros_in_query_ast(
        schema, macro_registry, query_ast, graphql_args, subclass_sets=subclass_sets)
    new_graphql_string = print_ast(new_query_ast)

    return new_graphql_string, new_args
