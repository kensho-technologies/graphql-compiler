from typing import Union

from graphql import GraphQLList, GraphQLNonNull, GraphQLScalarType


# The valid types that a field inside an object or interface in the GraphQL schema may be.
GraphQLSchemaFieldType = Union[GraphQLList, GraphQLNonNull, GraphQLScalarType]

# The type of the object that describes which type needs to have which field names forced to
# be a different type than would have been automatically inferred.
# Dict of GraphQL type name -> (Dict of field name on that type -> the desired type of the field)
ClassToFieldTypeOverridesType = Dict[str, Dict[str, GraphQLSchemaFieldType]]
