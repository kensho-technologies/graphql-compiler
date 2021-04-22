# Copyright 2017-present Kensho Technologies, LLC.
import unittest

from . import test_input_data
from ..query_decomposition import try_express_as_bounded_query


class QueryDecompositionTests(unittest.TestCase):
    """Ensure valid queries are decomposed if possible."""

    def setUp(self):
        """Initialize the test schema once for all tests, and disable max diff limits."""
        self.maxDiff = None
        self.schema = get_schema()

    def test_immediate_output(self):
        test_data = test_input_data.immediate_output()

        # TODO Do I get bounded query from IR or from AST?

        bounded_expression_result = try_express_as_bounded_query()
