

def run_sql_query(engine, compilation_result, parameters):
    """Run a sqlalchemy query (with no retries )and format the result as a list of dicts."""
    return [dict(row) for row in engine.execute(compilation_result.query, parameters)]
