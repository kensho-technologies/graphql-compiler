# Copyright 2017-present Kensho Technologies, LLC.
from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from itertools import chain
from typing import Any, FrozenSet, Iterable

# C-based module confuses pylint, which is why we disable the check below.
from ciso8601 import parse_datetime  # pylint: disable=no-name-in-module
from graphql import (
    DirectiveLocation,
    GraphQLArgument,
    GraphQLBoolean,
    GraphQLDirective,
    GraphQLField,
    GraphQLFloat,
    GraphQLID,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    GraphQLString,
    lexicographic_sort_schema,
    print_schema,
)
from graphql.type.directives import specified_directives
import six

from .typedefs import (  # noqa
    ClassToFieldTypeOverridesType,
    GraphQLSchemaFieldType,
    TypeEquivalenceHintsType,
)


# Constraints:
# - 'op_name' can only contain characters [A-Za-z_];
# - cannot be used at or within vertex fields marked @fold;
# - strings in 'value' can be encoded as '%tag_name' if referring to a tag named 'tag_name',
#   or as '$parameter_name' if referring to a parameter 'parameter_name' which will be provided
#   to the query at execution time.
FilterDirective = GraphQLDirective(
    name="filter",
    args=OrderedDict(
        [
            (
                "op_name",
                GraphQLArgument(
                    type_=GraphQLNonNull(GraphQLString),
                    description="Name of the filter operation to perform.",
                ),
            ),
            (
                "value",
                GraphQLArgument(
                    type_=GraphQLList(GraphQLNonNull(GraphQLString)),
                    description="List of string operands for the operator.",
                ),
            ),
        ]
    ),
    is_repeatable=True,
    locations=[
        DirectiveLocation.FIELD,
        DirectiveLocation.INLINE_FRAGMENT,
    ],
)


# Constraints:
# - 'tag_name' can only contain characters [A-Za-z_];
# - 'tag_name' has to be distinct for each @output directive;
# - can only be applied to property fields;
# - cannot be applied to fields within a scope marked @fold.
TagDirective = GraphQLDirective(
    name="tag",
    args=OrderedDict(
        [
            (
                "tag_name",
                GraphQLArgument(
                    type_=GraphQLNonNull(GraphQLString),
                    description="Name to apply to the given property field.",
                ),
            ),
        ]
    ),
    locations=[
        DirectiveLocation.FIELD,
    ],
)


# Constraints:
# - 'out_name' can only contain characters [A-Za-z_];
# - 'out_name' has to be distinct for each @output directive;
# - can only be applied to property fields.
OutputDirective = GraphQLDirective(
    name="output",
    args=OrderedDict(
        [
            (
                "out_name",
                GraphQLArgument(
                    type_=GraphQLNonNull(GraphQLString),
                    description=(
                        "What to designate the output field generated from this property field."
                    ),
                ),
            ),
        ]
    ),
    locations=[
        DirectiveLocation.FIELD,
    ],
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
    name="output_source",
    locations=[
        DirectiveLocation.FIELD,
    ],
)


# Constraints:
# - can only be applied to vertex fields, except the root vertex of the query;
# - may not exist at the same vertex field as @recurse, @fold, or @output_source;
# - when filtering is applied on or within an @optional vertex field, evaluation is sequential:
#   the @optional is resolved first, and if a satisfactory edge exists, it is taken;
#   then, filtering is applied and eliminates results that don't match from the result set.
OptionalDirective = GraphQLDirective(
    name="optional",
    locations=[
        DirectiveLocation.FIELD,
    ],
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
    name="fold",
    locations=[
        DirectiveLocation.FIELD,
    ],
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
    name="recurse",
    args=OrderedDict(
        [
            (
                "depth",
                GraphQLArgument(
                    type_=GraphQLNonNull(GraphQLInt),
                    description=(
                        "Recurse up to this many times on this edge. A depth of 1 produces "
                        "the current vertex and its immediate neighbors along the given edge."
                    ),
                ),
            ),
        ]
    ),
    locations=[
        DirectiveLocation.FIELD,
    ],
)

# TODO(selene): comments for the macro directives
MacroEdgeDirective = GraphQLDirective(
    name="macro_edge",
    locations=[
        # Used to mark edges that are defined via macros in the schema.
        DirectiveLocation.FIELD_DEFINITION,
    ],
)


