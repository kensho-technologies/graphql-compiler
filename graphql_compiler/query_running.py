

def run_sql_query(engine, compilation_result, parameters):
    return [dict(row) for row in engine.execute(compilation_result.query, parameters)]
