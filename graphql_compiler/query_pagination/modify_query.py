# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import copy

from graphql.language.ast import (
    Argument, Directive, Field, InlineFragment, Name, OperationDefinition, SelectionSet
)


# ParameterizedPaginationQueries namedtuple describes two query ASTs that have filters for
# pagination added with which the query result size can be controlled.
ParameterizedPaginationQueries = namedtuple(
    'ParameterizedPaginationQueries',
    (
        'next_page_query',          # Document, AST of query that will return the next page of
                                    # results when its parameterized filters have parameter values.

        'remainder_query',          # Document, AST of query that will return the remainder of
                                    # results when its parameterized filters have parameter values.

        'pagination_filters',       # List[PaginationFilter], filters usable for pagination. Note
                                    # that depending on if the filters chosen for pagination are
                                    # user-created or added by pagination, they might not have
                                    # parameter values. These can be generated using the
                                    # parameter_generator module.

        'user_parameters',          # dict, parameters that the user has defined for query filters.
                                    # The parameter values  may have been modified by the query
                                    # paginator for pagination purposes.
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
        'property_field',               # str, name of the property field being filtered.
        'next_page_query_filter',       # Directive, filter directive with '<' operator usable
                                        # for pagination in the next page query.
        'remainder_query_filter',       # Directive, filter directive with '>=' operator usable
                                        # for pagination in the remainder query.
        'related_filters',              # List[Directive], filter directives that are on the same
                                        # vertex and property field as the next page and remainder
                                        # queries' filters.
    ),
)


def _get_field_with_name(ast, field_name):
    """Search the AST selection set for a field with the given name, returning None if not found."""
    if ast.selection_set is None:
        return None

    selections_list = ast.selection_set.selections
    for selection in selections_list:
        if selection.name.value == field_name:
            return selection

    return None


def _add_next_page_filter_to_directives(directives_list, filter_modification):
    """Return a directives list with the next page filter added. If already present, do nothing."""
    if filter_modification.next_page_filter not in directives_list:
        new_directives = copy(directives_list)
        new_directives.append(filter_modification.next_page_filter)
        return new_directives

    return directives_list


def _add_remainder_filter_to_directives(directives_list, filter_modification):
    """Return a directives list with the remainder filter added."""
    if filter_modification.remainder_filter not in directives_list:
        new_directives = copy(directives_list)
        new_directives.append(filter_modification.remainder_filter)
        return new_directives

    return directives_list


def _add_pagination_filters_recursively(ast, parent_ast, filter_modifications, add_filter_func):
    """Return an AST with pagination filters added.

    Args:
        ast: Document, AST of the current node.
        parent_ast: Document, parent AST of the current node.
        filter_modifications: List[FilterModification namedtuple], describing filters to be added.
        add_filter_func: Function that applies filter modifications to list of directives. This
                         function either adds the next page query's filter, or the remainder query's
                         filter, depending on which query is currently being generated recursively.

    Returns:
        Document, AST with the given filter modifications performed.
    """
    if not isinstance(ast, (Field, InlineFragment, OperationDefinition)):
        raise AssertionError(
            u'Input AST is of type "{}", which should not be a selection.'
            u''.format(type(ast).__name__)
        )

    if isinstance(ast, Field):
        current_field_modifications = [
            modification
            for modification in filter_modifications
            if modification.vertex is parent_ast and modification.property_field == ast.name.value
        ]

        if current_field_modifications != []:
            # Add filter directives to property field
            new_ast = copy(ast)

            for modification in current_field_modifications:
                new_directives = add_filter_func(ast.directives, modification)
                new_ast.directives = new_directives

            return new_ast

    current_vertex_modifications = [
        filter_modification
        for filter_modification in filter_modifications
        if filter_modification.vertex is ast
    ]

    made_changes = False
    new_selections = []
    # We first consider whether to add a property field, to make sure property fields precede vertex
    # fields.
    for modification in current_vertex_modifications:
        # If the property field is not a Selection, add it to new_selections.
        if not _get_field_with_name(ast, modification.property_field):
            new_selection = _create_field(modification.property_field)
            new_selection = _add_pagination_filters_recursively(
                new_selection, ast, filter_modifications, add_filter_func
            )

            made_changes = True
            new_selections.append(new_selection)

    if ast.selection_set is not None:
        for selection in ast.selection_set.selections:
            new_selection = _add_pagination_filters_recursively(
                selection, ast, filter_modifications, add_filter_func
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


def _generate_pagination_filter(filter_modification):
    """Create PaginationFilter namedtuple documenting filters usable for pagination."""
    vertex_class = filter_modification.vertex.name.value
    property_field = filter_modification.property_field
    next_page_query_filter = filter_modification.next_page_query_filter
    remainder_query_filter = filter_modification.remainder_query_filter
    if field is None or field.directives is None:
        related_filters = []
    else:
        related_filters = [
            directive
            for directive in field.directives
            if (
                directive.name.value == 'filter' and
                directive is not next_page_query_filter and
                directive is not remainder_query_filter
            )
        ]

    pagination_filter = PaginationFilter(
        vertex_class, property_field, next_page_query_filter, remainder_query_filter,
        related_filters
    )
    return pagination_filter


def generate_parameterized_queries(
    schema_graph, statistics, query_ast, parameters, filter_modifications
):
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
        filter_modifications: List[FilterModification namedtuple], documenting modifications to be
                              made to the next page query and remainder query's filters.

    Returns:
        ParameterizedPaginationQueries namedtuple.
    """
    next_page_ast = _add_pagination_filters_recursively(
        ast, None, filter_modifications, _add_next_page_filter_to_directives
    )
    remainder_ast = _add_pagination_filters_recursively(
        ast, None, filter_modifications, _add_remainder_filter_to_directives
    )
    if next_page_ast is query_ast or remainder_ast is query_ast:
        raise AssertionError(u'Expected next page query {} and remainder query {} to be different'
                             u' from the original given query {}. This means filter modifications'
                             u' were not applied: {}'
                             .format(next_page_ast, remainder_ast, query_ast, filter_modifications))

    pagination_filters = [
        _generate_pagination_filter(modification)
        for modification in filter_modifications
    ]

    parameterized_queries = ParameterizedPaginationQueries(
        next_page_ast, remainder_ast, pagination_filters, parameters
    )
    return parameterized_queries
