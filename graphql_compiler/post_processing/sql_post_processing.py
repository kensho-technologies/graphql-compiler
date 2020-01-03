# Copyright 2019-present Kensho Technologies, LLC.
import html
import re
from typing import Any, Dict, List, Optional, Sequence

from graphql import GraphQLScalarType

from graphql_compiler.compiler import blocks, expressions

from ..backend import sql_backend
from ..compiler.compiler_frontend import graphql_to_ir
from ..schema.schema_info import SQLAlchemySchemaInfo


def _mssql_xml_path_string_to_list(
    xml_path_result: str, list_entry_type: GraphQLScalarType
) -> List[Any]:
    """Convert the string result produced with XML PATH for MSSQL folds to a list.

    Args:
        xml_path_result: str, result from an XML PATH folded output
        list_entry_type: GraphQLScalarType, type the results should be output as

    Returns:
        list representation of the result with all XML and GraphQL Compiler escaping reversed
    """
    # Return an empty list if the XML PATH result is "".
    if xml_path_result == "":
        return []

    # Split the XML path result on "|".
    list_result: Sequence[Optional[str]] = xml_path_result.split("|")

    # Convert "~" to None.
    list_result = [None if result == "~" else result for result in list_result]

    # Convert "^d" to "|".
    list_result = [
        result.replace("^d", "|") if result is not None else None for result in list_result
    ]

    # Convert "^n" to "~".
    list_result = [
        result.replace("^n", "~") if result is not None else None for result in list_result
    ]

    # Convert "^e" to "^".
    list_result = [
        result.replace("^e", "^") if result is not None else None for result in list_result
    ]

    # Convert "&#x{2 digit HEX};" to unicode character.
    new_list_result: List[Optional[str]] = []
    for result in list_result:
        if result is not None:
            split_result = re.split("&#x([A-Fa-f0-9][A-Fa-f0-9]);", result)
            new_result = split_result[0]
            for hex_value, next_substring in zip(split_result[1::2], split_result[2::2]):
                new_result += chr(int(hex_value, 16)) + next_substring
            new_list_result.append(new_result)
        else:
            new_list_result.append(None)

    # Convert "&amp;" to "&", "&gt;" to ">", "&lt;" to "<".
    list_result = [
        html.unescape(result) if result is not None else None for result in new_list_result
    ]

    # Convert to the appropriate return type.
    list_result_to_return: List[Optional[Any]] = [
        list_entry_type.parse_value(result) if result is not None else None
        for result in list_result
    ]

    return list_result_to_return


def post_process_mssql_folds(
    schema_info: SQLAlchemySchemaInfo, graphql_query: str, query_results: Dict[str, Any]
) -> None:
    r"""Convert XML PATH fold results from a string to a list of the appropriate type.

    See _get_xml_path_clause in graphql_compiler/compiler/emit_sql.py for an in-depth description
    of the encoding process.

    Post-processing steps:
        1. split on "|",
        2. convert "~" to None
        3. convert caret escaped characters (excluding "^" itself)
            i.e. "^d" (delimiter) to "|" and "^n" (null) to "~"
        4. with caret escaped characters removed, convert "^e" to "^"
        5. convert ampersand escaped characters (excluding "&" itself)
            i.e. "&gt;" to ">", "&lt;" to "<" and "&#xHEX;" to "\xHEX"
        6. with ampersand escaped characters removed, convert "&amp;" to "&"

    Args:
        schema_info: SQLAlchemySchemaInfo, schema the query was run on
        graphql_query: str, a GraphQL query
        query_results: Dict[str, Any], results from graphql_query being run with schema_info,
                       mutated in place

    """
    # Get the internal representation of the query.
    ir_and_metadata = graphql_to_ir(
        schema_info.schema,
        graphql_query,
        type_equivalence_hints=schema_info.type_equivalence_hints,
    )
    lowered_ir_blocks = sql_backend.lower_func(schema_info, ir_and_metadata)

    # Loop through ir_blocks; for all ConstructResult for FoldedContextFields, look up string result
    # in query_results and update to a list.
    for block in lowered_ir_blocks.ir_blocks:
        if isinstance(block, blocks.ConstructResult):
            for out_name, expression in block.fields.items():
                if isinstance(expression, expressions.FoldedContextField):
                    xml_path_result = query_results[out_name]
                    list_result = _mssql_xml_path_string_to_list(
                        xml_path_result, expression.field_type.of_type
                    )
                    query_results[out_name] = list_result
