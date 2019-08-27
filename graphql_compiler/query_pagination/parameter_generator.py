# Copyright 2019-present Kensho Technologies, LLC.
from copy import copy
from uuid import UUID

from graphql_compiler.compiler.helpers import get_parameter_name
from graphql_compiler.cost_estimation.filter_selectivity_utils import MAX_UUID_INT, MIN_UUID_INT


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
    return parameter_names[0], parameter_names[1]


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
    """Return the given integer's corresponding property field value.

    Note that the property field values need not be integers. For example, all UUID values can be
    converted to integers and vice versa, but they are provided in a string format (e.g.
    00000000-0000-0000-0000-000000000000).
    Example: If int_value is 9, and the property field is a uuid, then the resulting field
    value will be 00000000-0000-0000-0000-000000000009.

    Args:
        schema_graph: SchemaGraph instance.
        vertex_class: str, name of vertex class to which the property field belongs.
        property_field: str, name of property field for which the domain of values is computed.
        int_value: int, integer value which will be represented as a property field value.

    Returns:
        Any, the given integer's corresponding property field value.

    Raises:
        ValueError, if the given int_value is outside the range of valid values for the given
        property field.
    """
    if _is_uuid_field(schema_graph, vertex_class, property_field):
        if not MIN_UUID_INT <= int_value <= MAX_UUID_INT:
            raise AssertionError(u'Integer value {} could not be converted to UUID, as it'
                                 u' is not in the range of valid UUIDs {} - {}: {} {}'
                                 .format(int_value, MIN_UUID_INT, MAX_UUID_INT, vertex_class,
                                         property_field))

        return str(UUID(int=int(int_value)))
    else:
        raise AssertionError(u'Could not represent int {} as {} {}. Currently,'
                             u' only uuid fields are supported.'
                             .format(int_value, vertex_class, property_field))


def _get_domain_of_field(schema_graph, statistics, vertex_class, property_field):
    """Return the domain of values for a property field.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        vertex_class: str, name of vertex class to which the property field belongs.
        property_field: str, name of property field for which the domain of values is computed.

    Returns:
        Tuple(Any, Any), describing the inclusive lower and upper bound of the domain of values for
        the given property field.
    """
    # TODO(vlad): Once histogram statistics are implemented, the domain of values for fields without
    #             predefined lower and upper bounds (e.g. 'name') can be found.
    if _is_uuid_field(schema_graph, vertex_class, property_field):
        return MIN_UUID_INT, MAX_UUID_INT
    else:
        raise AssertionError(u'Could not find domain for {} {}. Currently,'
                             u' only uuid fields are supported.'
                             .format(vertex_class, property_field))


def _get_lower_and_upper_bound_of_ternary_int_filter(
    schema_graph, vertex_class, property_field, filter_directive, user_parameters
):
    """Return the interval of values passing through a ternary filter over an integer property.

    Args:
        schema_graph: SchemaGraph instance.
        vertex_class: str, name of vertex class to which the property field belongs.
        property_field: str, name of integer property field to which the Filter Directives belong.
        filter_directive: Directives, ternary filter directive for which the lower and upper bound
                          of passing values is computed.
        user_parameters: dict, parameters defined by the user for the query being paginated.

    Returns:
        Tuple(int or None, int or None), describing the inclusive lower and upper bound of values
        passing through the given filter. If the given filter does not restrict the lower bound,
        a value of None is returned for the lower bound, and respectively for the upper bound.
    """
    lower_bound_parameter_name, upper_bound_parameter_name = _get_ternary_filter_parameters(
        filter_directive
    )
    lower_bound_parameter_value = user_parameters[lower_bound_parameter_name]
    upper_bound_parameter_value = user_parameters[upper_bound_parameter_name]

    lower_bound_int = _convert_field_value_to_int(
        schema_graph, vertex_class, property_field, lower_bound_parameter_value
    )
    upper_bound_int = _convert_field_value_to_int(
        schema_graph, vertex_class, property_field, upper_bound_parameter_value
    )
    return lower_bound_int, upper_bound_int


