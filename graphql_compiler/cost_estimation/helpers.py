# Copyright 2019-present Kensho Technologies, LLC.
from graphql import GraphQLInt

from ..global_utils import is_same_type
from ..schema import GraphQLDate, GraphQLDateTime
from ..schema.schema_info import QueryPlanningSchemaInfo


def is_datetime_field_type(
    schema_info: QueryPlanningSchemaInfo, vertex_name: str, field_name: str
) -> bool:
    """Return whether the field is of type GraphQLDateTime."""
    field_type = schema_info.schema.get_type(vertex_name).fields[field_name].type
    return is_same_type(GraphQLDateTime, field_type)


def is_date_field_type(
    schema_info: QueryPlanningSchemaInfo, vertex_name: str, field_name: str
) -> bool:
    """Return whether the field is of type GraphQLDate."""
    field_type = schema_info.schema.get_type(vertex_name).fields[field_name].type
    return is_same_type(GraphQLDate, field_type)


def is_int_field_type(
    schema_info: QueryPlanningSchemaInfo, vertex_name: str, field_name: str
) -> bool:
    """Return whether the field is of type GraphQLInt."""
    field_type = schema_info.schema.get_type(vertex_name).fields[field_name].type
    return is_same_type(GraphQLInt, field_type)


def is_uuid4_type(schema_info: QueryPlanningSchemaInfo, vertex_name: str, field_name: str) -> bool:
    """Return whether the field is a uniformly distributed uuid4 type."""
    return field_name in schema_info.uuid4_fields.get(vertex_name, {})
