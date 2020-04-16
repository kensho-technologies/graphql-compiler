# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import copy

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
    SelectionSetNode,
    StringValueNode,
)

from ..ast_manipulation import get_only_query_definition
from ..exceptions import GraphQLValidationError
from ..schema import FilterDirective, OutputDirective


SubQueryPlan = namedtuple(
    "SubQueryPlan",
    (
        "query_ast",  # Document, representing a piece of the overall query with directives added
        "schema_id",  # str, identifying the schema that this query piece targets
        "parent_query_plan",  # SubQueryPlan, the query that the current query depends on
        "child_query_plans",  # List[SubQueryPlan], the queries that depend on the current query
    ),
)


OutputJoinDescriptor = namedtuple(
    "OutputJoinDescriptor",
    (
        "output_names",  # Tuple[str, str], (parent output name, child output name)
        # May be expanded to have more attributes, e.g. is_optional, describing how the join
        # should be made
    ),
)


QueryPlanDescriptor = namedtuple(
    "QueryPlanDescriptor",
    (
        "root_sub_query_plan",  # SubQueryPlan
        "intermediate_output_names",  # frozenset[str], names of outputs to be removed at the end
        "output_join_descriptors",
        # List[OutputJoinDescriptor], describing which outputs should be joined and how
    ),
)


def make_query_plan(root_sub_query_node, intermediate_output_names):
    """Return a QueryPlanDescriptor, whose query ASTs have @filters added.

    For each parent of parent and child SubQueryNodes, a new @filter directive will be added
    in the child AST. It will be added on the field whose @output directive has the out_name
    equal to the child's out name as specified in the QueryConnection. The newly added @filter
    will be a 'in_collection' type filter, and the name of the local variable is guaranteed to
    be the same as the out_name of the @output on the parent.

    ASTs contained in the input node and its children nodes will not be modified.

    Args:
        root_sub_query_node: SubQueryNode, representing the base of a query split into pieces
                             that we want to turn into a query plan
        intermediate_output_names: frozenset[str], names of outputs to be removed at the end

    Returns:
        QueryPlanDescriptor namedtuple, containing a tree of SubQueryPlans that wrap
        around each individual query AST, the set of intermediate output names that are
        to be removed at the end, and information on which outputs are to be connect to which
        in what manner
    """
    output_join_descriptors = []

    root_sub_query_plan = SubQueryPlan(
        query_ast=root_sub_query_node.query_ast,
        schema_id=root_sub_query_node.schema_id,
        parent_query_plan=None,
        child_query_plans=[],
    )

    _make_query_plan_recursive(root_sub_query_node, root_sub_query_plan, output_join_descriptors)

    return QueryPlanDescriptor(
        root_sub_query_plan=root_sub_query_plan,
        intermediate_output_names=intermediate_output_names,
        output_join_descriptors=output_join_descriptors,
    )


def _make_query_plan_recursive(sub_query_node, sub_query_plan, output_join_descriptors):
    """Recursively copy the structure of sub_query_node onto sub_query_plan.

    For each child connection contained in sub_query_node, create a new SubQueryPlan for
    the corresponding child SubQueryNode, add appropriate @filter directive to the child AST,
    and attach the new SubQueryPlan to the list of children of the input sub-query plan.

    Args:
        sub_query_node: SubQueryNode, whose descendents are copied over onto sub_query_plan.
                        It is not modified by this function
        sub_query_plan: SubQueryPlan, whose list of child query plans and query AST are
                        modified
        output_join_descriptors: List[OutputJoinDescriptor], describing which outputs should be
                                 joined and how

    """
    # Iterate through child connections of query node
    for child_query_connection in sub_query_node.child_query_connections:
        child_sub_query_node = child_query_connection.sink_query_node
        parent_out_name = child_query_connection.source_field_out_name
        child_out_name = child_query_connection.sink_field_out_name

        child_query_type = get_only_query_definition(
            child_sub_query_node.query_ast, GraphQLValidationError
        )
        child_query_type_with_filter = _add_filter_at_field_with_output(
            child_query_type,
            child_out_name,
            parent_out_name
            # @filter's local variable is named the same as the out_name of the parent's @output
        )
        if child_query_type is child_query_type_with_filter:
            raise AssertionError(
                'An @output directive with out_name "{}" is unexpectedly not found in the '
                'AST "{}".'.format(child_out_name, child_query_type)
            )
        else:
            new_child_query_ast = DocumentNode(definitions=[child_query_type_with_filter])

        # Create new SubQueryPlan for child
        child_sub_query_plan = SubQueryPlan(
            query_ast=new_child_query_ast,
            schema_id=child_sub_query_node.schema_id,
            parent_query_plan=sub_query_plan,
            child_query_plans=[],
        )

        # Add new SubQueryPlan to parent's child list
        sub_query_plan.child_query_plans.append(child_sub_query_plan)

        # Add information about this edge
        new_output_join_descriptor = OutputJoinDescriptor(
            output_names=(parent_out_name, child_out_name),
        )
        output_join_descriptors.append(new_output_join_descriptor)

        # Recursively repeat on child SubQueryPlans
        _make_query_plan_recursive(
            child_sub_query_node, child_sub_query_plan, output_join_descriptors
        )