MacroEdgeDefinitionDirective = GraphQLDirective(
    name="macro_edge_definition",
    args=OrderedDict(
        [
            (
                "name",
                GraphQLArgument(
                    type_=GraphQLNonNull(GraphQLString),
                    description="Name of the macro edge.",
                ),
            ),
        ]
    ),
    locations=[
        DirectiveLocation.FIELD,
    ],
)


MacroEdgeTargetDirective = GraphQLDirective(
    name="macro_edge_target",
    locations=[
        DirectiveLocation.FIELD,
        DirectiveLocation.INLINE_FRAGMENT,
    ],
)

# TODO(selene): comment for the stitch directive
StitchDirective = GraphQLDirective(
    name="stitch",
    args=OrderedDict(
        [
            (
                "source_field",
                GraphQLArgument(
                    type_=GraphQLNonNull(GraphQLString),
                    description="",
                ),
            ),
            (
                "sink_field",
                GraphQLArgument(
                    type_=GraphQLNonNull(GraphQLString),
                    description="",
                ),
            ),
        ]
    ),
    locations=[DirectiveLocation.FIELD_DEFINITION],
)

OUTBOUND_EDGE_FIELD_PREFIX = "out_"
INBOUND_EDGE_FIELD_PREFIX = "in_"
VERTEX_FIELD_PREFIXES = frozenset({OUTBOUND_EDGE_FIELD_PREFIX, INBOUND_EDGE_FIELD_PREFIX})


def is_vertex_field_name(field_name: str) -> bool:
    """Return True if the field's name indicates it is a non-root vertex field."""
    # N.B.: A vertex field is a field whose type is a vertex type. This is what edges are.
    return field_name.startswith(OUTBOUND_EDGE_FIELD_PREFIX) or field_name.startswith(
        INBOUND_EDGE_FIELD_PREFIX
    )


def _unused_function(*args: Any, **kwargs: Any) -> None:
    """Must not be called. Placeholder for functions that are required but aren't used."""
    raise NotImplementedError(
        "The function you tried to call is not implemented, args / kwargs: "
        "{} {}".format(args, kwargs)
    )


def _serialize_date(value: Any) -> str:
    """Serialize a Date object to its proper ISO-8601 representation."""
    # Python datetime.datetime is a subclass of datetime.date, but in this case, the two are not
    # interchangeable. Rather than using isinstance, we will therefore check for exact type
    # equality.
    if type(value) != date:
        raise ValueError(
            "Expected argument to be a python date object. "
            "Got {} of type {} instead.".format(value, type(value))
        )
    return value.isoformat()


def _parse_date_value(value: Any) -> date:
    """Deserialize a Date object from its proper ISO-8601 representation."""
    if type(value) == date:
        # We prefer exact type equality instead of isinstance() because datetime objects
        # are subclasses of date but are not interchangeable for dates for our purposes.
        return value
    elif isinstance(value, str):
        # ciso8601 only supports parsing into datetime objects, not date objects.
        # This is not a problem in itself: "YYYY-MM-DD" strings will get parsed into datetimes
        # with hour/minute/second/microsecond set to 0, and tzinfo=None.
        # We don't want our parsing to implicitly lose precision, so before we convert the parsed
        # datetime into a date value, we just assert that these fields are set as expected.
        dt = parse_datetime(value)  # This will raise ValueError in case of bad ISO 8601 formatting.
        if (
            dt.hour != 0
            or dt.minute != 0
            or dt.second != 0
            or dt.microsecond != 0
            or dt.tzinfo is not None
        ):
            raise ValueError(
                f"Expected an ISO-8601 date string in 'YYYY-MM-DD' format, but got a datetime "
                f"string with a non-empty time component. This is not supported, since converting "
                f"it to a date would result in an implicit loss of precision. Received value "
                f"{repr(value)}, parsed as {dt}."
            )

        return dt.date()
    else:
        raise ValueError(
            f"Expected a date object or its ISO-8601 'YYYY-MM-DD' string representation. "
            f"Got {value} of type {type(value)} instead."
        )


