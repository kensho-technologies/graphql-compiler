
class GraphQLStatistics(object):
	"""Provides estimates for GraphQL object counts and directive result size

	For the purposes of query cost estimation, we need information about how many results certain
	operations produce. Provided statistics, the class estimates the operation's result size.
	We plan to support vertex counts, edge counts, field domain counts, unique_indexed elements, 
	histograms, and type coercion.

	We also plan to add support for dynamic statistic gathering e.g. if a statistic is not provided,
	this class would also be able to issue GraphQL queries to provide better estimates.
	"""

	def __init__(schema_graph, class_counts, domain_counts, previous_directive_usage, histograms):
		"""Initializes the class with the given statistics.

		Args:
			schema_graph: SchemaGraph object
	        class_counts: function, string -> int, that accepts a class name and returns the
                          total number of instances plus subclass instances
			domain_counts: function, (string, string) -> int, that accepts a class name and a
						   valid vertex field, and returns the number of different values the vertex
						   field has.
			previous_directive_usage: function, (string, GraphQLDirective instance) -> int, accepts 
									  a class name and the directive that was applied, and returns 
									  the previous directive size. 
			histograms: function, (string, string) -> [(float, float, float)], that accepts a class
						name and a valid vertex field, and returns a list containing tuple 
						describing each histogram entry as (start of bucket range, end of bucket 
						range, element count)
		"""

		self._schema_graph = schema_graph
		self._class_counts = class_counts
		self._domain_counts = domain_counts
		self._previous_usage = previous_directive_usage
		self._histograms = histograms
	    self.unique_indexes = schema_graph.get_unique_indexes_for_class(location_name)

	def estimate_directive_result_size(parent_entity, directive):
		if 
		# TODO(vlad): For @filter, consider domain_count, unique_indexes, histogram
		pass

	def estimate_traversal_result_size():
		# TODO(vlad): Add support for coercion.

		# Extra care must be taken to solve the case where 
		# "a" is a subclass of "A", "b" is a subclass of "B". We have edges A->B.
		# Do we 

		pass