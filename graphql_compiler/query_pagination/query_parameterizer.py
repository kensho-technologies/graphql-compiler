# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple


def generate_parameterized_queries(schema_info, query_ast, parameters, vertex_partition):
    """Execute the VertexPartitionPlan by splitting the query_ast into two ASTs.

    In order to paginate arbitrary GraphQL queries, additional filters may need to be added to be
    able to limit the number of results in the original query. This function creates two new queries
    with additional filters stored as PaginationFilters with which the query result size can be
    controlled.

    Args:
        schema_info: QueryPlanningSchemaInfo
        query_ast: Document, query that is being paginated.
        parameters: dict, list of parameters for the given query.
        vertex_partition: VertexPartitionPlan

    Returns:
        - ast of the next page query
        - ast of the remainder query
        - the name of the filter parameter used to split the ast
    """
    raise NotImplementedError()
