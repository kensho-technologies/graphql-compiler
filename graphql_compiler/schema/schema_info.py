# Copyright 2019-present Kensho Technologies, LLC.
from abc import ABCMeta
from collections import namedtuple
from dataclasses import dataclass, field
from enum import Enum, Flag, auto, unique
from functools import partial
from typing import AbstractSet, Dict, Mapping, Optional, Sequence, Tuple, Union

from graphql.type import GraphQLSchema
from graphql.type.definition import GraphQLInterfaceType, GraphQLObjectType
import six
import sqlalchemy
from sqlalchemy.dialects.mssql import dialect as mssql_dialect
from sqlalchemy.dialects.mysql import dialect as mysql_dialect
from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect
from sqlalchemy.engine.interfaces import Dialect

from . import TypeEquivalenceHintsType, is_vertex_field_name
from ..cost_estimation.statistics import Statistics
from ..schema_generation.schema_graph import SchemaGraph


@dataclass(frozen=True)
class DirectJoinDescriptor:
    """Describes the ability to join two tables using the specified columns.

    The resulting join expression could be something like:
    JOIN origin_table.from_column = destination_table.to_column

    The type of join (inner vs left, etc.) is not specified.
    The tables are not specified.
    """

    from_column: str  # The column in the source table we intend to join on.
    to_column: str  # The column in the destination table we intend to join on.


@dataclass(frozen=True)
class CompositeJoinDescriptor:
    """Describes the ability to join two tables with a composite relationship.

    The resulting join expression could be something like:
    JOIN
        origin_table.from_column_1 == destination_table.to_column_1 AND
        origin_table.from_column_2 == destination_table.to_column_2 AND
        origin_table.from_column_3 == destination_table.to_column_3

    The type of join (inner vs left, etc.) is not specified.
    The tables are not specified.
    """

    # (from_column, to_column) pairs, where from_column is on the origin table
    # and to_column is on the destination table of the join.
    column_pairs: AbstractSet[Tuple[str, str]]

    def __post_init__(self) -> None:
        """Validate fields."""
        if not self.column_pairs:
            raise AssertionError("The column_pairs field is expected to be non-empty.")


JoinDescriptor = Union[DirectJoinDescriptor, CompositeJoinDescriptor]


@dataclass
class GenericSchemaInfo:
    """Class for storing generic schema info required for querying."""

    schema: GraphQLSchema

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
    # TODO: make sure we are treating empty dict the same as None
    type_equivalence_hints: Optional[Dict[str, str]]


@dataclass
class BackendSpecificSchemaInfo(metaclass=ABCMeta):
    """Common base class to be used by all backend-specific schema info classes.

    This helps hide that the data actually lives one nesting level deeper.
    """

    generic_schema_info: GenericSchemaInfo

    @property
    def schema(self) -> GraphQLSchema:
        """Return schema."""
        return self.generic_schema_info.schema

    @property
    def type_equivalence_hints(self) -> Optional[Dict[str, str]]:
        """Return type equivalence hints."""
        return self.generic_schema_info.type_equivalence_hints


@dataclass
class MatchSchemaInfo(BackendSpecificSchemaInfo):
    pass


def create_match_schema_info(
    schema: GraphQLSchema, type_equivalence_hints: Optional[Dict[str, str]] = None
) -> MatchSchemaInfo:
    """Create a SchemaInfo object for a database using MATCH."""
    generic_schema_info = GenericSchemaInfo(
        schema=schema, type_equivalence_hints=type_equivalence_hints
    )
    return MatchSchemaInfo(generic_schema_info=generic_schema_info)


@dataclass
class GremlinSchemaInfo(BackendSpecificSchemaInfo):
    pass


def create_gremlin_schema_info(
    schema: GraphQLSchema, type_equivalence_hints: Optional[Dict[str, str]] = None
) -> GremlinSchemaInfo:
    """Create a SchemaInfo object for a database using Gremlin."""
    generic_schema_info = GenericSchemaInfo(
        schema=schema, type_equivalence_hints=type_equivalence_hints
    )
    return GremlinSchemaInfo(generic_schema_info=generic_schema_info)


@dataclass
class CypherSchemaInfo(BackendSpecificSchemaInfo):
    pass


def create_cypher_schema_info(
    schema: GraphQLSchema, type_equivalence_hints: Optional[Dict[str, str]] = None
) -> CypherSchemaInfo:
    """Create a SchemaInfo object for a database using Cypher."""
    generic_schema_info = GenericSchemaInfo(
        schema=schema, type_equivalence_hints=type_equivalence_hints
    )
    return CypherSchemaInfo(generic_schema_info=generic_schema_info)