def _add_filter_at_field_with_output(ast, field_out_name, input_filter_name):
    """Return an AST with @filter added at the field with the specified @output, if found.

    Args:
        ast: Field, InlineFragment, or OperationDefinition, an AST Node type that occurs in
             the selections of a SelectionSet. It is not modified by this function
        field_out_name: str, the out_name of an @output directive. This function will create
                        a new @filter directive on the field that has an @output directive
                        with this out_name
        input_filter_name: str, the name of the local variable in the new @filter directive
                           created

    Returns:
        Field, InlineFragment, or OperationDefinition, identical to the input ast except
        with an @filter added at the specified field if such a field is found. If no changes
        were made, this is the same object as the input
    """
    if not isinstance(ast, (FieldNode, InlineFragmentNode, OperationDefinitionNode)):
        raise AssertionError(
            'Input AST is of type "{}", which should not be a selection.'
            "".format(type(ast).__name__)
        )

    if isinstance(ast, FieldNode):
        # Check whether this field has the expected directive, if so, modify and return
        if ast.directives is not None and any(
            _is_output_directive_with_name(directive, field_out_name)
            for directive in ast.directives
        ):
            new_directives = list(ast.directives)
            new_directives.append(_get_in_collection_filter_directive(input_filter_name))
            new_ast = copy(ast)
            new_ast.directives = new_directives
            return new_ast

    if ast.selection_set is None:  # Nothing to recurse on
        return ast

    # Otherwise, recurse and look for field with desired out_name
    made_changes = False
    new_selections = []
    for selection in ast.selection_set.selections:
        new_selection = _add_filter_at_field_with_output(
            selection, field_out_name, input_filter_name
        )
        if new_selection is not selection:  # Changes made somewhere down the line
            if not made_changes:
                made_changes = True
            else:
                # Change has already been made, but there is a new change. Implies that multiple
                # fields have the @output directive with the desired name
                raise GraphQLValidationError(
                    'There are multiple @output directives with the out_name "{}"'.format(
                        field_out_name
                    )
                )
        new_selections.append(new_selection)

    if made_changes:
        new_ast = copy(ast)
        new_ast.selection_set = SelectionSetNode(selections=new_selections)
        return new_ast
    else:
        return ast


def _is_output_directive_with_name(directive, out_name):
    """Return whether or not the input is an @output directive with the desired out_name."""
    if not isinstance(directive, DirectiveNode):
        raise AssertionError('Input "{}" is not a directive.'.format(directive))
    return (
        directive.name.value == OutputDirective.name
        and directive.arguments[0].value.value == out_name
    )


def _get_in_collection_filter_directive(input_filter_name):
    """Create a @filter directive with in_collecion operation and the desired variable name."""
    return DirectiveNode(
        name=NameNode(value=FilterDirective.name),
        arguments=[
            ArgumentNode(
                name=NameNode(value="op_name"), value=StringValueNode(value="in_collection"),
            ),
            ArgumentNode(
                name=NameNode(value="value"),
                value=ListValueNode(values=[StringValueNode(value="$" + input_filter_name),],),
            ),
        ],
    )


def print_query_plan(query_plan_descriptor, indentation_depth=4):
    """Return a string describing query plan."""
    query_plan_strings = [""]
    plan_and_depth = _get_plan_and_depth_in_dfs_order(query_plan_descriptor.root_sub_query_plan)

    for query_plan, depth in plan_and_depth:
        line_separation = "\n" + " " * indentation_depth * depth
        query_plan_strings.append(line_separation)

        query_str = 'Execute in schema named "{}":\n'.format(query_plan.schema_id)
        query_str += print_ast(query_plan.query_ast)
        query_str = query_str.replace("\n", line_separation)
        query_plan_strings.append(query_str)

    query_plan_strings.append("\n\nJoin together outputs as follows: ")
    query_plan_strings.append(str(query_plan_descriptor.output_join_descriptors))
    query_plan_strings.append("\n\nRemove the following outputs at the end: ")
    query_plan_strings.append(str(query_plan_descriptor.intermediate_output_names) + "\n")

    return "".join(query_plan_strings)


def _get_plan_and_depth_in_dfs_order(query_plan):
    """Return a list of topologically sorted (query plan, depth) tuples."""

    def _get_plan_and_depth_in_dfs_order_helper(query_plan, depth):
        plan_and_depth_in_dfs_order = [(query_plan, depth)]
        for child_query_plan in query_plan.child_query_plans:
            plan_and_depth_in_dfs_order.extend(
                _get_plan_and_depth_in_dfs_order_helper(child_query_plan, depth + 1)
            )
        return plan_and_depth_in_dfs_order

    return _get_plan_and_depth_in_dfs_order_helper(query_plan, 0)
