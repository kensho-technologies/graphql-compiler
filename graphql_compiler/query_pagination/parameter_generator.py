# Copyright 2019-present Kensho Technologies, LLC.
from copy import copy
from uuid import UUID

from graphql_compiler.compiler.helpers import get_parameter_name


def _get_binary_filter_parameter(filter_directive):
    """Return the parameter name for a binary Filter Directive."""
    filter_arguments = filter_directive.arguments[1].value.values
    if len(filter_arguments) != 1:
        raise AssertionError(u'Expected one argument in filter {}'.format(filter_directive))

    argument_name = filter_arguments[0].value
    parameter_name = get_parameter_name(argument_name)
    return parameter_name


def _get_ternary_filter_parameters(filter_directive):
    """Return the parameter names for a ternary Filter Directive."""
    filter_arguments = filter_directive.arguments[1].value.values
    if len(filter_arguments) != 2:
        raise AssertionError(u'Expected two arguments in filter {}'.format(filter_directive))

    argument_names = [filter_arguments[0].value, filter_arguments[1].value]
    parameter_names = [
        get_parameter_name(argument)
        for argument in argument_names
    ]
    return parameter_names


def _get_filter_operation(filter_directive):
    """Return the @filter's op_name as a string."""
    return filter_directive.arguments[0].value.value


def _is_uuid_field(vertex_class, property_field):
    """Return True if the given vertex's property field is a UUID."""
    return property_field == 'uuid'


def _decode_uuid_to_int(uuid_string):
    """Return the integer representation of a UUID string."""
    return UUID(uuid_string).int


def _encode_int_as_uuid(uuid_int):
    """Return the n-th lexicographical UUID, where n is the int argument."""
    return str(UUID(int=int(uuid_int)))


def _get_lower_and_upper_bound_of_related_filters(pagination_filter, user_parameters):
    """Stuff"""
    lower_bound, upper_bound = None, None
    for related_filter in pagination_filter.related_filters:
        filter_operation = _get_filter_operation(related_filter)

        if filter_operation == '<':
            upper_bound = user_parameters[_get_binary_filter_parameter(related_filter)]
        elif filter_operation == '<=':
            upper_bound = user_parameters[_get_binary_filter_parameter(related_filter)]
        elif filter_operation == '>':
            lower_bound = user_parameters[_get_binary_filter_parameter(related_filter)]
        elif filter_operation == '>=':
            lower_bound = user_parameters[_get_binary_filter_parameter(related_filter)]
        elif filter_operation == 'between':
            parameter_names = _get_ternary_filter_parameters(related_filter)
            lower_bound = user_parameters[parameter_names[0]]
            upper_bound = user_parameters[parameter_names[1]]

    return lower_bound, upper_bound


def _get_domain_of_field(vertex_class, field_name):
    """Stuff"""
    if field_name == 'uuid':
        return '00000000-0000-0000-0000-000000000000', 'ffffffff-ffff-ffff-ffff-ffffffffffff'

    raise AssertionError(u'Unrecognized property field {}'.format(field_name))


def _generate_parameters_for_int_pagination_filter(
    schema_graph, statistics, pagination_filter, user_parameters, num_pages
):
    """Stuff"""
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

    lower_bound_int = _decode_uuid_to_int(domain_lower_bound)
    upper_bound_int = _decode_uuid_to_int(domain_upper_bound)

    fraction_covered = float(1.0 / num_pages)
    proper_cut = lower_bound_int + (upper_bound_int - lower_bound_int) * fraction_covered
    proper_cut_uuid_string = _encode_int_as_uuid(int(proper_cut))

    next_page_parameter_name = _get_binary_filter_parameter(
        pagination_filter.next_page_query_filter
    )
    remainder_parameter_name = _get_binary_filter_parameter(
        pagination_filter.remainder_query_filter
    )

    return (
        (next_page_parameter_name, proper_cut_uuid_string),
        (remainder_parameter_name, proper_cut_uuid_string)
    )


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

    if _is_uuid_field(pagination_filter.vertex_class, pagination_filter.property_field):
        next_page_parameter, remainder_parameter = _generate_parameters_for_int_pagination_filter(
            schema_graph, statistics, pagination_filter, user_parameters, num_pages
        )
    else:
        raise AssertionError(u'Found pagination filter over vertex class {}'
                             u' and property field {}. Currently, only filters'
                             u' over uuid property fields are allowed for pagination: {}'
                             .format(pagination_filter.vertex_class,
                                     pagination_filter.property_field,
                                     pagination_filters))

    next_page_pagination_parameters[next_page_parameter[0]] = next_page_parameter[1]
    remainder_pagination_parameters[remainder_parameter[0]] = remainder_parameter[1]

    return next_page_pagination_parameters, remainder_pagination_parameters


def _validate_all_pagination_filters_have_parameters(
    pagination_filters, next_page_pagination_parameters, remainder_pagination_parameters
):
    """Validate that all PaginationFilters have assigned parameter values."""
    for pagination_filter in pagination_filters:
        next_page_filter_parameter_name = _get_binary_filter_parameter(
            pagination_filter.next_page_query_filter
        )
        remainder_filter_parameter_name = _get_binary_filter_parameter(
            pagination_filter.remainder_query_filter
        )

        if next_page_filter_parameter_name not in next_page_pagination_parameters:
            raise AssertionError(u'Could not find parameter value for'
                                 u'pagination parameter {} belonging to next page query: {} {} {}'
                                 .format(next_page_filter_parameter_name, pagination_filters,
                                         next_page_pagination_parameters,
                                         remainder_pagination_parameters))

        if remainder_filter_parameter_name not in remainder_pagination_parameters:
            raise AssertionError(u'Could not find parameter value for'
                                 u'pagination parameter {} belonging to remainder query: {} {} {}'
                                 .format(remainder_filter_parameter_name, pagination_filters,
                                         next_page_pagination_parameters,
                                         remainder_pagination_parameters))


def generate_parameters_for_parameterized_query(
    schema_graph, statistics, parameterized_pagination_queries, num_pages
):
    """Generate parameters for the given parameterized pagination queries.
][
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

    # Since the query parameterizer may have chosen some of the user's filters for pagination, it's
    # possible that both a user parameter and a pagination parameter exist with the same parameter
    # name. If such a conflict occurs, the pagination parameter is chosen as the parameter's value.
    next_page_parameters = copy(user_parameters)
    next_page_parameters.update(next_page_pagination_parameters)
    remainder_parameters = copy(user_parameters)
    remainder_parameters.update(remainder_pagination_parameters)

    return next_page_parameters, remainder_parameters