def _serialize_datetime(value: Any) -> str:
    """Serialize a DateTime object to its proper ISO-8601 representation."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.isoformat()
    else:
        raise ValueError(
            f"Expected a timezone-naive datetime object. Got {value} of type {type(value)} instead."
        )


def _parse_datetime_value(value: Any) -> datetime:
    """Deserialize a DateTime object from a date/datetime or a ISO-8601 string representation."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value
    elif isinstance(value, str):
        dt = parse_datetime(value)  # This will raise ValueError in case of bad ISO 8601 formatting.
        if dt.tzinfo is not None:
            raise ValueError(
                f"Expected a timezone-naive datetime value, but got a timezone-aware datetime "
                f"string. This is not supported, since discarding the timezone component would "
                f"result in an implicit loss of precision. Received value {repr(value)}, "
                f"parsed as {dt}."
            )

        return dt
    elif type(value) == date:
        # The date type is a supertype of datetime. We check for exact type equality
        # rather than using isinstance(), to avoid having this branch get hit
        # by timezone-aware datetimes (i.e. ones that fail the value.tzinfo is None check above).
        #
        # This is a widening conversion (there's no loss of precision) so we allow it to be implicit
        # since use ciso8601 parsing logic for parsing datetimes, and ciso8601 successfully parses
        # datetimes that only have data down to day precision.
        return datetime(value.year, value.month, value.day)
    else:
        raise ValueError(
            f"Expected a timezone-naive datetime or an ISO-8601 string representation parseable "
            f"by the ciso8601 library. Got {value} of type {type(value)} instead."
        )


GraphQLDate = GraphQLScalarType(
    name="Date",
    description=(
        "The `Date` scalar type represents day-accuracy date objects."
        "Values are serialized following the ISO-8601 datetime format specification, "
        'for example "2017-03-21". Serialization and parsing support is guaranteed for the format '
        "described here, with the year, month and day fields included and separated by dashes as "
        "in the example. Implementations are allowed to support additional serialization formats, "
        "if they so choose."
        # GraphQL compiler's implementation of GraphQL-based querying uses the ciso8601 library
        # for date and datetime parsing, so it additionally supports the subset of the ISO-8601
        # standard supported by that library.
    ),
    serialize=_serialize_date,
    parse_value=_parse_date_value,
    parse_literal=_unused_function,  # We don't yet support parsing Date objects in literals.
)


GraphQLDateTime = GraphQLScalarType(
    name="DateTime",
    description=(
        "The `DateTime` scalar type represents timezone-naive timestamps with up to microsecond "
        "accuracy. Values are serialized following the ISO-8601 datetime format specification, "
        'for example "2017-03-21T12:34:56.012345" or "2017-03-21T12:34:56". Serialization and '
        "parsing support is guaranteed for the format described here, with all fields down to "
        "and including seconds required to be included, and fractional seconds optional, as in "
        "the example. Implementations are allowed to support additional serialization formats, "
        "if they so choose."
        # GraphQL compiler's implementation of GraphQL-based querying uses the ciso8601 library
        # for date and datetime parsing, so it additionally supports the subset of the ISO-8601
        # standard supported by that library.
    ),
    serialize=_serialize_datetime,
    parse_value=_parse_datetime_value,
    parse_literal=_unused_function,  # We don't yet support parsing DateTime objects in literals.
)


GraphQLDecimal = GraphQLScalarType(
    name="Decimal",
    description=(
        "The `Decimal` scalar type is an arbitrary-precision decimal number object "
        "useful for representing values that should never be rounded, such as "
        "currency amounts. Values are allowed to be transported as either a native Decimal "
        "type, if the underlying transport allows that, or serialized as strings in "
        'decimal format, without thousands separators and using a "." as the '
        'decimal separator: for example, "12345678.012345".'
    ),
    serialize=str,
    parse_value=Decimal,
    parse_literal=_unused_function,  # We don't yet support parsing Decimal objects in literals.
)

CUSTOM_SCALAR_TYPES: FrozenSet[GraphQLScalarType] = frozenset(
    {
        GraphQLDecimal,
        GraphQLDate,
        GraphQLDateTime,
    }
)
SUPPORTED_SCALAR_TYPES: FrozenSet[GraphQLScalarType] = frozenset(
    {
        GraphQLInt,
        GraphQLString,
        GraphQLBoolean,
        GraphQLFloat,
        GraphQLID,
    }
).union(CUSTOM_SCALAR_TYPES)

DIRECTIVES = (
    FilterDirective,
    TagDirective,
    OutputDirective,
    OutputSourceDirective,
    OptionalDirective,
    RecurseDirective,
    FoldDirective,
    MacroEdgeDirective,
    StitchDirective,
)


