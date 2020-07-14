"""Module to execute GraphQL introspection query faster than graphql-core.

On a large schema with tens of thousands of types, the approach using graphql-core's
graphql_sync takes 26 seconds to run, whereas this module executes the same query in
1.37 seconds. This module calls the same Type resolvers as graphql_sync to prevent
code duplication with graphql-core.

This module is fully dependent on the introspection query returned by `get_introspection_query`
from graphql-core (with default parameters). Changes to that query will need to be
reflected in this module. This module also assumes that the introspection query can
be executed on the given schema.
"""


from typing import Any, Dict, Tuple, cast

from graphql import (
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
)


__Schema = cast(GraphQLObjectType, introspection_types["__Schema"])
__Directive = cast(GraphQLObjectType, introspection_types["__Directive"])
__DirectiveLocation = cast(GraphQLEnumType, introspection_types["__DirectiveLocation"])
__Type = cast(GraphQLObjectType, introspection_types["__Type"])
__Field = cast(GraphQLObjectType, introspection_types["__Field"])
__InputValue = cast(GraphQLObjectType, introspection_types["__InputValue"])
__EnumValue = cast(GraphQLObjectType, introspection_types["__EnumValue"])
__TypeKind = cast(GraphQLEnumType, introspection_types["__TypeKind"])


def _get_type_ref(type_: GraphQLType) -> Dict[str, Any]:
    of_type = __Type.fields["ofType"].resolve(type_, None)
    return {
        "kind": __TypeKind.serialize(__Type.fields["kind"].resolve(type_, None)),
        "name": __Type.fields["name"].resolve(type_, None),
        "ofType": _get_type_ref(of_type) if of_type else None,
    }


def _get_input_value(arg: Tuple[str, GraphQLArgument]) -> Dict[str, Any]:
    return {
        "name": __InputValue.fields["name"].resolve(arg, None),
        "description": __InputValue.fields["description"].resolve(arg, None),
        "type": _get_type_ref(__InputValue.fields["type"].resolve(arg, None)),
        "defaultValue": __InputValue.fields["defaultValue"].resolve(arg, None),
    }


def _get_field(field: Tuple[str, GraphQLField]) -> Dict[str, Any]:
    return {
        "name": __Field.fields["name"].resolve(field, None),
        "description": __Field.fields["description"].resolve(field, None),
        "args": [_get_input_value(arg) for arg in __Field.fields["args"].resolve(field, None)],
        "type": _get_type_ref(__Field.fields["type"].resolve(field, None)),
        "isDeprecated": __Field.fields["isDeprecated"].resolve(field, None),
        "deprecationReason": __Field.fields["deprecationReason"].resolve(field, None),
    }


def _get_enum_value(enum_value: Tuple[str, GraphQLEnumValue]) -> Dict[str, Any]:
    return {
        "name": __EnumValue.fields["name"].resolve(enum_value, None),
        "description": __EnumValue.fields["description"].resolve(enum_value, None),
        "isDeprecated": __EnumValue.fields["isDeprecated"].resolve(enum_value, None),
        "deprecationReason": __EnumValue.fields["deprecationReason"].resolve(enum_value, None),
    }


def _get_full_type(type_: GraphQLNamedType, schema: GraphQLSchema) -> Dict[str, Any]:
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


def execute_fast_introspection_query(schema: GraphQLSchema) -> Dict[str, Any]:
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

    return response_payload
