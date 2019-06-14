from collections import namedtuple


##
# A GraphQLStatistics object bundles statistics function regarding GraphQL objects and vertex field
# values.
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
    if statistics.class_count is None:
        return None
    return statistics.class_count(name)


def _get_concrete_vertex_links_count(statistics, concrete_vertex_in_name, concrete_vertex_out_name,
                                     edge_name):
    """Return number of edges of a given type connecting two concrete vertices of given types."""
    if statistics.concrete_vertex_links is None:
        return None
    return statistics.concrete_vertex_links(concrete_vertex_in_name, concrete_vertex_out_name,
                                            edge_name)


def _get_domain_count(statistics, vertex_name, field_name):
    if statistics.domain_count is None:
        return None
    return statistics.domain_count(vertex_name, field_name)


def _get_histogram(statistics, vertex_name, field_name):
    if statistics.histogram is None:
        return None
    return statistics.histogram(vertex_name, field_name)
