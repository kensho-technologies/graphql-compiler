# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple


# Complete schema information sufficient to compile GraphQL queries to SQLAlchemy
SQLAlchemySchemaInfo = namedtuple('SQLAlchemySchemaInfo', (
    'schema',  # GraphQLSchema
    'tables',  # dict mapping every graphql type in the schema to a sqlalchemy table
    'joins',   # dict mapping every graphql type in the schema to:
               #    dict mapping edge fields at that type to a dict with keys:
               #        from_column_name: string, column name in the from_table to join on
               #        to_column_name: string, column name in the to_table to join on
))
