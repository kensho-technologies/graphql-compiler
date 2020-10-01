# Copyright 2019-present Kensho Technologies, LLC.
from copy import copy
import logging
from typing import Any, Dict, List, Set, Tuple, cast

from graphql import print_ast
from graphql.language.ast import (
    ArgumentNode,
    DirectiveNode,
    DocumentNode,
    FieldNode,
    InlineFragmentNode,
    ListValueNode,
    NameNode,
    OperationDefinitionNode,
    SelectionNode,
    SelectionSetNode,
    StringValueNode,
)
from graphql.pyutils import FrozenList

from ..ast_manipulation import get_ast_field_name, get_only_query_definition
from ..compiler.helpers import get_parameter_name
from ..cost_estimation.analysis import QueryPlanningAnalysis
from ..cost_estimation.int_value_conversion import convert_field_value_to_int
from ..exceptions import GraphQLError
from ..global_utils import ASTWithParameters, PropertyPath, VertexPath
from .pagination_planning import VertexPartitionPlan


logger = logging.getLogger(__name__)


def _generate_new_name(base_name: str, taken_names: Set[str]) -> str:
    """Return a name based on the provided string that is not already taken.

    This method tries the following names: {base_name}_0, then {base_name}_1, etc.
    and returns the first one that's not in taken_names

    Args:
        base_name: The base for name construction as explained above
        taken_names: The set of names not permitted as output

    Returns:
        a name based on the base_name that is not in taken_names
    """
    index = 0
    while "{}_{}".format(base_name, index) in taken_names:
        index += 1
    return "{}_{}".format(base_name, index)


def _get_binary_filter_node_parameter(filter_directive: DirectiveNode) -> str:
    """Return the parameter name for a binary Filter Directive."""
    filter_arguments = cast(ListValueNode, filter_directive.arguments[1].value).values
    if len(filter_arguments) != 1:
        raise AssertionError(f"Expected one argument in filter {filter_directive}")

    argument_name = cast(StringValueNode, filter_arguments[0]).value
    parameter_name = get_parameter_name(argument_name)
    return parameter_name


def _get_filter_node_operation(filter_directive: DirectiveNode) -> str:
    """Return the @filter's op_name as a string."""
    return cast(StringValueNode, filter_directive.arguments[0].value).value


def _is_new_filter_stronger(
    query_analysis: QueryPlanningAnalysis,
    property_path: PropertyPath,
    operation: str,
    new_filter_value: Any,
    old_filter_value: Any,
) -> bool:
    """Return if the old filter can be omitted in the presence of the new one.

    Args:
        query_analysis: the entire query with any query analysis needed for pagination
        property_path: path to the filtered field from the query root
        operation: the operation that both filters share. One of "<" and ">=".
        new_filter_value: the value of the new filter
        old_filter_value: the value of the old filter. Must be the exact same type
                          as the value of the new filter.

    Returns:
        whether the old filter can be removed with no change in query meaning.
    """
    vertex_type = query_analysis.types[property_path.vertex_path].name
    new_int_value = convert_field_value_to_int(
        query_analysis.schema_info,
        vertex_type,
        property_path.field_name,
        new_filter_value,
    )
    old_int_value = convert_field_value_to_int(
        query_analysis.schema_info,
        vertex_type,
        property_path.field_name,
        old_filter_value,
    )

    if operation == "<":
        return new_int_value <= old_int_value
    elif operation == ">=":
        return new_int_value >= old_int_value
    else:
        raise AssertionError(f"Expected operation to be < or >=, got {operation}.")


def _are_filter_operations_equal_and_possible_to_eliminate(
    filter_operation_1: str, filter_operation_2: str
) -> bool:
    """Return True only if one of the filters is redundant."""
    if filter_operation_1 == filter_operation_2 == "<":
        return True
    if filter_operation_1 == filter_operation_2 == ">=":
        return True
    return False


