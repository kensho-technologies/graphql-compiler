# Copyright 2017-present Kensho Technologies, LLC.
from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal

import arrow
from graphql import (DirectiveLocation, GraphQLArgument, GraphQLDirective, GraphQLInt, GraphQLList,
                     GraphQLNonNull, GraphQLScalarType, GraphQLString)


# Constraints:
# - 'op_name' can only contain characters [A-Za-z_];
# - cannot be used at or within vertex fields marked @fold;
# - strings in 'value' can be encoded as '%tag_name' if referring to a tag named 'tag_name',
#   or as '$parameter_name' if referring to a parameter 'parameter_name' which will be provided
#   to the query at execution time.
FilterDirective = GraphQLDirective(
    name='filter',
    args=OrderedDict([(
        'op_name', GraphQLArgument(
            type=GraphQLNonNull(GraphQLString),
            description='Name of the filter operation to perform.',
        )),
        ('value', GraphQLArgument(
            type=GraphQLNonNull(GraphQLList(GraphQLNonNull(GraphQLString))),
            description='List of string operands for the operator.',
        ))]
    ),
    locations=[
        DirectiveLocation.FIELD,
        DirectiveLocation.INLINE_FRAGMENT,
    ]
)


# Constraints:
# - 'tag_name' can only contain characters [A-Za-z_];
# - 'tag_name' has to be distinct for each @output directive;
# - can only be applied to property fields;
# - cannot be applied to fields within a scope marked @fold.
TagDirective = GraphQLDirective(
    name='tag',
    args=OrderedDict([
        ('tag_name', GraphQLArgument(
            type=GraphQLNonNull(GraphQLString),
            description='Name to apply to the given property field.',
        )),
    ]),
    locations=[
        DirectiveLocation.FIELD,
    ]
)


# Constraints:
# - 'out_name' can only contain characters [A-Za-z_];
# - 'out_name' has to be distinct for each @output directive;
# - can only be applied to property fields.
OutputDirective = GraphQLDirective(
    name='output',
    args=OrderedDict([
        ('out_name', GraphQLArgument(
            type=GraphQLNonNull(GraphQLString),
            description='What to designate the output field generated from this property field.',
        )),
    ]),
    locations=[
        DirectiveLocation.FIELD,
    ]
)


# Gremlin queries are designed as pipelines, and do not capture the full Cartesian product of
# all possible traversals that would satisfy the query. For example, consider an example graph
# where vertices A and B are each connected with vertices X and Y via an edge of type E:
#
# A --E-> X, A --E-> Y
# B --E-> X, B --E-> Y
#
# If our query starts at vertices A and B, and traverses the outbound edge E,
# Gremlin will output two possible traversals: one ending in X, and one ending with Y.
# However, which predecessor vertex these traversals will have is undefined:
# one path will be one of {(A, X), (B, X)} and the other will be one of {(A, Y), (B, Y)}.
# A Cartesian product result (which is what OrientDB MATCH returns) would return all four
# traversals: {(A, X), (B, X), (A, Y), (B, Y)}.
#
# The @output_source directive is a mitigation strategy that allows users
# to specify *which* set of results they want fully covered. Namely,
# OutputSource on a given location will ensure that all possible values
# at that location are represented in at least one row of the returned result set.
#
# Constraints:
# - can exist at most once, and only on a vertex field;
# - if it exists, has to be on the last vertex visited by the query;
# - may not exist at or within a vertex marked @optional or @fold.
OutputSourceDirective = GraphQLDirective(
    name='output_source',
    locations=[
        DirectiveLocation.FIELD,
    ]
)


# Constraints:
# - can only be applied to vertex fields, except the root vertex of the query;
# - may not exist at the same vertex field as @recurse, @fold, or @output_source;
# - when filtering is applied on or within an @optional vertex field, evaluation is sequential:
#   the @optional is resolved first, and if a satisfactory edge exists, it is taken;
#   then, filtering is applied and eliminates results that don't match from the result set.
OptionalDirective = GraphQLDirective(
    name='optional',
    locations=[
        DirectiveLocation.FIELD,
    ]
)


# Consider the following query:
# {
#     Vertex_A {
#         name @output(out_name: "vertex_a_name")
#         out_Vertex_B {
#             name @output(out_name: "vertex_b_name")
#         }
#     }
# }
# The query will return one row (with keys "vertex_a_name" and "vertex_b_name")
# per possible traversal starting at a Vertex_A and going outbound toward the Vertex_B.
#
# Suppose you instead wanted one row per Vertex_A, containing Vertex_A's name
# and a list of Vertex_B names containing all the names of Vertex_B elements
# connected to the Vertex_A named by that row. This new query effectively "folds"
# the "vertex_b_name" outputs for each "vertex_a_name" into a list, similarly to
# the SQL operation GROUP BY but grouping according to graph structure rather than value.
# In other words, if two distinct Vertex_A vertices happen to be named the same,
# we'd like to receive two rows from our query -- one corresponding to each Vertex_A object.
# This is what the @fold decorator allows -- the query we should use is:
# {
#     Vertex_A {
#         name @output(out_name: "vertex_a_name")
#         out_Vertex_B @fold {
#             name @output(out_name: "vertex_b_name_list")
#         }
#     }
# }
#
# IMPORTANT: Normally, out_Vertex_B in the above query also filters the result set
#            such that Vertex_A objects with no corresponding Vertex_B objects are
#            not returned as results. When @fold is applied to out_Vertex_B, however,
#            this filtering is not applied, and "vertex_b_name_list" will return
#            an empty list for Vertex_A objects that don't have out_Vertex_B data.
#
# Constraints:
# - can only be applied to vertex fields, except the root vertex of the query;
# - may not exist at the same vertex field as @recurse, @optional, @output_source, or @filter;
# - traversals and filtering within a vertex field marked @fold are prohibited;
# - @tag or @fold may not be used within a scope marked @fold.
FoldDirective = GraphQLDirective(
    name='fold',
    locations=[
        DirectiveLocation.FIELD,
    ]
)


