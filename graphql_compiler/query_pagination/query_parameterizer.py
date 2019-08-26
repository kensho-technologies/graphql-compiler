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

# ParameterizedPaginationQueries namedtuple, describing two query ASTs that have PaginationFilters
# describing filters with which the query result size can be controlled. Note that these filters are
# returned parameterized i.e. values for the filters' parameters have yet to be generated.
# Additionally, a dict containing user-defined parameters is stored. Since this function may modify
# the user parameters to ensure better pagination, the user_parameters dict may differ from the
# original query's parameters that were provided to the paginator.
ParameterizedPaginationQueries = namedtuple(
    'ParameterizedPaginationQueries',
    (
        'next_page_query',          # Document, AST of query that will return the next page of
                                    # results when combined with pagination parameters.
        'remainder_query',          # Document, AST of query that will return the remainder of
                                    # results when combined with pagination parameters.
        'pagination_filters',       # List[PaginationFilter], filters usable for pagination.
        'user_parameters',          # dict, parameters that the user has defined for other filters.
    ),
)

# PaginationFilter namedtuples document filters usable for pagination purposes within the larger
# context of a ParameterizedPaginationQueries namedtuple. These filters may either be added by the
# query parameterizer, or filters that the user has added whose parameter values may be modified for
# generating paginated queries.
PaginationFilter = namedtuple(
    'PaginationFilter',
    (
        'vertex_class',                 # str, vertex class to which the property field belongs to.
                                        # The given AST instance must be a vertex instance inside
                                        # the original query being paginated, as this field is
                                        # compared using referential equality.

        'property_field',               # str, name of the property field being filtered.

        'next_page_query_filter',       # Directive, filter directive with '<' operator usable
                                        # for pagination in the page query.

        'remainder_query_filter',       # Directive, filter directive with '>=' operator usable
                                        # for pagination in the remainder query.

        'related_filters',              # List[Directive], filter directives that share the same
                                        # vertex and property field as the next_page_query_filter,
                                        # and are used to generate more accurate pages.
    ),
)