TYPENAME_META_FIELD_NAME = "__typename"  # This meta field is built-in.
COUNT_META_FIELD_NAME = "_x_count"


ALL_SUPPORTED_META_FIELDS = frozenset(
    (
        TYPENAME_META_FIELD_NAME,
        COUNT_META_FIELD_NAME,
    )
)


EXTENDED_META_FIELD_DEFINITIONS = OrderedDict(((COUNT_META_FIELD_NAME, GraphQLField(GraphQLInt)),))


def is_meta_field(field_name: str) -> bool:
    """Return True if the field is considered a meta field in the schema, and False otherwise."""
    return field_name in ALL_SUPPORTED_META_FIELDS


def insert_meta_fields_into_existing_schema(graphql_schema: GraphQLSchema) -> None:
    """Add compiler-specific meta-fields into all interfaces and types of the specified schema.

    It is preferable to use the EXTENDED_META_FIELD_DEFINITIONS constant above to directly inject
    the meta-fields during the initial process of building the schema, as that approach
    is more robust. This function does its best to not mutate unexpected definitions, but
    may break unexpectedly as the GraphQL standard is extended and the underlying
    GraphQL library is updated.

    Use this function at your own risk. Don't say you haven't been warned.

    Properties added include:
        - "_x_count", which allows filtering folds based on the number of elements they capture.

    Args:
        graphql_schema: GraphQLSchema object describing the schema that is going to be used with
                        the compiler. N.B.: MUTATED IN-PLACE in this method.
    """
    query_type = graphql_schema.query_type
    if query_type is None:
        raise AssertionError(
            f"Unexpectedly received a GraphQL schema with no defined query type. It is impossible "
            f"to insert GraphQL compiler's meta fields into such a schema, since the schema cannot "
            f"be used for querying with GraphQL compiler. Received schema type map: "
            f"{graphql_schema.type_map}"
        )

    root_type_name = query_type.name

    for type_name, type_obj in six.iteritems(graphql_schema.type_map):
        if type_name.startswith("__") or type_name == root_type_name:
            # Ignore the types that are built into GraphQL itself, as well as the root query type.
            continue

        if not isinstance(type_obj, (GraphQLObjectType, GraphQLInterfaceType)):
            # Ignore definitions that are not interfaces or types.
            continue

        for meta_field_name, meta_field in six.iteritems(EXTENDED_META_FIELD_DEFINITIONS):
            if meta_field_name in type_obj.fields:
                raise AssertionError(
                    "Unexpectedly encountered an existing field named {} while "
                    "attempting to add a meta-field of the same name. Make sure "
                    "you are not attempting to add meta-fields twice.".format(meta_field_name)
                )

            type_obj.fields[meta_field_name] = meta_field


def check_for_nondefault_directive_names(directives: Iterable[GraphQLDirective]) -> None:
    """Check if any user-created directives are present."""
    # Include compiler-supported directives, and the default directives GraphQL defines.
    expected_directive_names = {
        directive.name for directive in chain(DIRECTIVES, specified_directives)
    }

    directive_names = {directive.name for directive in directives}

    nondefault_directives_found = directive_names - expected_directive_names
    if nondefault_directives_found:
        raise AssertionError("Unsupported directives found: {}".format(nondefault_directives_found))


def compute_schema_fingerprint(schema: GraphQLSchema) -> str:
    """Compute a fingerprint compactly representing the data in the given schema.

    The fingerprint is not sensitive to things like type or field order. This function is guaranteed
    to be robust enough that if two GraphQLSchema have the same fingerprint, then they also
    represent the same schema.

    Because of internal implementation changes, different versions of this library *may* produce
    different fingerprints for the same schema. Since cross-version fingerprint stability
    is an *explicit non-goal* here, changing a schema's fingerprint will not be considered
    a breaking change.

    The fingerprint is computed on a best-effort basis and has some known issues at the moment.
    Please see the discussion in the pull request below for more details.
    https://github.com/kensho-technologies/graphql-compiler/pull/737

    Args:
        schema: the schema for which to compute a fingerprint.

    Returns:
        a hexadecimal string fingerprint compactly representing the data in the schema.
    """
    lexicographically_sorted_schema = lexicographic_sort_schema(schema)
    text = print_schema(lexicographically_sorted_schema)
    return sha256(text.encode("utf-8")).hexdigest()
