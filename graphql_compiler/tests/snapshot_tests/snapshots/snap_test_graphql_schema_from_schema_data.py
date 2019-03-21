# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots['GraphQLSchemaGenerationTests::test_graphql_schema_generation_from_schema_data_api 1'] = '''schema {
  query: RootSchemaQuery
}

directive @filter(op_name: String!, value: [String!]!) on FIELD | INLINE_FRAGMENT

directive @tag(tag_name: String!) on FIELD

directive @output(out_name: String!) on FIELD

directive @output_source on FIELD

directive @optional on FIELD

directive @recurse(depth: Int!) on FIELD

directive @fold on FIELD

scalar Decimal

interface Entity {
  _x_count: Int
  name: String
}

type Location implements Entity {
  _x_count: Int
  description: String
  in_Person_LivesIn: [Person]
  name: String
}

type Person implements Entity {
  _x_count: Int
  alias: [String]
  name: String
  net_worth: Decimal
  out_Person_LivesIn: [Location]
}

type RootSchemaQuery {
  Entity: Entity
  Location: Location
  Person: Person
}
'''