def _get_lower_and_upper_bound_of_binary_int_filter(
    schema_graph, vertex_class, property_field, filter_directive, user_parameters
):
    """Return the interval of values passing through a binary filter over an integer property.

    Args:
        schema_graph: SchemaGraph instance.
        vertex_class: str, name of vertex class to which the property field belongs.
        property_field: str, name of integer property field to which the Filter Directives belong.
        filter_directive: Directives, binary filter directive for which the lower and upper bound of
                          passing values is computed.
        user_parameters: dict, parameters defined by the user for the query being paginated.

    Returns:
        Tuple(int or None, int or None), describing the inclusive lower and upper bound of values
        passing through the given filter. If the given filter does not restrict the lower bound,
        a value of None is returned for the lower bound, and respectively for the upper bound.
    """
    parameter_name = _get_binary_filter_parameter(filter_directive)
    parameter_value = user_parameters[parameter_name]
    value_as_int = _convert_field_value_to_int(
        schema_graph, vertex_class, property_field, parameter_value
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
        raise AssertionError(u'Filter operation {} not a supported binary inequality operator.')

    return lower_bound, upper_bound


def _get_lower_and_upper_bound_of_int_filters(
    schema_graph, vertex_class, property_field, filter_list, user_parameters
):
    """Return the interval of values passing through a list of filters over an integer property.

    Args:
        schema_graph: SchemaGraph instance.
        vertex_class: str, name of vertex class to which the property field belongs.
        property_field: str, name of integer property field to which the Filter Directives belong.
        filter_list: List[Directives], list of filter directives.
        user_parameters: dict, parameters defined by the user for the query being paginated.

    Returns:
        Tuple(int or None, int or None), describing the inclusive lower and upper bound of values
        passing through all filters. If the given filters do not restrict the lower bound,
        a value of None is returned for the lower bound, and respectively for the upper bound.
    """
    binary_inequality_filters = ['<', '<=', '>=', '>=']
    ternary_inequality_filters = ['between']

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
    """Create parameter values for a pagination filter over an integer property.

    Args:
        schema_graph: SchemaGraph instance.
        statistics: Statistics object.
        pagination_filter: PaginationFilter namedtuple.
        user_parameters: dict, parameters defined by the user for the query being paginated.
        num_pages: int, number of pages to split the query into.

    Returns:
        two dicts:
            - dict, containing parameters for the PaginationFilter's next page query filter.
            - dict, containing parameters for the PaginationFilter's remainder query filter.
    """
    vertex_class = pagination_filter.vertex_class
    property_field = pagination_filter.property_field

    # TODO(vlad): Once histograms are implemented, the filter parameters generation can be improved,
    #             since we can avoid assuming that property field values are distributed evenly
    #             among the domain of possible values.
    domain_lower_bound, domain_upper_bound = _get_domain_of_field(
        schema_graph, statistics, vertex_class, property_field
    )
    if domain_lower_bound is None or domain_upper_bound is None:
        raise AssertionError(u'Received domain with no lower or upper bound {} {}.'
                             u' Generating parameters for filters with such domains'
                             u' is unsupported.'.format(domain_lower_bound, domain_upper_bound))

    filter_lower_bound, filter_upper_bound = _get_lower_and_upper_bound_of_int_filters(
        schema_graph, vertex_class, property_field, pagination_filter.already_existing_filters,
        user_parameters
    )

    # We find the interval of values that pass all filters of the given query.
    if filter_lower_bound is not None:
        intersection_lower_bound = max(domain_lower_bound, filter_lower_bound)
    else:
        intersection_lower_bound = domain_lower_bound

    if filter_upper_bound is not None:
        intersection_upper_bound = min(domain_upper_bound, filter_upper_bound)
    else:
        intersection_upper_bound = domain_upper_bound

    if intersection_lower_bound > intersection_upper_bound:
        raise AssertionError(u'Could not page over empty interval {} {}: {} {}.'
                             .format(intersection_lower_bound, intersection_upper_bound,
                                     pagination_filter, user_parameters))

    interval_size = intersection_upper_bound - intersection_lower_bound + 1

    # Assumption: vertex_class vertices are distributed evenly among the property field's domain.
    # E.g. To split the query into 5 pages, the current filter's parameter should be 1/5 of the
    # original query's integer interval.
    fraction_to_query = float(1.0 / num_pages)
    filter_parameter_int = intersection_lower_bound + int(interval_size * fraction_to_query)
    filter_parameter_as_field_value = _convert_int_to_field_value(
        schema_graph, vertex_class, property_field, filter_parameter_int
    )

    next_page_parameter_name = _get_binary_filter_parameter(
        pagination_filter.next_page_query_filter
    )
    remainder_parameter_name = _get_binary_filter_parameter(
        pagination_filter.remainder_query_filter
    )

    next_page_filter_parameters = {next_page_parameter_name: filter_parameter_as_field_value}
    remainder_filter_parameters = {remainder_parameter_name: filter_parameter_as_field_value}
    return next_page_filter_parameters, remainder_filter_parameters


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

    # TODO(vlad): Support paginating over multiple PaginationFilters for better pages. For example,
    #             in queries with cartesian product-esque result data, paginating with a single
    #             Filter does not perform well in practice.
    if _is_uuid_field(
        schema_graph, pagination_filter.vertex_class, pagination_filter.property_field
    ):
        # Since all UUIDs correspond to integers, we can paginate over them as integer filters.
        next_page_filter_parameters, remainder_filter_parameters = (
            _generate_parameters_for_int_pagination_filter(
                schema_graph, statistics, pagination_filter, user_parameters, num_pages
            )
        )
    else:
        raise AssertionError(u'Found pagination filter over vertex class {}'
                             u' and property field {}. Currently, only filters'
                             u' over uuid property fields are allowed for pagination: {}'
                             .format(pagination_filter.vertex_class,
                                     pagination_filter.property_field,
                                     pagination_filters))

    next_page_pagination_parameters.update(next_page_filter_parameters)
    remainder_pagination_parameters.update(remainder_filter_parameters)
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
                                 u' pagination parameter {} belonging to next page query: {} {} {}'
                                 .format(next_page_filter_parameter_name, pagination_filters,
                                         next_page_pagination_parameters,
                                         remainder_pagination_parameters))

        if remainder_filter_parameter_name not in remainder_pagination_parameters:
            raise AssertionError(u'Could not find parameter value for'
                                 u' pagination parameter {} belonging to remainder query: {} {} {}'
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
            - dict, parameters with which to execute the next page query. The next page query's
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
    # possible that both a user parameter and a pagination parameter have the same parameter name.
    # If such a conflict occurs, the pagination parameter is chosen as the parameter's value.
    next_page_parameters = copy(user_parameters)
    next_page_parameters.update(next_page_pagination_parameters)
    remainder_parameters = copy(user_parameters)
    remainder_parameters.update(remainder_pagination_parameters)

    return next_page_parameters, remainder_parameters