# Constraints:
# - may not be applied to the root vertex of the query (since it requires an edge to recurse on);
# - may not exist at or within a vertex marked @optional or @fold;
# - when not applied to vertex fields of union type, the vertex property type must
#   either be an interface type implemented by the type of the current scope, or must be the exact
#   same type as the type of the current scope;
# - inline fragments and filters within the @recurse block do not affect the recursion depth,
#   but simply eliminate some of its outputs;
# - it must always be the case that depth >= 1, where depth = 1 produces the current vertex
#   and its immediate neighbors along the specified edge.
RecurseDirective = GraphQLDirective(
    name='recurse',
    args=OrderedDict([
        ('depth', GraphQLArgument(
            type=GraphQLNonNull(GraphQLInt),
            description='Recurse up to this many times on this edge. A depth of 1 produces '
                        'the current vertex and its immediate neighbors along the given edge.',
        )),
    ]),
    locations=[
        DirectiveLocation.FIELD,
    ]
)


def _unused_function(*args, **kwargs):
    """Must not be called. Placeholder for functions that are required but aren't used."""
    raise NotImplementedError(u'The function you tried to call is not implemented, args / kwargs: '
                              u'{} {}'.format(args, kwargs))


def _serialize_date(value):
    """Serialize a Date object to its proper ISO-8601 representation."""
    if not isinstance(value, date):
        raise ValueError(u'The received object was not a date: '
                         u'{} {}'.format(type(value), value))
    return value.isoformat()


def _parse_date_value(value):
    """Deserialize a Date object from its proper ISO-8601 representation."""
    return arrow.get(value, 'YYYY-MM-DD').date()


def _serialize_datetime(value):
    """Serialize a DateTime object to its proper ISO-8601 representation."""
    if not isinstance(value, (datetime, arrow.Arrow)):
        raise ValueError(u'The received object was not a datetime: '
                         u'{} {}'.format(type(value), value))
    return value.isoformat()


def _parse_datetime_value(value):
    """Deserialize a DateTime object from its proper ISO-8601 representation."""
    if value.endswith('Z'):
        # Arrow doesn't support the "Z" literal to denote UTC time.
        # Strip the "Z" and add an explicit time zone instead.
        value = value[:-1] + '+00:00'

    return arrow.get(value, 'YYYY-MM-DDTHH:mm:ssZ').datetime


GraphQLDate = GraphQLScalarType(
    name='Date',
    description='The `Date` scalar type represents day-accuracy date objects.'
                'Values are serialized following the ISO-8601 datetime format specification, '
                'for example "2017-03-21". The year, month and day fields must be included, '
                'and the format followed exactly, or the behavior is undefined.',
    serialize=_serialize_date,
    parse_value=_parse_date_value,
    parse_literal=_unused_function,  # We don't yet support parsing Date objects in literals.
)


GraphQLDateTime = GraphQLScalarType(
    name='DateTime',
    description='The `DateTime` scalar type represents timezone-aware second-accuracy timestamps.'
                'Values are serialized following the ISO-8601 datetime format specification, '
                'for example "2017-03-21T12:34:56+00:00". All of these fields must be included, '
                'including the seconds and the time zone, and the format followed exactly, '
                'or the behavior is undefined.',
    serialize=_serialize_datetime,
    parse_value=_parse_datetime_value,
    parse_literal=_unused_function,  # We don't yet support parsing DateTime objects in literals.
)


GraphQLDecimal = GraphQLScalarType(
    name='Decimal',
    description='The `Decimal` scalar type is an arbitrary-precision decimal number object '
                'useful for representing values that should never be rounded, such as '
                'currency amounts. Values are allowed to be transported as either a native Decimal '
                'type, if the underlying transport allows that, or serialized as strings in '
                'decimal format, without thousands separators and using a "." as the '
                'decimal separator: for example, "12345678.012345".',
    serialize=str,
    parse_value=Decimal,
    parse_literal=_unused_function,  # We don't yet support parsing Decimal objects in literals.
)


DIRECTIVES = (
    FilterDirective,
    TagDirective,
    OutputDirective,
    OutputSourceDirective,
    OptionalDirective,
    RecurseDirective,
    FoldDirective,
)
