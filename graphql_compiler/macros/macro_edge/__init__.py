# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple


MacroEdgeDefinition = namedtuple(
    'MacroEdgeDefinition', (
        'expansion_ast',  # GraphQL AST object defining how the macro edge should be expanded
        'macro_args',     # Dict[str, Any] containing any arguments that the macro requires
    )
)


def make_macro_edge_definition(schema, macro_edge_graphql, macro_edge_args,
                               type_equivalence_hints=None):
    """Validate the GraphQL macro edge definition, and return it in a form suitable for storage.

    Args:
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

    Returns:
        tuple (class name, macro edge name, MacroEdgeDefinition) suitable for inclusion into the
        GraphQL macro registry
    """
    raise NotImplementedError()
