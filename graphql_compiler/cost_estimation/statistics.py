from collections import namedtuple

##
# A GraphQLStatistics object bundles statistics regarding GraphQL objects and vertex field values.
# Contains:
#   - class_count: function, string -> int, that accepts a class name and returns the total number
#                  of instances plus subclass instances.
#   - concrete_vertex_links: function, (string, string, string) -> optional int, that accepts two 
#                        concrete vertex class names and an edge class name, and returns how many 
#                        edges of the given type connect two vertices of the given types, or None if
#                        the statistic doesn't exist.
#   - domain_counts: function, (string, string) -> optional int, that accepts a class name and a
#                    valid vertex field, and returns the number of different values the vertex field
#                    has, or None if the statistic doesn't exist.
#   - histograms: function, (string, string) -> optional [(float, float, float)], that accepts a
#                 class name and a valid vertex field, and returns a list containing tuple
#                 describing each histogram entry as (inclusive start of bucket interval, inclusive 
#                 end of bucket interval, element count), or None if the statistic doesn't exist.
GraphQLStatistics = namedtuple(
    'GraphQLStatistics',
    ('class_count', 'concrete_vertex_links', 'domain_count', 'histogram')
)

def _get_class_count(statistics, name):
    """Return how many classes have the given name."""
    return statistics['class_count'](name)


def _get_vertex_pair_links_count(statistics, concrete_vertex_in_name, concrete_vertex_out_name, 
                                 edge_name):
    """Return number of edges of a given type connecting two concrete vertices of given types."""
    return statistics['concrete_vertex_links'](concrete_vertex_in_name, concrete_vertex_out_name, 
                                               edge_name)


def _get_domain_count(statistics, vertex_name, field_name):
    return statistics['domain_count'](vertex_name, field_name)


def _get_histograms(statistics, vertex_name, field_name):
    return statistics['histograms'](vertex_name, field_name)

    # def _assert_interval_type_is_number(interval):
    #     for element in interval:
    #         element_type = type(element)
    #         if element_type != IntType and element_type != FloatType:
    #             raise AssertionError('Provided non-number type as argument {}'.format(element_type))


    # def _get_intersection_length(interval_a, interval_b):
    #     """Find the length of intersection between two intervals given as a tuple of ints or floats."""
    #     intersection_of_bucket_and_interval = min(interval_a[1], interval_b[1]) - 
    #                                           max(interval_a[0], interval_b[0])
    #     return intersection_of_bucket_and_interval

    # def _estimate_count_in_interval_using_bucket(bucket, interval):
    #     """Estimate number of elements in bucket (start, end, bucketCount) contained in interval"""


    # def _attempt_estimate_count_in_interval_from_histogram(vertex_name, field_name, lower_bound,
    #                                                     upper_bound):
    #     """Using histograms, attempts to estimate """
    #     histogram = self._histograms(vertex_name, field_name)
    #     if histogram is None:
    #         return None

    #     result_count = 0
    #     for histogram_bucket in histogram:
    #         length_of_intervals_intersection = _get_intersection_length((lower_bound, upper_bound),
    #                                                                  (histogram_bucket[0], 
    #                                                                   histogram_bucket[1]))
    #         bucket_length = histogram_bucket[1] - histogram_bucket[0]
    #         intersection_as_fraction_of_bucket = length_of_intervals_intersection / bucket_length
    #         elements_in_bucket = histogram_bucket[2]

    #         # We assume elements are uniformly distributed within the bucket's interval and include the
    #         # fraction of the bucket's entries that are within the interval we're interested in
    #         result_count += elements_in_bucket * intersection_as_fraction_of_bucket
    #     return result_count


    # def _attempt_estimate_count_in_interval_from_boundary_values(vertex_name, field_name, lower_bound,
    #                                                           upper_bound):
    #     boundary_values = self._boundary_values(vertex_name, field_name)
    #     if boundary_values is None:
    #         return None

    #     # Assume field_name values are uniformly distributed among the minimum and maximum values
    #     # TODO(vlad): if the min and max values are different by several orders of magnitude, assume
    #     #             elements are distributed logarithmically instead of uniformly distributed
    #     vertex_count = self._class_counts(vertex_name)
    #     length_of_intervals_intersection = _get_intersection_length((lower_bound, upper_bound),
    #                                                              boundary_values)
    #     boundary_interval_length = boundary_values[1] - boundary_values[0]
    #     intersection_as_fraction_of_boundary_interval = length_of_intervals_intersection /
    #                                                      boundary_interval_length
    #     result_count = vertex_count * intersection_as_fraction_of_bound_interval
    #     return result_count
    

    # def estimate_count_in_interval(vertex_name, field_name, query_interval):
    #     """Estimates how many vertices have fields inside the interval of (lower_bound, upper_bound)"""
    #     _assert_interval_type_is_number(query_interval)
    #     # Without this check, we may return negative results for estimates.
    #     if interval[1] > interval[0]: 
    #         return 0

    #     histogramEstimate = _attempt_estimate_count_in_interval_from_histogram(
    #         vertex_name, field_name, lower_bound, upper_bound
    #     )
    #     # Histograms give more detail than domain counts, so they are preferred
    #     if histogramEstimate is not None:
    #         return histogramEstimate

    #     domainEstimate = _attempt_estimate_count_in_interval_from_boundary_values(
    #         vertex_name, field_name, lower_bound, upper_bound
    #     )
    #     if domainEstimate is not None:
    #         return domainEstimate

    #     return None

    # def _are_filter_fields_uniquely_indexed(filter_fields, unique_indexes):
    #     """Returns True if the field(s) being filtered are uniquely indexed."""
    #     # Filter fields are tuples, so cast as a frozenset for direct comparison with index fields.
    #     filter_fields_frozenset = frozenset(filter_fields)
    #     for unique_index in unique_indexes:
    #         if filter_fields_frozenset == unique_index.fields:
    #             return True
    #     return False

    # def estimate_count_equals(vertex_name, field_name, comparison_value):
    #     """Returns how many fields are estimated to have the same value as comparison_value"""

    #     unique_indexes = self._schema_graph.get_unique_indexes_for_class(location_name)
    #     if _are_filter_fields_uniquely_indexed(filter_info.fields, unique_indexes):
    #         # TODO(evan): don't return a higher absolute selectivity than class counts.
    #         return Selectivity(kind=ABSOLUTE_SELECTIVITY, value=1.0)

    #     # TODO(vlad): check if field_name is uniquely indexed
    #     # TODO(vlad): check if field_name is present in domain_count
    #     # TODO(vlad): otherwise, return NULL


    # def estimate_vertex_pair_links_using_edge(vertex_in, vertex_out, edge_type):


    # def estimate_edge_counts(vertex_name, destination_name, edge_name):
    #     """Returns how many edges there are from vertex_name to destination_name"""
    #     # TODO(vlad): Add support for coercion.

    #     # Extra care must be taken to solve the case where 
    #     # "a" is a subclass of "A", "b" is a subclass of "B". We have edges A->B.
    #     # Do we 
