# Copyright 2019-present Kensho Technologies, LLC.
from typing import Dict, Union

from graphql import (
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLUnionType,
)


# The valid types that a field inside an object or interface in the GraphQL schema may be.
GraphQLSchemaFieldType = Union[GraphQLList, GraphQLNonNull, GraphQLScalarType]

# The type of the object that describes which type needs to have which field names forced to
# be a different type than would have been automatically inferred.
# Dict of GraphQL type name -> (Dict of field name on that type -> the desired type of the field)
ClassToFieldTypeOverridesType = Dict[str, Dict[str, GraphQLSchemaFieldType]]

# The type of the type equivalence hints object, which defines which GraphQL intefaces and object
# types should be considered equivalent to which union types. This is our workaround for the lack
# of interface-interface and object-object inheritance.
TypeEquivalenceHintsType = Dict[Union[GraphQLInterfaceType, GraphQLObjectType], GraphQLUnionType]
