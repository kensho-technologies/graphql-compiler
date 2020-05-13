# Copyright 2019-present Kensho Technologies, LLC.
import html
import re
from typing import Any, Dict, List, Optional, Sequence

from graphql import GraphQLList, GraphQLScalarType

from ..compiler.compiler_frontend import OutputMetadata
from ..deserialization import deserialize_scalar_value


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

    # Some of the special characters involved in XML path array aggregation.
    delimiter = "|"
    null = "~"

    # Remove the "|" from the first result in the string representation of the list.
    if xml_path_result[0] != delimiter:
        raise AssertionError(
            f"Unexpected fold result. All XML path array aggregated lists must start with a "
            f"'{delimiter}'. Received a result beginning with '{xml_path_result[0]}': "
            f"{xml_path_result}"
        )
    xml_path_result = xml_path_result[1:]

    # Split the XML path result on "|".
    list_result: Sequence[Optional[str]] = xml_path_result.split(delimiter)

    # Convert "~" to None. Note that this must be done before "^n" -> "~".
    list_result = [None if result == null else result for result in list_result]

    # Convert "^d" to "|".
    list_result = [
        result.replace("^d", delimiter) if result is not None else None for result in list_result
    ]

    # Convert "^n" to "~".
    list_result = [
        result.replace("^n", null) if result is not None else None for result in list_result
    ]

    # Convert "^e" to "^". Note that this must be done after the caret escaped characters i.e.
    # after "^n" -> "~" and "^d" -> "|".
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

    # Convert "&amp;" to "&", "&gt;" to ">", "&lt;" to "<". Note that the ampersand conversion
    # must be done after the ampersand escaped HEX values.
    list_result = [
        html.unescape(result) if result is not None else None for result in new_list_result
    ]

    # Convert to the appropriate return type.
    list_result_to_return: List[Optional[Any]] = [
        deserialize_scalar_value(list_entry_type, result) if result is not None else None
        for result in list_result
    ]

    return list_result_to_return


def post_process_mssql_folds(
    query_results: List[Dict[str, Any]], output_metadata: Dict[str, OutputMetadata]
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
        query_results: Dict[str, Any], results from graphql_query being run with schema_info,
                       mutated in place
        output_metadata: Dict[str, OutputMetadata], mapping output name to output metadata with
                         information about whether this output is from a fold scope

    """
    for out_name, metadata in output_metadata.items():
        # If this output is folded and has type GraphQLList (i.e. it is not an _x_count),
        # post-process the result to list form.
        if metadata.folded and isinstance(metadata.type, GraphQLList):
            for query_result in query_results:
                xml_path_result = query_result[out_name]
                list_result = _mssql_xml_path_string_to_list(xml_path_result, metadata.type.of_type)
                query_result[out_name] = list_result
