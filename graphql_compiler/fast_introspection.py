# Copyright 2020-present Kensho Technologies, LLC.
"""Module to execute GraphQL introspection query faster than graphql-core.

The approach using graphql-core's graphql_sync() function is approximately 20x slower
than the code in this module. On a large schema with tens of thousands of types,
graphql_sync takes 26 seconds to run, whereas this module executes the same query in
1.37 seconds. This module calls the same Type resolvers as graphql_sync to prevent
code duplication with graphql-core.

The major difference between graphql_sync and this module is this module is very specific
to the introspection query, which removes the indirection that graphql_sync experiences as
graphql_sync must parse and traverse the query document to identify the next field to resolve,
whereas in this module, everything is hardcoded. This may be the source of the severe
performance difference.

This module is fully dependent on the introspection query returned by `get_introspection_query`
from graphql-core (with default parameters). Changes to that query will need to be
reflected in this module.
"""

from typing import Any, Dict, Optional, Tuple, cast

from graphql import (
    ExecutionResult,
    GraphQLAbstractType,
    GraphQLArgument,
    GraphQLDirective,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLNamedType,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLType,
    introspection_types,
    is_abstract_type,
    validate_schema,
)


_introspection_query = """
query IntrospectionQuery {
    __schema {
        queryType { name }
        mutationType { name }
        subscriptionType { name }
        types {
            ...FullType
        }
        directives {
            name
            description
            locations
            args {
                ...InputValue
            }
        }
    }
}

fragment FullType on __Type {
    kind
    name
    description
    fields(includeDeprecated: true) {
        name
        description
        args {
            ...InputValue
        }
        type {
            ...TypeRef
        }
        isDeprecated
        deprecationReason
    }
    inputFields {
        ...InputValue
    }
    interfaces {
        ...TypeRef
    }
    enumValues(includeDeprecated: true) {
        name
        description
        isDeprecated
        deprecationReason
    }
    possibleTypes {
        ...TypeRef
    }
}

fragment InputValue on __InputValue {
    name
    description
    type { ...TypeRef }
    defaultValue
}

fragment TypeRef on __Type {
    kind
    name
    ofType {
        kind
        name
        ofType {
            kind
            name
            ofType {
                kind
                name
                ofType {
                    kind
                    name
                    ofType {
                        kind
                        name
                        ofType {
                            kind
                            name
                            ofType {
                                kind
                                name
                            }
                        }
                    }
                }
            }
        }
    }
}
"""


def _remove_whitespace_from_query(query: str) -> str:
    """Return an equivalent query with spaces and newline characters removed."""
    return query.replace(" ", "").replace("\n", "")


_whitespace_free_introspection_query = _remove_whitespace_from_query(_introspection_query)


# Pylint appears to think that "introspection_types" is not dict-like.
# It is a FrozenDict, so this is a false-positive error.
# pylint: disable=unsubscriptable-object
__Schema = cast(GraphQLObjectType, introspection_types["__Schema"])
__Directive = cast(GraphQLObjectType, introspection_types["__Directive"])
__DirectiveLocation = cast(GraphQLEnumType, introspection_types["__DirectiveLocation"])
__Type = cast(GraphQLObjectType, introspection_types["__Type"])
__Field = cast(GraphQLObjectType, introspection_types["__Field"])
__InputValue = cast(GraphQLObjectType, introspection_types["__InputValue"])
__EnumValue = cast(GraphQLObjectType, introspection_types["__EnumValue"])
__TypeKind = cast(GraphQLEnumType, introspection_types["__TypeKind"])
# pylint: enable=unsubscriptable-object


def _get_type_ref(type_: GraphQLType) -> Dict[str, Any]:
    """Compute data for the TypeRef fragment of the introspection query for a particular type."""
    of_type = __Type.fields["ofType"].resolve(type_, None)
    return {
        "kind": __TypeKind.serialize(__Type.fields["kind"].resolve(type_, None)),
        "name": __Type.fields["name"].resolve(type_, None),
        "ofType": _get_type_ref(of_type) if of_type else None,
    }


def _get_input_value(arg: Tuple[str, GraphQLArgument]) -> Dict[str, Any]:
    """Compute data for the InputValue fragment of the introspection query for a particular arg."""
    return {
        "name": __InputValue.fields["name"].resolve(arg, None),
        "description": __InputValue.fields["description"].resolve(arg, None),
        "type": _get_type_ref(__InputValue.fields["type"].resolve(arg, None)),
        "defaultValue": __InputValue.fields["defaultValue"].resolve(arg, None),
    }


def _get_field(field: Tuple[str, GraphQLField]) -> Dict[str, Any]:
    """Compute data for `fields` field of the introspection query for a particular field."""
    return {
        "name": __Field.fields["name"].resolve(field, None),
        "description": __Field.fields["description"].resolve(field, None),
        "args": [_get_input_value(arg) for arg in __Field.fields["args"].resolve(field, None)],
        "type": _get_type_ref(__Field.fields["type"].resolve(field, None)),
        "isDeprecated": __Field.fields["isDeprecated"].resolve(field, None),
        "deprecationReason": __Field.fields["deprecationReason"].resolve(field, None),
    }