# FilterModification namedtuples document pagination filters that will be added or modified in the
# given query. They contain all the information of a PaginationFilter, but are designed for storing
# the information of what needs to be modified in a given query to obtain the next page query and
# the remainder query.
FilterModification = namedtuple(
    'FilterModification',
    (
        'vertex',                       # Document, AST of the vertex instance in the query having
                                        # its filters modified.
        'property_field',               # str, name of the property field being filtered.

        'next_page_query_filter_old',   # Directive or None, '<' filter directive already present in
                                        # the given query that will be replaced with the new
                                        # next page query filter.

        'next_page_query_filter_new',   # Directive, '<' filter directive that will either replace
                                        # the old next page query filter. If the old next page query
                                        # filter has value None, then this filter will instead be
                                        # added to the filter directives list.

        'remainder_query_filter_old',   # Directive or None, '<' filter directive already present in
                                        # the given query that will be replaced with the new
                                        # remainder query filter.

        'remainder_query_filter_new',   # Directive, '<' filter directive that will either replace
                                        # the old remainder query filter. If the old remainder query
                                        # filter has value None, then this filter will instead be
                                        # added to the filter directives list.
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


def _get_field_with_name(ast, primary_key_field_name):
    """Return the primary key field for a given AST node, creating the property field if needed."""
    if ast.selection_set is None:
        return None

    selections_list = ast.selection_set.selections
    for selection in selections_list:
        if selection.name.value == primary_key_field_name:
            return selection

    return None


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
    """Stuff!"""
    # HACK(vlad): Currently, information about the primary key is not stored in the Schema Graph, so
    #             the primary key is assumed to be 'uuid'.
    return 'uuid'


def _get_nodes_for_pagination(statistics, query_ast):
    """Return a list of nodes usable for pagination belonging to the given AST node."""
    definition_ast = get_only_query_definition(query_ast, GraphQLError)
    root_node = get_only_selection_from_ast(definition_ast, GraphQLError)

    # TODO(vlad): Return a better selection of nodes for pagination, as paginating over the root
    #             node doesn't create good pages in practice.
    return [root_node]


def _create_filters_for_pagination(parameter_index, parameters):
    """Create two filters used for pagination, one of type '>=', and another of type '<'."""
    paged_lower_param = RESERVED_PARAMETER_PREFIX + 'lower_bound_{}'.format(parameter_index)
    paged_upper_param = RESERVED_PARAMETER_PREFIX + 'upper_bound_{}'.format(parameter_index)
    if paged_lower_param in parameters.keys() or paged_upper_param in parameters.keys():
        raise AssertionError(
            u'Parameter list {} already contains at least one of {} {},'
            u' which is reserved for pagination. This might also'
            u' occur if names for pagination parameters are'
            u' incorrectly generated'.format(parameters, paged_lower_param, paged_upper_param))

    next_page_query_filter_directive = _create_binary_filter_directive('<', paged_lower_param)
    remainder_query_filter_directive = _create_binary_filter_directive('>=', paged_upper_param)
    return next_page_query_filter_directive, remainder_query_filter_directive


def _add_next_page_filters_to_directives(directives_list, filter_modification):
    """Return a directives list with the next page filter added."""
    made_changes = False
    new_directives_list = []
    for directive in directives_list:
        if directive is filter_modification.next_page_query_filter_old:
            new_directives_list.append(filter_modification.next_page_query_filter_new)
            made_changes = True
        else:
            new_directives_list.append(directive)

    if filter_modification.next_page_query_filter_old is None:
        new_directives_list.append(filter_modification.next_page_query_filter_new)
        made_changes = True

    if made_changes:
        return new_directives_list
    else:
        return directives_list


def _add_remainder_filters_to_directives(directives_list, filter_modification):
    """Return a directives list with the remainder filter added."""
    made_changes = False
    new_directives_list = []
    for directive in directives_list:
        if directive is filter_modification.remainder_query_filter_old:
            new_directives_list.append(filter_modification.remainder_query_filter_new)
            made_changes = True
        else:
            new_directives_list.append(directive)

    if filter_modification.remainder_query_filter_old is None:
        new_directives_list.append(filter_modification.remainder_query_filter_new)
        made_changes = True

    if made_changes:
        return new_directives_list
    else:
        return directives_list


def _add_pagination_filters_to_ast(
    ast, parent_ast, filter_modifications, _add_filter_to_directives_func
):
    """Return an AST with @filter added at the field, if found."""
    if not isinstance(ast, (Field, InlineFragment, OperationDefinition)):
        raise AssertionError(
            u'Input AST is of type "{}", which should not be a selection.'
            u''.format(type(ast).__name__)
        )

    if isinstance(ast, Field):
        # Check whether this field has the expected directive, if so, modify and return
        current_field_modifications = [
            modification
            for modification in filter_modifications
            if modification.vertex is parent_ast and modification.property_field == ast.name.value
        ]

        if current_field_modifications != []:
            new_ast = copy(ast)

            for modification in current_field_modifications:
                new_directives = _add_filter_to_directives_func(ast.directives, modification)
                new_ast.directives = new_directives

            return new_ast

    current_vertex_modifications = [
        filter_modification
        for filter_modification in filter_modifications
        if filter_modification.vertex is ast
    ]

    made_changes = False
    new_selections = []
    for modification in current_vertex_modifications:
        if not _get_field_with_name(ast, modification.property_field):
            new_selection = _create_field(current_vertex_modifications[0].property_field)
            new_selection = _add_pagination_filters_to_ast(
                new_selection, ast, filter_modifications, _add_filter_to_directives_func
            )

            made_changes = True
            new_selections.append(new_selection)

    if ast.selection_set is not None:
        for selection in ast.selection_set.selections:
            new_selection = _add_pagination_filters_to_ast(
                selection, ast, filter_modifications, _add_filter_to_directives_func
            )

            if new_selection is not selection:  # Changes made somewhere down the line
                made_changes = True

            new_selections.append(new_selection)

    if made_changes:
        new_ast = copy(ast)
        new_ast.selection_set = SelectionSet(selections=new_selections)
        return new_ast
    else:
        return ast


def _rename_parameters(parameters, renamed_parameters):
    """"""
    # if new_name contains parameters:
    #     bla
    # if old name not in parameters:
    #     bla
    # if old_name intersection new_name:
    #     bla

    new_parameters = copy(parameters)
    for old_name, new_name in six.iteritems(renamed_parameters):
        new_parameters[new_name] = parameters[old_name]
        del new_parameters[old_name]

    return new_parameters


def generate_parameterized_queries(schema_graph, statistics, query_ast, parameters):
    """Generate two parameterized queries that can be used to paginate over a given query.

    In order to paginate arbitrary GraphQL queries, additional filters may need to be added to be
    able to limit the number of results in the original query. This function creates two new queries
    with additional filters stored as PaginationFilters with which the query result size can be
    controlled.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        query_ast: Document, query that is being paginated.
        parameters: dict, list of parameters for the given query.

    Returns:
        ParameterizedPaginationQueries namedtuple
    """
    pagination_vertices = _get_nodes_for_pagination(statistics, query_ast)

    filter_modifications = []
    pagination_filters = []
    renamed_parameters = dict()
    for index, vertex in enumerate(pagination_vertices):
        vertex_class = vertex.name.value
        property_field_name = _get_primary_key_name(schema_graph, vertex_class)

        # By default, choose to add a new filter.
        next_page_original_filter = None
        remainder_original_filter = None
        next_page_created_filter, remainder_created_filter = _create_filters_for_pagination(
            index, parameters
        )

        related_filters = []
        field = _get_field_with_name(vertex, property_field_name)
        if field is not None and field.directives is not None:
            related_filters = [
                directive
                for directive in field.directives
                if directive.name.value == 'filter'
            ]

        # If there's already a '<' or '>=' filter, we use that for paginating over this vertex
        # instead.
        for directive in related_filters:
            if _get_filter_operation(directive) == '<':
                next_page_original_filter = directive
                break

        for directive in related_filters:
            if _get_filter_operation(directive) == '>=':
                remainder_original_filter = directive
                break

        filter_modifications.append(FilterModification(
            vertex, property_field_name, next_page_original_filter, next_page_created_filter,
            remainder_original_filter, remainder_created_filter,
        ))

        pagination_filters.append(PaginationFilter(
            vertex_class, property_field_name, next_page_created_filter, remainder_created_filter,
            related_filters
        ))

        if next_page_original_filter is not None:
            old_parameter_name = _get_binary_filter_parameter(next_page_original_filter)
            new_parameter_name = _get_binary_filter_parameter(next_page_created_filter)
            renamed_parameters[old_parameter_name] = new_parameter_name

        if remainder_original_filter is not None:
            old_parameter_name = _get_binary_filter_parameter(next_page_original_filter)
            new_parameter_name = _get_binary_filter_parameter(next_page_created_filter)
            renamed_parameters[old_parameter_name] = new_parameter_name

    query_selection = get_only_selection_from_ast(
        get_only_query_definition(query_ast, GraphQLError), GraphQLError
    )

    parameterized_next_page_query_ast = _add_pagination_filters_to_ast(
        query_selection, None, filter_modifications, _add_next_page_filters_to_directives
    )

    parameterized_remainder_query_ast = _add_pagination_filters_to_ast(
        query_selection, None, filter_modifications, _add_remainder_filters_to_directives
    )

    new_parameters = _rename_parameters(parameters, renamed_parameters)

    parameterized_queries = ParameterizedPaginationQueries(
        parameterized_next_page_query_ast,
        parameterized_remainder_query_ast,
        pagination_filters,
        new_parameters
    )
    return parameterized_queries
