# Copyright 2019-present Kensho Technologies, LLC.
from typing import Dict, Optional, Set

from graphql import GraphQLInterfaceType, GraphQLObjectType, GraphQLSchema, GraphQLUnionType
import six

from ..schema.typedefs import TypeEquivalenceHintsType


def compute_subclass_sets(
    schema: GraphQLSchema, type_equivalence_hints: Optional[TypeEquivalenceHintsType] = None
) -> Dict[str, Set[str]]:
    """Return a dict mapping class names to the set of its subclass names.

    A class here means an object type or interface.

    B is a subclass of A if any of the following conditions hold:
     - B is the same class as A
     - A is an interface and B implements it
     - A is equivalent to a union type (see type_equivalence_hints) and B is a member of it
     - B is a subclass of C and C is a subclass of A

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        type_equivalence_hints: optional dict of GraphQL type to equivalent GraphQL union

    Returns:
        dict mapping class names to the set of its subclass names.
    """
    if type_equivalence_hints is None:
        type_equivalence_hints = {}

    # A class is a subclass of itself.
    subclass_set = {
        classname: {classname}
        for classname, graphql_type in six.iteritems(schema.type_map)
        if isinstance(graphql_type, (GraphQLInterfaceType, GraphQLObjectType))
    }

    # A class is a subclass of interfaces it implements.
    for classname, graphql_type in six.iteritems(schema.type_map):
        if isinstance(graphql_type, GraphQLObjectType):
            for interface in graphql_type.interfaces:
                subclass_set[interface.name].add(classname)

    # The base of the union is a superclass of other members.
    for graphql_type, equivalent_type in six.iteritems(type_equivalence_hints):
        if isinstance(equivalent_type, GraphQLUnionType):
            for subclass in equivalent_type.types:
                subclass_set[graphql_type.name].add(subclass.name)
        else:
            raise AssertionError("Unexpected type {}".format(type(equivalent_type)))

    # Note that the inheritance structure in the GraphQL schema is already transitive. Union types
    # encompass all of the object type subclasses of their equivalent object type and cannot
    # encompass other union types. Interface types are implemented by all their object type
    # subclasses and cannot be implemented by other interface types.
    return subclass_set