def _add_pagination_filter_at_node(
    query_analysis: QueryPlanningAnalysis,
    node_vertex_path: VertexPath,
    node_ast: SelectionNode,
    pagination_field: str,
    directive_to_add: DirectiveNode,
    extended_parameters: Dict[str, Any],
) -> Tuple[SelectionNode, Dict[str, Any]]:
    """Add the filter to the target field, returning a query and its new parameters.

    Args:
        query_analysis: the entire query with any query analysis needed for pagination
        node_vertex_path: path to the node_ast from the query root
        node_ast: part of the entire query, rooted at the location where we are
                  adding a filter.
        pagination_field: field on which we are adding a filter
        directive_to_add: filter directive to add
        extended_parameters: original parameters of the query along with
                             the parameter used in directive_to_add

    Returns:
        tuple (new_ast, removed_parameters)
        new_ast: A query with the filter inserted, and any filters on the same location with
                 the same operation removed.
        new_parameters: The parameters to use with the new_ast
    """
    if not isinstance(node_ast, (FieldNode, InlineFragmentNode, OperationDefinitionNode)):
        raise AssertionError(
            f'Input AST is of type "{type(node_ast).__name__}", which should not be a selection.'
        )

    if node_ast.selection_set is None:
        raise AssertionError(
            f"Vertex field AST has no selection set at path {node_vertex_path}. "
            f"Query: {query_analysis.query_string_with_parameters}"
        )

    new_directive_operation = _get_filter_node_operation(directive_to_add)
    new_directive_parameter_name = _get_binary_filter_node_parameter(directive_to_add)
    new_directive_parameter_value = extended_parameters[new_directive_parameter_name]

    # If the field exists, add the new filter and remove redundant filters.
    new_parameters = dict(extended_parameters)
    new_selections = []
    found_field = False
    for selection_ast in node_ast.selection_set.selections:
        new_selection_ast = selection_ast
        field_name = get_ast_field_name(selection_ast)
        if field_name == pagination_field:
            found_field = True
            new_selection_ast = copy(selection_ast)
            new_selection_ast.directives = copy(selection_ast.directives)

            new_directives: List[DirectiveNode] = []
            for directive in selection_ast.directives or []:
                operation = _get_filter_node_operation(directive)
                if _are_filter_operations_equal_and_possible_to_eliminate(
                    new_directive_operation, operation
                ):
                    parameter_name = _get_binary_filter_node_parameter(directive)
                    parameter_value = new_parameters[parameter_name]
                    if not _is_new_filter_stronger(
                        query_analysis,
                        PropertyPath(node_vertex_path, pagination_field),
                        operation,
                        new_directive_parameter_value,
                        parameter_value,
                    ):
                        logger.error(
                            "Pagination filter %(new_filter)s on %(pagination_field)s with param "
                            "%(new_filter_param)s is not stronger than existing filter "
                            "%(existing_filter)s with param %(existing_param)s. This is either a "
                            "bug in parameter generation, or this assertion is outdated. "
                            "Query: %(query)s",
                            {
                                "new_filter": print_ast(directive_to_add),
                                "pagination_field": pagination_field,
                                "new_filter_param": new_directive_parameter_value,
                                "existing_filter": print_ast(directive),
                                "existing_param": parameter_value,
                                "query": query_analysis.query_string_with_parameters,
                            },
                        )
                    del new_parameters[parameter_name]
                else:
                    new_directives.append(directive)
            new_directives.append(directive_to_add)
            new_selection_ast.directives = FrozenList(new_directives)
        new_selections.append(new_selection_ast)

    # If field didn't exist, create it and add the new directive to it.
    if not found_field:
        new_selections.insert(
            0, FieldNode(name=NameNode(value=pagination_field), directives=[directive_to_add])
        )

    new_ast = copy(node_ast)
    new_ast.selection_set = SelectionSetNode(selections=new_selections)
    return new_ast, new_parameters


