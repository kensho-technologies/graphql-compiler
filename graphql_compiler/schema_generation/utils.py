# Copyright 2019-present Kensho Technologies, LLC.
def amend_custom_scalar_types(schema, scalars):
    """Amend the serialization, parsing and description of custom scalar types in the schema.

       Information about the fields, (other than the name), of custom GraphQLScalarType objects is
       lost when GraphQLSchema objects are serialized into strings. This function uses the
       original type definitions to mutate the schema and reconstructs fields of custom
       scalar types.

       Args:
           schema: GraphQLSchema object
           scalars: set of GraphQLScalarType objects, the original custom GraphQLScalarType
                    objects.
    """
    # The schema text contains no information about how to parse or serialize non-builtin scalar
    # types so we add this information manually.
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
