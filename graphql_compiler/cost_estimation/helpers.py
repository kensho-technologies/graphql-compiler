# Copyright 2019-present Kensho Technologies, LLC.
from graphql import GraphQLInt


def is_int_field_type(schema_info, vertex_name, field_name):
    """Return whether the field is of type GraphQLInt."""
    field_type = schema_info.schema.get_type(vertex_name).fields[field_name].type
    return GraphQLInt.is_same_type(field_type)


def is_uuid4_type(schema_info, vertex_name, field_name):
    """Return whether the field is a uniformly distributed uuid4 type."""
    return field_name in schema_info.uuid4_fields.get(vertex_name, {})
