# Copyright 2021-present Kensho Technologies, LLC.
from typing import Any, Callable, ContextManager, Dict, Iterable, Mapping

from ..post_processing.sql_post_processing import post_process_mssql_folds
from ..query_formatting.common import deserialize_multiple_arguments
from .typedefs import QueryExecutionFunc, SimpleExecute


def _execute_simple_execute_node(
    provider_client_makers: Dict[str, Callable[[], ContextManager[QueryExecutionFunc]]],
    query_plan_node: SimpleExecute,
) -> Iterable[Mapping[str, Any]]:
    """Execute a SimpleExecute."""
    provider_client_maker = provider_client_makers[query_plan_node.provider_id]
    arguments = deserialize_multiple_arguments(
        query_plan_node.arguments, query_plan_node.input_metadata
    )

    with provider_client_maker() as query_client:
        result = query_client(query_plan_node.query, query_plan_node.input_metadata, arguments)
        # Apply post processing for MSSQL folds if applicable.
        requires_postprocessing = False
        for _, output_metadata in query_plan_node.output_metadata.items():
            if (
                output_metadata.provider_metadata is not None
                and output_metadata.provider_metadata.requires_fold_postprocessing
            ):
                requires_postprocessing = True
        if requires_postprocessing:
            list_dict_result = [dict(entry) for entry in result]
            post_process_mssql_folds(list_dict_result, query_plan_node.output_metadata)
            return list_dict_result

        # Otherwise, return result as is.
        return result
