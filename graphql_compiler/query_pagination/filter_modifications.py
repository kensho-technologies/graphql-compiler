# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import copy

from graphql.language.ast import (
    Argument, Directive, Field, InlineFragment, ListValue, Name, OperationDefinition, SelectionSet,
    StringValue
)
import six

from graphql_compiler.ast_manipulation import get_only_query_definition, get_only_selection_from_ast
from graphql_compiler.compiler.helpers import get_parameter_name
from graphql_compiler.exceptions import GraphQLError
from graphql_compiler.schema import FilterDirective


RESERVED_PARAMETER_PREFIX = '__paged_'

# FilterModification namedtuples document pagination filters that will be added or modified in the
# given query. They contain all the information of a PaginationFilter, but are designed for storing
# the information of what needs to be modified in a given query to obtain the next page query and
# the remainder query.
FilterModification = namedtuple(
    'FilterModification',
    (
        'vertex',                   # Document, AST of the vertex instance in the query having its
                                    # filters modified.
        'property_field',           # str, name of the property field being filtered.
        'next_page_query_filter',   # Directive, '<' filter directive that will be used to generate
                                    # the next page query.
        'remainder_query_filter',   # Directive, '>=' filter directive that will be used to generate
                                    # the remainder query. This filter may
    )
)


def _get_binary_filter_parameter(filter_directive):
    """Return the parameter name for a binary Filter Directive."""
    filter_arguments = filter_directive.arguments[1].value.values
    if len(filter_arguments) != 1:
        raise AssertionError(u'Expected one argument in filter {}'.format(filter_directive))

    argument_name = filter_arguments[0].value
    parameter_name = get_parameter_name(argument_name)
    return parameter_name


def _get_filter_operation(filter_directive):
    """Return the @filter's op_name as a string."""
    return filter_directive.arguments[0].value.value


def _create_field(field_name):
    """Return a property field with the given name."""
    property_field = Field(
        alias=None, name=Name(value=field_name),
        arguments=[], directives=[], selection_set=None,
    )

    return property_field


def _create_binary_filter_directive(filter_operation, filter_parameter):
    """Create a FilterDirective with the given binary filter and argument name."""
    binary_inequality_filters = ['>', '<', '>=', '<=']
    if filter_operation not in binary_inequality_filters:
        raise AssertionError(u'Could not create a filter for pagination with op_name as {}.'
                             u' Currently, only {} are supported.'
                             .format(filter_operation, binary_inequality_filters))

    filter_ast = Directive(
        name=Name(value=FilterDirective.name),
        arguments=[
            Argument(
                name=Name(value='op_name'),
                value=StringValue(value=filter_operation),
            ),
            Argument(
                name=Name(value='value'),
                value=ListValue(
                    values=[
                        StringValue(value=u'$' + filter_parameter),
                    ],
                ),
            ),
        ],
    )

    return filter_ast


def _get_primary_key_name(schema_graph, vertex_class):
    """Return the name of the primary key field for a given vertex class."""
    # HACK(vlad): Currently, information about the primary key is not stored in the SchemaGraph, so
    #             the primary key is assumed to be 'uuid'.
    return 'uuid'


def _find_filter_containing_op_name(field, filter_operation):
    """Return FilterDirective containing the given operation as its op_name argument."""
    if field is None or field.directives is None:
        return None

    for directive in field.directives:
        if directive.name.value == 'filter' and _get_filter_operation(directive) == '<':
            return directive

    return None


def _find_unused_parameter_names_for_pagination(parameters):
    """Return unused parameter names for lower and upper bound pagination parameters."""
    # Since there are only len(parameters) defined parameter names, by the pigeonhole principle,
    # we're certain we will find two unused pagination parameters after len(parameters) + 1
    # attempts.
    parameter_naming_attempts = len(parameters) + 1
    for index in range(parameter_naming_attempts):
        paged_lower_param = RESERVED_PARAMETER_PREFIX + 'lower_bound_{}'.format(index)
        paged_upper_param = RESERVED_PARAMETER_PREFIX + 'upper_bound_{}'.format(index)

        if (
            paged_lower_param not in parameters.keys() and
            paged_upper_param not in parameters.keys()
        ):
            return paged_lower_param, paged_upper_param

    raise AssertionError(u'Could not find unused parameter names after {} tries: {}'
                         .format(parameter_naming_attempts, parameters))


def _create_filters_for_pagination(parameters):
    """Create two filters for pagination, one of type '>=', and another of type '<'."""
    lower_bound_parameter, upper_bound_parameter = _find_unused_parameter_names_for_pagination(
        parameters
    )

    next_page_query_filter = _create_binary_filter_directive('<', upper_bound_parameter)
    remainder_query_filter = _create_binary_filter_directive('>=', lower_bound_parameter)
    return next_page_query_filter, remainder_query_filter


def _get_nodes_for_pagination(statistics, query_ast):
    """Return a list of nodes usable for pagination belonging to the given AST node."""
    definition_ast = get_only_query_definition(query_ast, GraphQLError)
    root_node = get_only_selection_from_ast(definition_ast, GraphQLError)

    # TODO(vlad): Return a better selection of nodes for pagination, as paginating over the root
    #             node doesn't create good pages in practice.
    return [root_node]


def _get_modifications_needed_to_vertex_for_paging(schema_graph, vertex, parameters):
    """Return modifications needed to the given query to page over the given vertex.

    Args:
        schema_graph: SchemaGraph instance.
        vertex: Document, AST of the node for which filter modifications are being generated.
        parameters: dict, parameters with which a query will be executed.

    Returns:
        FilterModification namedtuple describing modifications to the given vertex's directive
        list for pagination.
    """
    vertex_class = vertex.name.value
    property_field_name = _get_primary_key_name(schema_graph, vertex_class)

    existing_filter_usable_for_next_page_query = _find_filter_containing_op_name(field, '<')
    existing_filter_usable_for_remainder_query = _find_filter_containing_op_name(field, '>=')
    next_page_created_filter, remainder_created_filter = _create_filters_for_pagination(parameters)

    # If there's already a '<' or '>=' filter, we use that for paginating over this vertex.
    next_page_query_filter = existing_filter_usable_for_next_page_query or next_page_created_filter
    remainder_query_filter = existing_filter_usable_for_remainder_query or remainder_created_filter

    filter_modification = FilterModification(
        vertex, property_field_name, next_page_query_filter, remainder_query_filter
    )
    return filter_modification


def get_modifications_for_pagination(schema_graph, statistics, query_ast, parameters):
    """Return FilterModification namedtuples for parameterizing and paging the given query.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_ast: Document, AST of the GraphQL query that will be split.
        parameters: dict, parameters with which query will be estimated.

    Returns:
        List[FilterModification], changes to be done to the query to allow pagination over the given
        query.
    """
    pagination_vertices = _get_nodes_for_pagination(statistics, query_ast)
    if len(pagination_vertices) != 1:
        raise AssertionError(u'Found more than one element in pagination vertices list {}.'
                             u' Currently, only one pagination vertex is allowed: {} {}'
                             .format(pagination_vertices, query_ast, parameters))
    vertex = pagination_vertices[0]

    filter_modifications = _get_modifications_needed_to_vertex_for_paging(
        schema_graph, vertex, parameters
    )
    return [filter_modifications]
