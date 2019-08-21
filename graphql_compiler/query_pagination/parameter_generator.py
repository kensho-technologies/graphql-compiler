# Copyright 2019-present Kensho Technologies, LLC.
from copy import deepcopy
from uuid import UUID

from graphql_compiler.compiler.helpers import get_parameter_name


def _is_uuid_field(vertex_class, property_field):
    """Stuff"""
    return property_field == 'uuid'


def _convert_uuid_string_to_int(uuid_string):
    """Return the integer representation of a UUID string."""
    return UUID(uuid_string).int


def _get_lower_and_upper_bound_of_related_filters(pagination_filter, user_parameters):
    """Stuff"""
    lower_bound, upper_bound = None, None
    for related_filter in pagination_filter.related_filters:
        if related_filter.op_name == '<' or related_filter.op_name == '<=':
            upper_bound = user_parameters[get_parameter_name(related_filter['value'][0])]
        if related_filter.op_name == '>' or related_filter.op_name == '>=':
            lower_bound = user_parameters[get_parameter_name(related_filter['value'][0])]
        if related_filter.op_name == 'between':
            lower_bound = user_parameters[get_parameter_name(related_filter['value'][0])]
            upper_bound = user_parameters[get_parameter_name(related_filter['value'][1])]

    return lower_bound, upper_bound


def _get_domain_of_field(vertex_class, field_name):
    if field_name == 'uuid':
        return '00000000-0000-0000-0000-000000000000', 'ffffffff-ffff-ffff-ffff-ffffffffffff'

    raise AssertionError(u'Unrecognized property field {}'.format(field_name))


def _generate_parameters_for_pagination_filters(
    schema_graph, statistics, pagination_filters, user_parameters, num_pages
):
    """Stuff"""
    next_page_pagination_parameters, remainder_pagination_parameters = dict(), dict()

    if len(pagination_filters) != 1:
        raise AssertionError(u'Expected pagination filters {} to have exactly'
                             u' one element, found {} elements: {}'
                             .format(pagination_filters, len(pagination_filters), user_parameters))
    pagination_filter = pagination_filters[0]

    if not _is_uuid_field(pagination_filter.vertex_class, pagination_filter.property_field):
        raise AssertionError(u'Found pagination filter over vertex class {}'
                             u' and property field {}. Currently, only filters'
                             u' over uuid property fields are allowed for pagination.'
                             .format(pagination_filter.vertex_class,
                                     pagination_filter.property_field))

    domain_lower_bound, domain_upper_bound = _get_domain_of_field(
        pagination_filter.vertex_class, pagination_filter.property_field
    )
    lower_bound, upper_bound = _get_lower_and_upper_bound_of_related_filters(
        pagination_filter, user_parameters
    )
    if lower_bound is not None:
        domain_lower_bound = max(domain_lower_bound, lower_bound)
    if upper_bound is not None:
        domain_upper_bound = max(domain_upper_bound, upper_bound)

    if domain_lower_bound > domain_upper_bound:
        raise AssertionError(u'Invalid domain.')

    lower_bound_int = _convert_uuid_string_to_int(domain_lower_bound)
    upper_bound_int = _convert_uuid_string_to_int(domain_upper_bound)

    fraction_covered = float(1.0 / num_pages)

    proper_cut = lower_bound_int + (upper_bound_int - lower_bound_int) * fraction_covered

    proper_cut_uuid = str(UUID(int=int(proper_cut)))

    next_page_query_parameter_name = pagination_filter.next_page_query_filter.arguments[1].value.values[0].value
    remainder_query_parameter_name = pagination_filter.remainder_query_filter.arguments[1].value.values[0].value
    next_page_pagination_parameters[get_parameter_name(next_page_query_parameter_name)] = proper_cut_uuid
    remainder_pagination_parameters[get_parameter_name(remainder_query_parameter_name)] = proper_cut_uuid

    return next_page_pagination_parameters, remainder_pagination_parameters


def _validate_all_pagination_filters_have_parameters(
    pagination_filters, next_page_pagination_parameters, remainder_pagination_parameters
):
    """Stuff"""
    return None


def generate_parameters_for_parameterized_query(
    schema_graph, statistics, parameterized_pagination_queries, num_pages
):
    """Generate parameters for the given parameterized pagination queries.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        parameterized_pagination_queries: ParameterizedPaginationQueries namedtuple, parameterized
                                          queries for which parameters are being generated.
        num_pages: int, number of pages to split the query into.

    Returns:
        two dicts:
            - dict, parameters with which to execute the page query. The next page query's
              parameters are generated such that only a page of the original query's result data is
              produced when the next page query is executed.
            - dict, parameters with which to execute the remainder query. The remainder query's
              parameters are generated such that the remainder of the original query's
              result data is produced when the remainder query is executed.
    """
    pagination_filters = parameterized_pagination_queries.pagination_filters
    user_parameters = parameterized_pagination_queries.user_parameters

    next_page_pagination_parameters, remainder_pagination_parameters = (
        _generate_parameters_for_pagination_filters(
            schema_graph, statistics, pagination_filters, user_parameters, num_pages
        )
    )

    _validate_all_pagination_filters_have_parameters(
        pagination_filters, next_page_pagination_parameters, remainder_pagination_parameters
    )

    # Since some of the user's parameters may have been parameterized
    next_page_parameters = deepcopy(user_parameters)
    next_page_parameters.update(next_page_pagination_parameters)
    remainder_parameters = deepcopy(user_parameters)
    remainder_parameters.update(remainder_pagination_parameters)

    return next_page_parameters, remainder_parameters