def _add_pagination_filter_recursively(
    query_analysis: QueryPlanningAnalysis,
    node_ast: SelectionNode,
    full_query_path: VertexPath,
    query_path: VertexPath,
    pagination_field: str,
    directive_to_add: DirectiveNode,
    extended_parameters: Dict[str, Any],
) -> Tuple[SelectionNode, Dict[str, Any]]:
    """Add the filter to the target field, returning a query and its new parameters.

    Args:
        query_analysis: the entire query with any query analysis needed for pagination
        node_ast: Part of the entire query, the location where we are adding a filter
        full_query_path: path to the pagination vertex from the root
        query_path: path to the pagination vertex from this node (node_ast)
        pagination_field: The field on which we are adding a filter
        directive_to_add: The filter directive to add
        extended_parameters: The original parameters of the query along with
                             the parameter used in directive_to_add

    Returns:
        tuple (new_ast, removed_parameters)
        new_ast: A query with the filter inserted, and any filters on the same location with
                 the same operation removed.
        new_parameters: The parameters to use with the new_ast
    """
    if not isinstance(node_ast, (FieldNode, InlineFragmentNode, OperationDefinitionNode)):
        raise AssertionError(
            f'Input AST is of type "{type(node_ast).__name__}", which should not be a selection.'
        )

    if len(query_path) == 0:
        return _add_pagination_filter_at_node(
            query_analysis,
            full_query_path,
            node_ast,
            pagination_field,
            directive_to_add,
            extended_parameters,
        )

    if node_ast.selection_set is None:
        raise AssertionError(f"Invalid query path {query_path} {node_ast}.")

    found_field = False
    new_selections = []
    for selection_ast in node_ast.selection_set.selections:
        new_selection_ast = selection_ast
        field_name = get_ast_field_name(selection_ast)
        if field_name == query_path[0]:
            found_field = True
            new_selection_ast, new_parameters = _add_pagination_filter_recursively(
                query_analysis,
                selection_ast,
                full_query_path,
                query_path[1:],
                pagination_field,
                directive_to_add,
                extended_parameters,
            )
        new_selections.append(new_selection_ast)

    if not found_field:
        raise AssertionError(f"Invalid query path {query_path} {node_ast}.")

    new_ast = copy(node_ast)
    new_ast.selection_set = SelectionSetNode(selections=new_selections)
    return new_ast, new_parameters


def _make_binary_filter_directive_node(op_name: str, param_name: str) -> DirectiveNode:
    """Make a binary filter directive node with the given binary op_name and parameter name."""
    return DirectiveNode(
        name=NameNode(value="filter"),
        arguments=[
            ArgumentNode(
                name=NameNode(value="op_name"),
                value=StringValueNode(value=op_name),
            ),
            ArgumentNode(
                name=NameNode(value="value"),
                value=ListValueNode(values=[StringValueNode(value="$" + param_name)]),
            ),
        ],
    )


def generate_parameterized_queries(
    query_analysis: QueryPlanningAnalysis,
    vertex_partition: VertexPartitionPlan,
    parameter_value: Any,
) -> Tuple[ASTWithParameters, ASTWithParameters]:
    """Generate two parameterized queries that can be used to paginate over a given query.

    The first query is produced by adding a "<" filter to a field in the original, and the
    second by adding a ">=" filter. The parameter value given is used in this filter. This
    function will potentially remove any existing filters that are no longer needed after
    the new filter is inserted.

    If the parameter_value is set such that the newly produced query is equivalent to the
    original query, an AssertionError is raised. Therefore, the parameter_value should be
    a value inside the range of initial possible values for that field.

    Args:
        query_analysis: the query with any query analysis needed for pagination
        vertex_partition: pagination plan dictating where to insert the filter
        parameter_value: the value of the parameter used for pagination

    Returns:
        tuple (next_page, remainder)
        next_page: AST and params for next page.
        remainder: AST and params for the remainder query that returns all results
                   not on the next page.
    """
    query = query_analysis.ast_with_parameters
    query_root = get_only_query_definition(query.query_ast, GraphQLError)

    # Create extended parameters that include the pagination parameter value
    param_name = _generate_new_name("__paged_param", set(query.parameters.keys()))
    extended_parameters = dict(query.parameters)
    extended_parameters[param_name] = parameter_value

    next_page_root, next_page_parameters = _add_pagination_filter_recursively(
        query_analysis,
        query_root,
        vertex_partition.query_path,
        vertex_partition.query_path,
        vertex_partition.pagination_field,
        _make_binary_filter_directive_node("<", param_name),
        extended_parameters,
    )
    remainder_root, remainder_parameters = _add_pagination_filter_recursively(
        query_analysis,
        query_root,
        vertex_partition.query_path,
        vertex_partition.query_path,
        vertex_partition.pagination_field,
        _make_binary_filter_directive_node(">=", param_name),
        extended_parameters,
    )

    next_page = ASTWithParameters(DocumentNode(definitions=[next_page_root]), next_page_parameters)
    remainder = ASTWithParameters(DocumentNode(definitions=[remainder_root]), remainder_parameters)
    return next_page, remainder
