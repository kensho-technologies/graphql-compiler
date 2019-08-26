# Copyright 2019-present Kensho Technologies, LLC.
from copy import copy
from uuid import UUID

from graphql_compiler.compiler.helpers import get_parameter_name
from graphql_compiler.cost_estimation.filter_selectivity_utils import MIN_UUID_INT, MAX_UUID_INT


def _get_binary_filter_parameter(filter_directive):
    """Return the parameter name of a binary Filter Directive."""
    filter_arguments = filter_directive.arguments[1].value.values
    if len(filter_arguments) != 1:
        raise AssertionError(u'Expected one argument in filter {}'.format(filter_directive))

    argument_name = filter_arguments[0].value
    parameter_name = get_parameter_name(argument_name)
    return parameter_name


def _get_ternary_filter_parameters(filter_directive):
    """Return the parameter names of a ternary Filter Directive."""
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
    """Return the Filter Directive's op_name as a string."""
    return filter_directive.arguments[0].value.value


def _is_uuid_field(schema_graph, vertex_class, property_field):
    """Return True if the given vertex's property field is a UUID."""
    # HACK(vlad): Currently, each UUID is assumed to have a name of 'uuid'. Using the schema
    #             graph for knowledge about UUID fields would generalize better.
    return property_field == 'uuid'


def _convert_field_value_to_int(schema_graph, vertex_class, property_field, value):
    """Return the integer representation of a property field value."""
    if _is_uuid_field(schema_graph, vertex_class, property_field):
        return UUID(value).int
    else:
        raise AssertionError(u'Could not represent {} {} value {} as int. Currently,'
                             u' only uuid fields are supported.'
                             .format(vertex_class, property_field, value))


def _convert_int_to_field_value(schema_graph, vertex_class, property_field, int_value):
    """Return the given integer's corresponding property field value."""
    if _is_uuid_field(schema_graph, vertex_class, property_field):
        return str(UUID(int=int(int_value)))
    else:
        raise AssertionError(u'Could not represent int {} as {} {}. Currently,'
                             u' only uuid fields are supported.'
                             .format(int_value, vertex_class, property_field))


def _get_domain_of_field(schema_graph, statistics, vertex_class, property_field):
    """Return the domain of values for a property field.

    Args:
        Stuff

    Returns:
        Stuff
    """
    # TODO(vlad): Once histogram statistics are implemented, the domain of values for fields without
    #             predefined lower and upper bounds (e.g. 'name') can be found.
    if _is_uuid_field(schema_graph, vertex_class, property_field):
        return MIN_UUID_INT, MAX_UUID_INT
    else:
        raise AssertionError(u'Could not find domain for {} {}. Currently,'
                             u' only uuid fields are supported.'
                             format(vertex_class, field_name))


def _get_lower_and_upper_bound_of_ternary_int_filter(
    schema_graph, vertex_class, property_field, filter_directive, user_parameters
):
    """Return the lower and upper bound of integers passing through a ternary integer filter.

    Args:
        Stuff

    Returns:
        Stuff
    """
    parameter_names = _get_ternary_filter_parameters(filter_directive)
    lower_bound_parameter, upper_bound_parameter = parameter_names[0], parameter_names[1]
    lower_bound_int = _convert_field_value_to_int(
        schema_graph, pagination_filter.vertex_class, pagination_filter.property_field,
        user_parameters[lower_bound_parameter]
    )
    upper_bound_int = _convert_field_value_to_int(
        schema_graph, pagination_filter.vertex_class, pagination_filter.property_field,
        user_parameters[upper_bound_parameter]
    )

    return lower_bound_int, upper_bound_int


def _get_lower_and_upper_bound_of_binary_int_filter(
    schema_graph, vertex_class, property_field, filter_directive, user_parameters
):
    """Return the lower and upper bound of integer passing through a binary integer filter.

    Args:
        Stuff

    Returns:
        Stuff
    """
    parameter_names = _get_binary_filter_parameters(filter_directive)
    value_as_int = _convert_field_value_to_int(
        schema_graph, pagination_filter.vertex_class, pagination_filter.property_field,
        parameter_value
    )

    # We indicate no lower and upper bounds by setting the values to None.
    lower_bound, upper_bound = None, None
    filter_operation = _get_filter_operation(filter_directive)
    if filter_operation == '<':
        upper_bound = value_as_int
    elif filter_operation == '<=':
        upper_bound = value_as_int
    elif filter_operation == '>':
        lower_bound = value_as_int
    elif filter_operation == '>=':
        lower_bound = value_as_int
    else:
        raise AssertionError(u'Filter operation {} not supported.')

    return lower_bound, upper_bound


