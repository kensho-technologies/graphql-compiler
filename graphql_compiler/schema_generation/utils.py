# Copyright 2019-present Kensho Technologies, LLC.
def amend_custom_scalar_types(schema, scalars):
    """Amend the serialization, parsing and description of custom scalar types in the schema.

    Information about the description, serialization and parsing of custom scalar type
    objects is lost when a GraphQL schema is parsed from a string. This causes issues when
    working with custom scalar type objects. In order to avoid these issues, this function
    amends custom scalar type objects in the schema by using their original definitions.

    Args:
        schema: GraphQLSchema object that has possibly been parsed from a string. It might be
                mutated in-place in this function.
        scalars: set of GraphQLScalarType objects, the original custom GraphQLScalarType
                 objects.
    """
    for graphql_type in scalars:
        # We cannot simply replace the value corresponding to the key graphql_type.name.
        # We actually need to modify the value because it is referenced in other places in the
        # schema such as graphql object fields.
        matching_schema_type = schema.get_type(graphql_type.name)
        if matching_schema_type:
            matching_schema_type.description = graphql_type.description
            matching_schema_type.serialize = graphql_type.serialize
            matching_schema_type.parse_value = graphql_type.parse_value
            matching_schema_type.parse_literal = graphql_type.parse_literal
