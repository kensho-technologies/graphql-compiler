# Copyright 2019-present Kensho Technologies, LLC.
from typing import Union, cast

from graphql import (
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLObjectType,
    GraphQLScalarType,
)

from ..global_utils import is_same_type
from ..schema import GraphQLDate, GraphQLDateTime
from ..schema.schema_info import QueryPlanningSchemaInfo


def _get_field_type(
    schema_info: QueryPlanningSchemaInfo, vertex_name: str, field_name: str
) -> Union[GraphQLList, GraphQLScalarType]:
    return (
        cast(
            Union[GraphQLObjectType, GraphQLInterfaceType], schema_info.schema.get_type(vertex_name)
        )
        .fields[field_name]
        .type
    )


def is_datetime_field_type(
    schema_info: QueryPlanningSchemaInfo, vertex_name: str, field_name: str
) -> bool:
    """Return whether the field is of type GraphQLDateTime."""
    return is_same_type(GraphQLDateTime, _get_field_type(schema_info, vertex_name, field_name))


def is_date_field_type(
    schema_info: QueryPlanningSchemaInfo, vertex_name: str, field_name: str
) -> bool:
    """Return whether the field is of type GraphQLDate."""
    return is_same_type(GraphQLDate, _get_field_type(schema_info, vertex_name, field_name))


def is_int_field_type(
    schema_info: QueryPlanningSchemaInfo, vertex_name: str, field_name: str
) -> bool:
    """Return whether the field is of type GraphQLInt."""
    return is_same_type(GraphQLInt, _get_field_type(schema_info, vertex_name, field_name))


def is_uuid4_type(schema_info: QueryPlanningSchemaInfo, vertex_name: str, field_name: str) -> bool:
    """Return whether the field is a uniformly distributed uuid4 type."""
    return field_name in schema_info.uuid4_fields.get(vertex_name, {})
