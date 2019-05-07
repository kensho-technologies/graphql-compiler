# Copyright 2017-present Kensho Technologies, LLC.
from graphql.type.definition import GraphQLObjectType, GraphQLUnionType
import six


def compute_subclass_sets(schema, type_equivalence_hints=None):
    """Return a dict mapping class names to the set of its direct subclass names.

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
        dict mapping class names to the set of its direct subclass names.
    """
    if type_equivalence_hints is None:
        type_equivalence_hints = {}

    # A class is a subclass of itself
    subclass_set = {
        classname: {classname}
        for classname in six.iterkeys(schema.get_type_map())
    }

    # A class is a subclass of interfaces it implements
    for classname, graphql_type in six.iteritems(schema.get_type_map()):
        if isinstance(graphql_type, GraphQLObjectType):
            for interface in graphql_type.interfaces:
                subclass_set[interface.name].add(classname)

    # The base of the union is a superclass of other members
    for graphql_type, equivalent_type in six.iteritems(type_equivalence_hints):
        if isinstance(equivalent_type, GraphQLUnionType):
            for subclass in equivalent_type.types:
                subclass_set[graphql_type.name].add(subclass.name)
        else:
            raise AssertionError(u'Unexpected type {}'.format(type(equivalent_type)))

    return subclass_set