@dataclass
class SQLSchemaInfo(BackendSpecificSchemaInfo):
    """Schema information specific to SQL databases.

    If the flavors start diverging in their attributes, consider making a class per flavor.
    """

    # Specifying the dialect for which we are compiling
    # e.g. sqlalchemy.dialects.mssql.dialect()
    dialect: Dialect
    # dict mapping every GraphQL object type or interface type name in the schema to
    # a sqlalchemy table.
    # Column types that do not exist for this dialect are not allowed.
    # All tables are expected to have primary keys.

    vertex_name_to_table: Dict[str, sqlalchemy.Table]
    # dict mapping every GraphQL object type or interface type name in the schema to
    # dict mapping every vertex field name at that type to a JoinDescriptor.
    # The tables the join is to be performed on are not specified.
    # They are inferred from the schema and the tables dictionary.
    join_descriptors: Dict[str, Dict[str, JoinDescriptor]]


def _create_sql_schema_info(
    dialect: Dialect,
    schema: GraphQLSchema,
    vertex_name_to_table: Dict[str, sqlalchemy.Table],
    join_descriptors: Dict[str, Dict[str, JoinDescriptor]],
    type_equivalence_hints: Optional[Dict[str, str]] = None,
) -> SQLSchemaInfo:
    """Create a SQLSchemaInfo object for a database using a flavor of SQL."""
    generic_schema_info = GenericSchemaInfo(
        schema=schema, type_equivalence_hints=type_equivalence_hints
    )

    return SQLSchemaInfo(
        generic_schema_info=generic_schema_info,
        dialect=dialect,
        vertex_name_to_table=vertex_name_to_table,
        join_descriptors=join_descriptors,
    )


create_postgresql_schema_info = partial(_create_sql_schema_info, postgresql_dialect)
create_mssql_schema_info = partial(_create_sql_schema_info, mssql_dialect)
create_mysql_schema_info = partial(_create_sql_schema_info, mysql_dialect)


# Complete schema information sufficient to compile GraphQL queries for most backends
CommonSchemaInfo = namedtuple(
    "CommonSchemaInfo",
    (
        # GraphQLSchema
        "schema",
        # optional dict of GraphQL interface or type -> GraphQL union.
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
        "type_equivalence_hints",
    ),
)


# Complete schema information sufficient to compile GraphQL queries to SQLAlchemy
#
# It describes the tables that correspond to each type (object type or interface type),
# and gives instructions on how to perform joins for each vertex field. The property fields on each
# type are implicitly mapped to columns with the same name on the corresponding table.
#
# NOTES:
# - RootSchemaQuery is a special type that does not need a corresponding table.
# - Builtin types like __Schema, __Type, etc. don't need corresponding tables.
# - Builtin fields like _x_count do not need corresponding columns.
SQLAlchemySchemaInfo = namedtuple(
    "SQLAlchemySchemaInfo",
    (
        # GraphQLSchema
        "schema",
        # optional dict of GraphQL interface or type -> GraphQL union.
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
        "type_equivalence_hints",
        # sqlalchemy.engine.interfaces.Dialect, specifying the dialect we are compiling for
        # (e.g. sqlalchemy.dialects.mssql.dialect()).
        "dialect",
        # dict mapping every graphql object type or interface type name in the schema to
        # a sqlalchemy table. Column types that do not exist for this dialect are not allowed.
        # All tables are expected to have primary keys.
        "vertex_name_to_table",
        # dict mapping every graphql object type or interface type name in the schema to:
        #    dict mapping every vertex field name at that type to a JoinDescriptor. The
        #    tables the join is to be performed on are not specified. They are inferred from
        #    the schema and the tables dictionary.
        "join_descriptors",
    ),
)


