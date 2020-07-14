# Copyright 2017-present Kensho Technologies, LLC.
import unittest

from graphql import get_introspection_query, graphql_sync

from ..fast_introspection import execute_fast_introspection_query
from .test_helpers import get_schema


graphiql_introspection_query = """
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


_whitespace_free_introspection_query = _remove_whitespace_from_query(graphiql_introspection_query)


class FastIntrospectionTests(unittest.TestCase):
    def test_graphql_get_introspection_query(self) -> None:
        self.assertEqual(
            _whitespace_free_introspection_query,
            _remove_whitespace_from_query(get_introspection_query()),
        )

    def test_fast_introspection_equal_graphql_sync(self) -> None:
        schema = get_schema()
        self.assertEqual(
            graphql_sync(schema, graphiql_introspection_query).data,
            execute_fast_introspection_query(schema),
        )