def _get_lower_and_upper_bound_of_int_filters(
    schema_graph, vertex_class, property_field, filter_list, user_parameters
):
    """Return the lower and upper bound of values passing through a list of integer filters.

    Args:
        Stuff

    Returns:
        Stuff
    """
    binary_inequality_filters = ['<', '<=', '>=', '>=']
    ternary_inequality_filters = ['between']

    # We indicate no lower and upper bounds by setting the values to None.
    lower_bound, upper_bound = None, None
    for filter_directive in filter_list:
        filter_operation = _get_filter_operation(filter_directive)

        if filter_operation in binary_inequality_filters:
            lower_bound, upper_bound = _get_lower_and_upper_bound_of_binary_int_filter(
                schema_graph, vertex_class, property_field, filter_directive, user_parameters
            )
        elif filter_operation in ternary_inequality_filters:
            lower_bound, upper_bound = _get_lower_and_upper_bound_of_ternary_int_filter(
                schema_graph, vertex_class, property_field, filter_directive, user_parameters
            )
        else:
            raise AssertionError(u'Found unsupported inequality filter operation {}.'
                                 u' Currently supported filter operations are: {} {}'
                                 .format(filter_operation, binary_inequality_filters,
                                         ternary_inequality_filters))

    return lower_bound, upper_bound


def _generate_parameters_for_int_pagination_filter(
    schema_graph, statistics, pagination_filter, user_parameters, num_pages
):
    """Create parameter values for a pagination filter over an integer field.

    Args:
        Stuff

    Returns:
        Stuff
    """
    vertex_class = pagination_filter.vertex_class
    property_field = pagination_filter.property_field

    domain_lower_bound, domain_upper_bound = _get_domain_of_field(
        schema_graph, statistics, vertex_class, property_field
    )
    if domain_lower_bound is None or domain_upper_bound is None:
        raise AssertionError(u'Received domain with no lower or upper bound {} {}.'
                             u' Parameters for pagination filters with such domains'
                             u' is unsupported.'.format(domain_lower_bound, domain_upper_bound))

    filter_lower_bound, filter_upper_bound = _get_lower_and_upper_bound_of_int_filters(
        schema_graph, vertex_class, property_field, pagination_filter.related_filters,
        user_parameters
    )

    lower_bound = domain_lower_bound
    upper_bound = domain_upper_bound
    if filter_lower_bound is not None:
        lower_bound = max(domain_lower_bound, filter_lower_bound)
    if filter_upper_bound is not None:
        upper_bound = min(domain_upper_bound, filter_upper_bound)

    if lower_bound > upper_bound:
        raise AssertionError(u'Could not page over empty interval {} {}: {} {}.'
                             .format(lower_bound, upper_bound, pagination_filter, user_parameters))

    fraction_to_query = float(1.0 / num_pages)

    interval_size = upper_bound - lower_bound + 1
    filter_value_int = lower_bound + interval_size * fraction_to_query
    filter_value_as_field_value = _convert_int_to_field_value(
        schema_graph, vertex_class, property_field, int(filter_value)
    )

    next_page_parameter_name = _get_binary_filter_parameter(
        pagination_filter.next_page_query_filter
    )
    remainder_parameter_name = _get_binary_filter_parameter(
        pagination_filter.remainder_query_filter
    )
    return (
        (next_page_parameter_name, filter_value_as_field_value),
        (remainder_parameter_name, filter_value_as_field_value)
    )


def _generate_parameters_for_pagination_filters(
    schema_graph, statistics, pagination_filters, user_parameters, num_pages
):
    """Create parameter values for the given pagination filters."""
    next_page_pagination_parameters, remainder_pagination_parameters = dict(), dict()

    if len(pagination_filters) != 1:
        raise AssertionError(u'Expected the pagination filters list {} to have exactly'
                             u' one element, found {} elements: {}'
                             .format(pagination_filters, len(pagination_filters), user_parameters))
    pagination_filter = pagination_filters[0]

    if _is_uuid_field(
        schema_graph, pagination_filter.vertex_class, pagination_filter.property_field
    ):
        # Since all UUIDs correspond to integers, we can paginate over them as integer filters.
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

    # Indices are not desirable here
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