def make_sqlalchemy_schema_info(
    schema: GraphQLSchema,
    type_equivalence_hints: TypeEquivalenceHintsType,
    dialect: Dialect,
    vertex_name_to_table: Dict[str, sqlalchemy.Table],
    join_descriptors: Dict[str, Dict[str, JoinDescriptor]],
    validate: bool = True,
) -> SQLAlchemySchemaInfo:
    """Make a SQLAlchemySchemaInfo if the input provided is valid.

    See the documentation of SQLAlchemySchemaInfo for more detailed documentation of the args.

    Args:
        schema: GraphQLSchema describing the schema against which queries can be written
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
        dialect: SQLAlchemy Dialect object specifying the SQL dialect that should be used to query
                 this schema
        vertex_name_to_table: dict mapping every GraphQL object type or interface type name in the
                              schema to a SQLAlchemy table
        join_descriptors: dict mapping GraphQL object and interface type names in the schema to:
                          dict mapping every vertex field name at that type to a
                          JoinDescriptor. The tables on which the join is to be performed
                          are not specified. They are inferred from the schema and the tables
                          dictionary.
        validate: whether to validate that the given inputs are valid for creation of
                  a SQLAlchemySchemaInfo object. Disabling validation may improve performance for
                  particularly large schemas, at the risk of constructing an invalid schema info.

    Returns:
        SQLAlchemySchemaInfo containing the input arguments provided
    """
    if validate:
        types_to_map = (GraphQLInterfaceType, GraphQLObjectType)
        builtin_fields = {
            "_x_count",
        }
        # TODO(bojanserafimov): More validation can be done:
        # - are the types of the columns compatible with the GraphQL type of the property field?
        # - do joins join on columns on which the (=) operator makes sense?
        # - do inherited columns have exactly the same type on the parent and child table?
        # - are all the column types available in this dialect?
        for type_name, graphql_type in six.iteritems(schema.type_map):
            if isinstance(graphql_type, types_to_map):
                if type_name != "RootSchemaQuery" and not type_name.startswith("__"):
                    # Check existence of sqlalchemy table for this type
                    if type_name not in vertex_name_to_table:
                        raise AssertionError("Table for type {} not found".format(type_name))
                    table = vertex_name_to_table[type_name]
                    if not isinstance(table, sqlalchemy.Table):
                        raise AssertionError(
                            "Table for type {} has wrong type {}".format(type_name, type(table))
                        )

                    # Check existence of all fields
                    for field_name in six.iterkeys(graphql_type.fields):
                        if is_vertex_field_name(field_name):
                            if field_name not in join_descriptors.get(type_name, {}):
                                raise AssertionError(
                                    "No join descriptor was specified for vertex "
                                    "field {} on type {}".format(field_name, type_name)
                                )
                        else:
                            if field_name not in builtin_fields and field_name not in table.c:
                                raise AssertionError(
                                    "Table for type {} has no column "
                                    "for property field {}".format(type_name, field_name)
                                )

    return SQLAlchemySchemaInfo(
        schema, type_equivalence_hints, dialect, vertex_name_to_table, join_descriptors
    )


@unique
class EdgeConstraint(Flag):
    """An integrity constraint on an edge in the schema."""

    AtLeastOneSource = auto()
    AtMostOneSource = auto()
    AtLeastOneDestination = auto()
    AtMostOneDestination = auto()


@unique
class UUIDOrdering(Enum):
    """Specifies how the database would compare two uuid values."""

    # Leftmost digits are most significant. This is the usual comparison method in
    # Postgres, Orientdb, and likely many other databases.
    LeftToRight = auto()

    # The most significant digits are the last 12 hex digits (6 bytes), followed
    # by the first digits, left to right. This is the comparison method in MSSQL.
    LastSixBytesFirst = auto()


@dataclass
class QueryPlanningSchemaInfo:
    """All schema information sufficient for query cost estimation and auto pagination."""

    # The schema used for querying
    schema: GraphQLSchema

    # optional dict of GraphQL interface or type -> GraphQL union.
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
    type_equivalence_hints: TypeEquivalenceHintsType

    # A SchemaGraph instance that corresponds to the GraphQLSchema, containing additional
    # information on unique indexes, subclass sets, and edge base connection classes.
    schema_graph: SchemaGraph

    # A Statistics object giving statistical information about all objects in the schema.
    statistics: Statistics

    # Mapping vertex names in the graphql schema to the non-empty sequence of property names
    # that are eligible pagination on that vertex in a general context. Some of the provided
    # properties might be ineligible for pagination in certain queries, for instance if the
    # query has a "=" filter on the field and it's uniquely indexed. The order of properties
    # within this sequence is used as a final (least significant) step in choosing which one
    # to use when multiple options are available.
    #
    # If a vertex name is omitted from this dict, the entire vertex is ineligible for pagination.
    pagination_keys: Mapping[str, Sequence[str]]

    # Dict mapping vertex names in the graphql schema to a dict mapping property names that
    # are known to contain uniformly distributed uuid values to the ordering method used for
    # them in the database. The types of these fields are expected to be ID or String.
    uuid4_field_info: Dict[str, Dict[str, UUIDOrdering]]

    # Map edge names to constraints inferred for them.
    edge_constraints: Dict[str, EdgeConstraint] = field(default_factory=dict)
