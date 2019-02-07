# Copyright 2017-present Kensho Technologies, LLC.
from graphql.type.definition import GraphQLObjectType, GraphQLUnionType
import six


def _transitive_closure(graph):
    """Compute the transitive closure of a graph represented as dict inplace."""
    # Floyd-Warshall O(N^3)
    for k, k_out in six.iteritems(graph):
        for i, i_out in six.iteritems(graph):
            for j, j_out in six.iteritems(graph):
                if k in i_out and j in k_out:
                    graph.setdefault(i, set()).add(j)
    return graph


def compute_subclass_sets(schema, type_equivalence_hints):
    """Return a dict mapping class names to the set of its subclass names."""
    subclass_set = dict()

    for classname, cls in six.iteritems(schema.get_type_map()):
        # A class is a subclass of itself
        subclass_set.setdefault(classname, set()).add(classname)

        # A class is a subclass of interfaces it implements
        if isinstance(cls, GraphQLObjectType):
            for interface in cls.interfaces:
                subclass_set.setdefault(interface.name, set()).add(classname)

        # Members of a union subclass it
        if isinstance(cls, GraphQLUnionType):
            for subclass in cls.types:
                subclass_set.setdefault(classname, set()).add(subclass.name)

    # The base of the union is a superclass of other members
    for typ, equivalent_type in six.iteritems(type_equivalence_hints):
        if isinstance(equivalent_type, GraphQLUnionType):
            for subclass in equivalent_type.types:
                subclass_set.setdefault(typ.name, set()).add(subclass.name)
        else:
            raise AssertionError(u'Unexpected type {}'.format(type(equivalent_type)))


    # NOTE(bojanserafimov): Taking the transitive closure has no effect on the current schema.
    # If B subclasses A, and C subclasses B, then C subclasses A
    return _transitive_closure(subclass_set)
