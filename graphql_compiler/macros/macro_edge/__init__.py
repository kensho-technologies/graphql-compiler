# Copyright 2019-present Kensho Technologies, LLC.
from ...ast_manipulation import get_only_query_definition, safe_parse_graphql
from ...exceptions import GraphQLInvalidMacroError
from .validation import get_and_validate_macro_edge_info


def make_macro_edge_descriptor(
    schema, subclass_sets, macro_edge_graphql, macro_edge_args, type_equivalence_hints=None
):
    """Validate the GraphQL macro edge definition, and return a MacroEdgeDescriptor describing it.

    Args:
        schema: GraphQL schema object, created using the GraphQL library
        subclass_sets: Dict[str, Set[str]] mapping class names to the set of its subclass names.
                       A class in this context means the name of a GraphQLObjectType,
                       GraphQLUnionType or GraphQLInterface.
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

    Returns:
        MacroEdgeDescriptor suitable for inclusion into the GraphQL macro registry
    """
    root_ast = safe_parse_graphql(macro_edge_graphql)

    definition_ast = get_only_query_definition(root_ast, GraphQLInvalidMacroError)

    macro_edge_descriptor = get_and_validate_macro_edge_info(
        schema,
        subclass_sets,
        definition_ast,
        macro_edge_args,
        type_equivalence_hints=type_equivalence_hints,
    )

    return macro_edge_descriptor
