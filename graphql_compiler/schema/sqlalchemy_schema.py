# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple


# Complete schema information sufficient to compile GraphQL queries to SQLAlchemy
#
# It describes the tables that correspond to each type, and gives instructions on how
# to perform joins for each vertex field. The property fields on each type are implicitly
# mapped to columns with the same name on the corresponding table.
SQLAlchemySchemaInfo = namedtuple('SQLAlchemySchemaInfo', (
    'schema',  # GraphQLSchema
    'tables',  # dict mapping every graphql type name in the schema to a sqlalchemy table
    'joins',   # dict mapping every graphql type name in the schema to:
               #    dict mapping every vertex field name at that type to a dict with keys:
               #        from_column_name: string, column name to join from
               #        to_column_name: string, column name to join to
))