def _get_enum_value(enum_value: Tuple[str, GraphQLEnumValue]) -> Dict[str, Any]:
    """Compute data for `enumValues` field of the introspection query for a particular enumvalue."""
    return {
        "name": __EnumValue.fields["name"].resolve(enum_value, None),
        "description": __EnumValue.fields["description"].resolve(enum_value, None),
        "isDeprecated": __EnumValue.fields["isDeprecated"].resolve(enum_value, None),
        "deprecationReason": __EnumValue.fields["deprecationReason"].resolve(enum_value, None),
    }


def _get_full_type(type_: GraphQLNamedType, schema: GraphQLSchema) -> Dict[str, Any]:
    """Compute data for the FullType fragment of the introspection query for a particular type."""
    fields = __Type.fields["fields"].resolve(type_, None, includeDeprecated=True)
    input_fields = __Type.fields["inputFields"].resolve(type_, None)
    interfaces = __Type.fields["interfaces"].resolve(type_, None)
    enum_values = __Type.fields["enumValues"].resolve(type_, None, includeDeprecated=True)

    # The possibleTypes resolver requires GraphQLResolveInfo, so we just duplicate the resolver code
    # here instead of having to mock GraphQLResolveInfo accurately. Moreover, GraphQLResolveInfo
    # is for graphql-core internal use only, so it changes frequently.
    possible_types = (
        schema.get_possible_types(cast(GraphQLAbstractType, type_))
        if is_abstract_type(type_)
        else None
    )

    return {
        "kind": __TypeKind.serialize(__Type.fields["kind"].resolve(type_, None)),
        "name": __Type.fields["name"].resolve(type_, None),
        "description": __Type.fields["description"].resolve(type_, None),
        "fields": [_get_field(field) for field in fields] if fields else None,
        "inputFields": (
            [_get_input_value(field) for field in input_fields] if input_fields else None
        ),
        "interfaces": (
            None if interfaces is None else [_get_type_ref(interface) for interface in interfaces]
        ),
        "enumValues": (
            [_get_enum_value(enum_value) for enum_value in enum_values] if enum_values else None
        ),
        "possibleTypes": (
            [_get_type_ref(possible_type) for possible_type in possible_types]
            if possible_types
            else None
        ),
    }


def _get_directive(directive: GraphQLDirective) -> Dict[str, Any]:
    """Compute data for `directives` field of the introspection query for a particular directive."""
    return {
        "name": __Directive.fields["name"].resolve(directive, None),
        "description": __Directive.fields["description"].resolve(directive, None),
        "locations": [
            __DirectiveLocation.serialize(location)
            for location in __Directive.fields["locations"].resolve(directive, None)
        ],
        "args": [
            _get_input_value(arg) for arg in __Directive.fields["args"].resolve(directive, None)
        ],
    }


def _execute_fast_introspection_query(schema: GraphQLSchema) -> ExecutionResult:
    """Compute the GraphQL introspection query."""
    response_types = []
    for type_ in __Schema.fields["types"].resolve(schema, None):
        response_types.append(_get_full_type(type_, schema))

    response_directives = []
    for directive in __Schema.fields["directives"].resolve(schema, None):
        response_directives.append(_get_directive(directive))

    query_type = __Schema.fields["queryType"].resolve(schema, None)
    mutation_type = __Schema.fields["mutationType"].resolve(schema, None)
    subscription_type = __Schema.fields["subscriptionType"].resolve(schema, None)

    response: Dict[str, Any] = {
        "queryType": {"name": __Type.fields["name"].resolve(query_type, None)},
        "mutationType": (
            {"name": __Type.fields["name"].resolve(mutation_type, None)} if mutation_type else None
        ),
        "subscriptionType": (
            {"name": __Type.fields["name"].resolve(subscription_type, None)}
            if subscription_type
            else None
        ),
        "types": response_types,
        "directives": response_directives,
    }
    response_payload = {"__schema": response}

    return ExecutionResult(data=response_payload, errors=None)


def try_fast_introspection(schema: GraphQLSchema, query: str) -> Optional[ExecutionResult]:
    """Compute the GraphQL introspection query if query can be computed fastly.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        query: string containing the introspection query to be executed on the schema

    Returns:
        - GraphQL Execution Result with data = None: there were schema validation errors.
        - GraphQL ExecutionResult with data != None: fast introspection was successful and computed
          data can be found under data attribute.
        - None if the query does not match the set introspection query in this module: the query
          cannot be computed fastly with this module.
    """
    if _remove_whitespace_from_query(query) != _whitespace_free_introspection_query:
        return None

    # Schema validations
    schema_validation_errors = validate_schema(schema)
    if schema_validation_errors:
        return ExecutionResult(data=None, errors=schema_validation_errors)

    return _execute_fast_introspection_query(schema)
