from graphql_compiler import get_sqlalchemy_schema_info, graphql_to_sql
from sqlalchemy import MetaData, create_engine

engine = create_engine('<connection string>')

# Reflect the default database schema.
metadata = MetaData(bind=engine)
metadata.reflect()

# Wrap the schema information into a SQLAlchemySchemaInfo object.
sql_schema_info = get_sqlalchemy_schema_info(metadata.tables, {}, engine.dialect)

# Write GraphQL query.
graphql_query = '''
{
    Animal {
        name @output(out_name: "animal_name")
    }
}
'''
parameters = {}

# Compile and execute query.
compilation_result = graphql_to_sql(sql_schema_info, graphql_query, parameters)
query_results = [dict(row) for row in engine.execute(compilation_result.query)]
