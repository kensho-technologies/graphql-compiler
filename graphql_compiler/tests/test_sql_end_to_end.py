import unittest

import six

from graphql_compiler.compiler import compile_graphql_to_sql
from graphql_compiler.compiler.ir_lowering_sql.metadata import CompilerMetadata
from graphql_compiler.tests.test_helpers import (
    create_sqlite_db,
    get_schema
)


class SqlQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine, metadata = create_sqlite_db()
        compiler_metadata = CompilerMetadata(engine.dialect.name, metadata)
        cls.compiler_metadata = compiler_metadata
        cls.engine = engine
        cls.metadata = metadata
        cls.schema = get_schema()

    def assertQueryOutputEquals(self, graphql_string, params, expected_results):
        """Sort both query results and expected results deterministically before comparing."""
        compilation_result = compile_graphql_to_sql(
            self.schema, graphql_string, self.compiler_metadata
        )

        query = compilation_result.query
        results = [dict(result) for result in self.engine.execute(query.params(**params))]
        sort_order = []
        if len(expected_results) > 0:
            sort_order = sorted(six.iterkeys(expected_results[0]))
        # sort by True/False for None/Not None to avoid comparisons to None to a non None type
        key = lambda result: tuple((result[col] is not None, result[col]) for col in sort_order)
        results = sorted(results, key=key)
        expected_results = sorted(expected_results, key=key)
        self.assertListEqual(expected_results, results)

    def test_basic_query(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear'},
            {'name': 'Biggest Bear'},
            {'name': 'Little Bear'},
            {'name': 'Medium Bear'},
        ]

        self.assertQueryOutputEquals(graphql_string, {}, expected_results)

    def test_basic_filter(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear'},
        ]
        params = {
            '$name': 'Big Bear'
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_basic_filter_between(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "between", value: ["$lower", "$upper"])
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear'},
            {'name': 'Biggest Bear'},
        ]
        params = {
            '$lower': 'Big Bear',
            '$upper': 'Biggest Bear',
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_basic_tag_filter(self):
        graphql_string = '''
        {
            Animal {
                name @tag(tag_name: "parent_name")
                     @output(out_name: "parent_name")
                out_Animal_ParentOf {
                    name @filter(op_name: ">" value: ["%parent_name"])
                         @output(out_name: "child_name")
                }
            }
        }
        '''
        expected_results = [
            {'parent_name': 'Big Bear', 'child_name': 'Medium Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, {}, expected_results)

    def test_basic_tag_filter_optional(self):
        graphql_string = '''
        {
            Animal {
                name @tag(tag_name: "parent_name")
                     @output(out_name: "parent_name")
                out_Animal_ParentOf @optional {
                    name @filter(op_name: ">" value: ["%parent_name"])
                         @output(out_name: "child_name")
                }
            }
        }
        '''
        expected_results = [
            {'parent_name': 'Big Bear', 'child_name': 'Medium Bear'},
            {'parent_name': 'Little Bear', 'child_name': None},
        ]
        self.assertQueryOutputEquals(graphql_string, {}, expected_results)

    def test_basic_out_edge(self):
        expected_results = [
            {'name': 'Big Bear', 'location_name': 'Wisconsin'},
        ]
        params = {
            '$name': 'Big Bear'
        }
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                out_Animal_LivesIn {
                    name @output(out_name: "location_name")
                }
            }
        }
        '''
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

        graphql_string = '''
        {
            Location {
                name @output(out_name: "location_name")
                in_Animal_LivesIn {
                    name @output(out_name: "name")
                         @filter(op_name: "=", value: ["$name"])
                }
            }
        }
        '''
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_basic_optional_out_edge(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$names"])
                out_Animal_LivesIn @optional {
                    name @output(out_name: "location_name")
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'location_name': 'Wisconsin'},
            {'name': 'Biggest Bear', 'location_name': None},
        ]
        params = {
            '$names': ['Biggest Bear', 'Big Bear']
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_optional_out_edge_between(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$names"])
                out_Animal_LivesIn @optional {
                    name @output(out_name: "location_name")
                         @filter(op_name: "between", value: ["$lower", "$upper"])
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'location_name': 'Wisconsin'},
            {'name': 'Biggest Bear', 'location_name': None},
        ]
        params = {
            '$names': ['Biggest Bear', 'Big Bear'],
            '$lower': 'Wisconsin',
            '$upper': 'Wisconsin',
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_multiple_optional_out_edge(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$names"])
                out_Animal_LivesIn @optional {
                    name @output(out_name: "location_name")
                }
                in_Animal_ParentOf @optional {
                    name @output(out_name: "parent_name")
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'location_name': 'Wisconsin', 'parent_name': 'Biggest Bear'},
            {'name': 'Biggest Bear', 'location_name': None, 'parent_name': None},
        ]
        params = {
            '$names': ['Biggest Bear', 'Big Bear']
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_optional_with_expansion(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$names"])
                in_Animal_ParentOf @optional {
                    out_Animal_LivesIn {
                        name @output(out_name: "parent_location_name")
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'parent_location_name': None},
            {'name': 'Biggest Bear', 'parent_location_name': None},
            {'name': 'Medium Bear', 'parent_location_name': 'Wisconsin'}
        ]
        params = {
            '$names': ['Biggest Bear', 'Big Bear', 'Medium Bear']
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_optional_with_expansion_filter(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$names"])
                in_Animal_ParentOf @optional {
                    out_Animal_LivesIn {
                        name @output(out_name: "parent_location_name")
                             @filter(op_name: "=", value: ["$location"])
                    }
                }
            }
        }
        '''
        # Medium Bear is discarded, because while it's parent Big Bear has a location, it's location
        # is not Michigan, thus the result is discarded.
        expected_results = [
            {'name': 'Big Bear', 'parent_location_name': None},
            {'name': 'Biggest Bear', 'parent_location_name': None},
        ]
        params = {
            '$names': ['Biggest Bear', 'Big Bear', 'Medium Bear'],
            '$location': 'Michigan'
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_basic_self_edge_out(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                out_Animal_ParentOf {
                    name @output(out_name: "child_name")
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'child_name': 'Medium Bear'},
            {'name': 'Biggest Bear', 'child_name': 'Big Bear'},
            {'name': 'Medium Bear', 'child_name': 'Little Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, {}, expected_results)

    def test_depth_two_self_edge_out(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                out_Animal_ParentOf {
                    out_Animal_ParentOf {
                        name @output(out_name: "grandchild_name")
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'grandchild_name': 'Little Bear'},
            {'name': 'Biggest Bear', 'grandchild_name': 'Medium Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, {}, expected_results)

    def test_deep_self_edge(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                out_Animal_ParentOf {
                    name @output(out_name: "child_name")
                    out_Animal_ParentOf {
                        name @output(out_name: "grandchild_name")
                        out_Animal_ParentOf {
                            name @output(out_name: "great_grandchild_name")
                        }
                    }
                }
            }
        }
        '''
        expected_results = [
            {
                'name': 'Biggest Bear',
                'child_name': 'Big Bear',
                'grandchild_name': 'Medium Bear',
                'great_grandchild_name': 'Little Bear'
            },
        ]
        self.assertQueryOutputEquals(graphql_string, {}, expected_results)

    def test_basic_recurse_in(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                in_Animal_ParentOf @recurse(depth: 3){
                    name @output(out_name: "ancestor")
                }
            }
        }
        '''
        params = {
            '$bear_name': 'Little Bear'
        }
        expected_results = [
            {'name': 'Little Bear', 'ancestor': 'Big Bear'},
            {'name': 'Little Bear', 'ancestor': 'Biggest Bear'},
            {'name': 'Little Bear', 'ancestor': 'Little Bear'},
            {'name': 'Little Bear', 'ancestor': 'Medium Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_basic_recurse_with_post_filter(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                in_Animal_ParentOf @recurse(depth: 3){
                    name @output(out_name: "ancestor")
                         @filter(op_name: "=", value: ["$ancestor_name"])
                }
            }
        }
        '''
        params = {
            '$bear_name': 'Little Bear',
            '$ancestor_name': 'Biggest Bear'
        }
        expected_results = [
            {'name': 'Little Bear', 'ancestor': 'Biggest Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_recurse_with_tag_post_filter(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @tag(tag_name: "ancestor_name")
                     @filter(op_name: "=", value: ["$bear_name"])
                in_Animal_ParentOf @recurse(depth: 3){
                    name @output(out_name: "ancestor")
                         @filter(op_name: ">", value: ["%ancestor_name"])
                }
            }
        }
        '''
        params = {
            '$bear_name': 'Little Bear',
        }
        expected_results = [
            {'name': 'Little Bear', 'ancestor': 'Medium Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_basic_recurse_limit_depth(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                in_Animal_ParentOf @recurse(depth: 1){
                    name @output(out_name: "ancestor")
                }
            }
        }
        '''
        params = {
            '$bear_name': 'Little Bear'
        }
        expected_results = [
            {'name': 'Little Bear', 'ancestor': 'Little Bear'},
            {'name': 'Little Bear', 'ancestor': 'Medium Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_basic_recurse_out(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                out_Animal_ParentOf @recurse(depth: 3){
                    name @output(out_name: "descendant")
                }
            }
        }
        '''
        params = {
            '$bear_name': 'Biggest Bear'
        }
        expected_results = [
            {'name': 'Biggest Bear', 'descendant': 'Big Bear'},
            {'name': 'Biggest Bear', 'descendant': 'Biggest Bear'},
            {'name': 'Biggest Bear', 'descendant': 'Little Bear'},
            {'name': 'Biggest Bear', 'descendant': 'Medium Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_recurse_and_traverse(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                out_Animal_ParentOf @recurse(depth: 3){
                    name @output(out_name: "descendant")
                }
                out_Animal_LivesIn {
                    name @output(out_name: "home")
                }
            }
        }
        '''
        params = {
            '$bear_name': 'Big Bear'
        }
        expected_results = [
            {'name': 'Big Bear', 'descendant': 'Big Bear', 'home': 'Wisconsin'},
            {'name': 'Big Bear', 'descendant': 'Little Bear', 'home': 'Wisconsin'},
            {'name': 'Big Bear', 'descendant': 'Medium Bear', 'home': 'Wisconsin'},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_recurse_and_optional_traverse(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$bear_names"])
                out_Animal_ParentOf @recurse(depth: 3){
                    name @output(out_name: "descendant")
                }
                out_Animal_LivesIn @optional {
                    name @output(out_name: "home")
                }
            }
        }
        '''
        params = {
            '$bear_names': ['Biggest Bear', 'Big Bear']
        }
        expected_results = [
            {'name': 'Big Bear', 'descendant': 'Big Bear', 'home': 'Wisconsin'},
            {'name': 'Big Bear', 'descendant': 'Little Bear', 'home': 'Wisconsin'},
            {'name': 'Big Bear', 'descendant': 'Medium Bear', 'home': 'Wisconsin'},
            {'name': 'Biggest Bear', 'descendant': 'Big Bear', 'home': None},
            {'name': 'Biggest Bear', 'descendant': 'Biggest Bear', 'home': None},
            {'name': 'Biggest Bear', 'descendant': 'Little Bear', 'home': None},
            {'name': 'Biggest Bear', 'descendant': 'Medium Bear', 'home': None},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_nested_recurse(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                out_Animal_ParentOf {
                    name @output(out_name: "child")
                    out_Animal_ParentOf @recurse(depth: 3){
                        name @output(out_name: "child_or_descendant")
                    }
                }
            }
        }
        '''
        params = {
            '$bear_name': 'Biggest Bear'
        }
        expected_results = [
            {'name': 'Biggest Bear', 'child': 'Big Bear', 'child_or_descendant': 'Big Bear'},
            {'name': 'Biggest Bear', 'child': 'Big Bear', 'child_or_descendant': 'Little Bear'},
            {'name': 'Biggest Bear', 'child': 'Big Bear', 'child_or_descendant': 'Medium Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_nested_recurse_with_tag(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$bear_names"])
                out_Animal_ParentOf {
                    name @output(out_name: "child")
                         @tag(tag_name: "child_name")
                    out_Animal_ParentOf @recurse(depth: 3){
                        name @output(out_name: "child_or_descendant")
                             @filter(op_name: "=", value: ["%child_name"])
                    }
                }
            }
        }
        '''
        params = {
            '$bear_names': ['Biggest Bear', 'Little Bear']
        }
        expected_results = [
            {'name': 'Biggest Bear', 'child': 'Big Bear', 'child_or_descendant': 'Big Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_nested_recurse_with_tag_optional(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$bear_names"])
                out_Animal_ParentOf @optional {
                    name @tag(tag_name: "child_name")
                    out_Animal_ParentOf @recurse(depth: 3){
                        name @output(out_name: "child_or_descendant")
                             @filter(op_name: "=", value: ["%child_name"])
                    }
                }
            }
        }
        '''
        params = {
            '$bear_names': ['Biggest Bear', 'Little Bear']
        }
        expected_results = [
            {'name': 'Biggest Bear', 'child_or_descendant': 'Big Bear'},
            {'name': 'Little Bear', 'child_or_descendant': None},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_nested_recurse_with_tag_junction(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$bear_names"])
                out_Animal_FriendsWith {
                    name @tag(tag_name: "friend_name")
                    out_Animal_FriendsWith @recurse(depth: 3){
                        name @output(out_name: "friend_or_friend_of_friend")
                             @filter(op_name: "=", value: ["%friend_name"])
                    }
                }
            }
        }
        '''
        params = {
            '$bear_names': ['Biggest Bear', 'Little Bear']
        }
        expected_results = [
            {'name': 'Biggest Bear', 'friend_or_friend_of_friend': 'Medium Bear'},
            {'name': 'Little Bear', 'friend_or_friend_of_friend': 'Big Bear'},
            {'name': 'Little Bear', 'friend_or_friend_of_friend': 'Biggest Bear'}
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_recurse_out_and_in(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$bear_names"])
                out_Animal_ParentOf @recurse(depth: 3){
                    name @output(out_name: "descendant")
                }
                in_Animal_ParentOf @recurse(depth: 3){
                    name @output(out_name: "ancestor")
                }
            }
        }
        '''
        params = {
            '$bear_names': ['Biggest Bear', 'Little Bear']
        }
        # note that Biggest Bears only recursive ancestor is himself
        # and that Little Bear's only recursive descendant is himself
        expected_results = [
            {'name': 'Biggest Bear', 'descendant': 'Big Bear', 'ancestor': 'Biggest Bear'},
            {'name': 'Biggest Bear', 'descendant': 'Biggest Bear', 'ancestor': 'Biggest Bear'},
            {'name': 'Biggest Bear', 'descendant': 'Little Bear', 'ancestor': 'Biggest Bear'},
            {'name': 'Biggest Bear', 'descendant': 'Medium Bear', 'ancestor': 'Biggest Bear'},
            {'name': 'Little Bear', 'descendant': 'Little Bear', 'ancestor': 'Big Bear'},
            {'name': 'Little Bear', 'descendant': 'Little Bear', 'ancestor': 'Biggest Bear'},
            {'name': 'Little Bear', 'descendant': 'Little Bear', 'ancestor': 'Little Bear'},
            {'name': 'Little Bear', 'descendant': 'Little Bear', 'ancestor': 'Medium Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)


    def test_basic_in_edge(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                in_Animal_ParentOf {
                    name @output(out_name: "parent_name")
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'parent_name': 'Biggest Bear'},
            {'name': 'Little Bear', 'parent_name': 'Medium Bear'},
            {'name': 'Medium Bear', 'parent_name': 'Big Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, {}, expected_results)

    def test_basic_recurse_with_expansion(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                out_Animal_ParentOf @recurse(depth: 3){
                    name @output(out_name: "descendant")
                    in_Animal_ParentOf @optional {
                        name @output(out_name: "descendant_parent")
                    }
                }
            }
        }
        '''
        params = {
            '$bear_name': 'Biggest Bear'
        }
        expected_results = [
            {
                'name': 'Biggest Bear',
                'descendant': 'Big Bear',
                'descendant_parent': 'Biggest Bear',
            },
            {
                'name': 'Biggest Bear',
                'descendant': 'Biggest Bear',
                'descendant_parent': None,
            },
            {
                'name': 'Biggest Bear',
                'descendant': 'Little Bear',
                'descendant_parent': 'Medium Bear',
            },
            {
                'name': 'Biggest Bear',
                'descendant': 'Medium Bear',
                'descendant_parent': 'Big Bear',
            },
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_basic_recurse_with_expansion_and_tag(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                out_Animal_ParentOf @recurse(depth: 3){
                    name @output(out_name: "descendant")
                         @tag(tag_name: "descendant_name")
                    out_Animal_ParentOf {
                        name @output(out_name: "descendant_child")
                             @filter(op_name: ">", value: ["%descendant_name"])
                    }
                }
            }
        }
        '''
        params = {
            '$bear_name': 'Biggest Bear'
        }
        expected_results = [
            {'name': 'Biggest Bear', 'descendant': 'Big Bear', 'descendant_child': 'Medium Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_basic_recurse_with_filtered_nested_expansion(self):
        # the filter using a tag below should be a no-op, since we traverse forward and then back
        # over the edge
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                out_Animal_ParentOf @recurse(depth: 3){
                    name @output(out_name: "descendant")
                         @tag(tag_name: "descendant")
                    in_Animal_ParentOf @optional {
                        name @output(out_name: "descendant_parent")
                        out_Animal_ParentOf {
                            name @output(out_name: "same_as_descendant")
                                 @filter(op_name: "=", value: ["%descendant"])
                        }
                    }
                }
            }
        }
        '''
        params = {
            '$bear_name': 'Biggest Bear',
        }
        expected_results = [
            {
                'name': 'Biggest Bear',
                'descendant': 'Big Bear',
                'same_as_descendant': 'Big Bear',
                'descendant_parent': 'Biggest Bear',
            },
            {
                'name': 'Biggest Bear',
                'descendant': 'Biggest Bear',
                'same_as_descendant': None,
                'descendant_parent': None,
            },
            {
                'name': 'Biggest Bear',
                'descendant': 'Little Bear',
                'same_as_descendant': 'Little Bear',
                'descendant_parent': 'Medium Bear',
            },
            {
                'name': 'Biggest Bear',
                'descendant': 'Medium Bear',
                'same_as_descendant': 'Medium Bear',
                'descendant_parent': 'Big Bear',
            },
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_recursion_in_recursion_with_expansion(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                in_Animal_ParentOf @recurse(depth: 1){
                    name @output(out_name: "ancestor")
                    out_Animal_ParentOf @recurse(depth: 1) {
                        name @output(out_name: "ancestor_or_ancestor_child")
                        out_Animal_Eats @optional {
                            ... on Food {
                                name @output(out_name: "ancestor_or_ancestor_child_eats")
                            }
                        }
                    }
                }
            }
        }
        '''
        params = {
            '$bear_name': 'Little Bear'
        }
        expected_results = [
            {
                'name': 'Little Bear',
                'ancestor': 'Little Bear',
                'ancestor_or_ancestor_child': 'Little Bear',
                'ancestor_or_ancestor_child_eats': None
            },
            {
                'name': 'Little Bear',
                'ancestor': 'Medium Bear',
                'ancestor_or_ancestor_child': 'Little Bear',
                'ancestor_or_ancestor_child_eats': None
            },
            {
                'name': 'Little Bear',
                'ancestor': 'Medium Bear',
                'ancestor_or_ancestor_child': 'Medium Bear',
                'ancestor_or_ancestor_child_eats': 'Gummy Bears'
            },
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_recursion_in_recursion_with_deep_tag(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                     @tag(tag_name: "name")
                in_Animal_ParentOf @recurse(depth: 1){
                    name @output(out_name: "self_or_parent")
                    out_Animal_ParentOf @recurse(depth: 1) {
                        name @output(out_name: "ancestor_or_self")
                             @filter(op_name: "=", value: ["%name"])
                    }
                }
            }
        }
        '''
        params = {
            '$bear_name': 'Little Bear'
        }
        # with the recurse out and back, the query can either stay at little bear both times
        # or it can traverse out to little bear's parent, and then back to little bear
        # creating two results
        expected_results = [
            {
                'name': 'Little Bear',
                'self_or_parent': 'Little Bear',
                'ancestor_or_self': 'Little Bear',
            },
            {
                'name': 'Little Bear',
                'self_or_parent': 'Medium Bear',
                'ancestor_or_self': 'Little Bear',
            },
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_double_recursion_in_recursion_tags(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                     @tag(tag_name: "name")
                in_Animal_ParentOf @recurse(depth: 1){
                    name @output(out_name: "self_or_ancestor")
                         @filter(op_name: ">", value: ["%name"])
                    out_Animal_ParentOf @recurse(depth: 1) {
                        name @output(out_name: "ancestor_or_ancestor_child")
                             @filter(op_name: ">", value: ["%name"])
                    }
                    in_Animal_ParentOf @recurse(depth: 1) {
                        name @output(out_name: "ancestor_or_ancestor_parent")
                             @filter(op_name: ">", value: ["%name"])
                    }
                }
            }
        }
        '''
        params = {
            '$bear_name': 'Little Bear'
        }
        expected_results = [
            {
                'name': 'Little Bear',
                'self_or_ancestor': 'Medium Bear',
                'ancestor_or_ancestor_child': 'Medium Bear',
                'ancestor_or_ancestor_parent': 'Medium Bear'
            },
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_basic(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                out_Animal_Eats {
                    ... on Food {
                        name @output(out_name: "food_name")
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'food_name': 'Apples'},
            {'name': 'Big Bear', 'food_name': 'Caramel Apples'},
            {'name': 'Big Bear', 'food_name': 'Gummy Bears'},
        ]
        params = {
            '$name': 'Big Bear'
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_basic_in(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "friends_name")
                     @filter(op_name: "=", value: ["$name"])
                in_Animal_FriendsWith {
                    name @output(out_name: "name")
                }
            }
        }
        '''
        expected_results = [
            {
                'friends_name': 'Big Bear',
                'name': 'Little Bear'
            },
        ]
        params = {
            '$name': 'Big Bear'
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_union(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                out_Animal_Eats {
                    ... on Food {
                        name @output(out_name: "food_name")
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Medium Bear', 'food_name': 'Gummy Bears'},
        ]
        params = {
            '$name': 'Medium Bear'
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_union_optional(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$names"])
                out_Animal_Eats @optional {
                    ... on Food {
                        name @output(out_name: "food_name")
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Medium Bear', 'food_name': 'Gummy Bears'},
            {'name': 'Biggest Bear', 'food_name': None},
        ]
        params = {
            '$names': ['Medium Bear', 'Biggest Bear']
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_basic_optional(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$names"])
                out_Animal_Eats @optional {
                    ... on Food {
                        name @output(out_name: "food_name")
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'food_name': 'Apples'},
            {'name': 'Big Bear', 'food_name': 'Caramel Apples'},
            {'name': 'Big Bear', 'food_name': 'Gummy Bears'},
            {'name': 'Little Bear', 'food_name': None}
        ]
        params = {
            '$names': ['Big Bear', 'Little Bear']
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_tag(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                     @tag(tag_name: "animal_name")
                out_Animal_Eats {
                    ... on Food {
                        name @output(out_name: "food_name")
                             @filter(op_name: "<", value: ["%animal_name"])
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'food_name': 'Apples'},
        ]
        params = {
            '$name': 'Big Bear'
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_self(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                out_Animal_FriendsWith {
                    name @output(out_name: "friend_name")
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Little Bear', 'friend_name': 'Big Bear'},
            {'name': 'Little Bear', 'friend_name': 'Biggest Bear'},
        ]
        params = {
            '$name': 'Little Bear',
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_self_union(self):
        graphql_string = '''
        {
            Species {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                out_Species_Eats {
                    ... on Species {
                        name @output(out_name: "eaten_species")
                    
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Bear', 'eaten_species': 'Rabbit'},
        ]
        params = {
            '$name': 'Bear',
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_recursive(self):
        # recursion is very high below to make sure cycle detection is working
        # if it is not, the query below will fail because it will continually traverse the
        # medium bear -> friends with -> medium bear edge and or the
        # medium bear -> friends with -> biggest bear -> friends with -> medium bear edge
        # exceeding the maximum recursions allowed by the DB
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                out_Animal_FriendsWith @recurse(depth: 150) {
                    name @output(out_name: "self_or_friend_name")
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Little Bear', 'self_or_friend_name': 'Big Bear'},
            {'name': 'Little Bear', 'self_or_friend_name': 'Biggest Bear'},
            {'name': 'Little Bear', 'self_or_friend_name': 'Little Bear'},
            {'name': 'Little Bear', 'self_or_friend_name': 'Medium Bear'},
        ]
        params = {
            '$name': 'Little Bear',
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_recursive_in_expansion(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                in_Animal_FriendsWith @recurse(depth: 1) {
                    name @output(out_name: "self_or_friend_name")
                    out_Animal_Eats {
                        ... on Food {
                            name @output(out_name: "self_or_friend_eats")
                        }
                    }
                }
            }
        }
        '''
        expected_results = [
            {
                'name': 'Biggest Bear',
                'self_or_friend_name': 'Medium Bear',
                'self_or_friend_eats': 'Gummy Bears',
            },
        ]
        params = {
            '$name': 'Biggest Bear',
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_optional_tag(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                in_Animal_FriendsWith @optional {
                    out_Animal_FriendsWith {
                        out_Animal_FriendsWith {
                            name @output(out_name: "friend_of_friend_of_friend")
                            out_Animal_Eats {
                                ... on Food {
                                    name @output(out_name: "friend_of_friend_of_friend_eats")
                                         @tag(tag_name: "friend_of_friend_of_friend_eats")
                                }
                            }
                        
                        }
                    }
                }
                out_Animal_Eats @optional {
                    ... on Food {
                        name @filter(op_name: "=", value: ["%friend_of_friend_of_friend_eats"])
                    }
                }
            }
        }
        '''
        expected_results = [
            {
                'name': 'Big Bear',
                'friend_of_friend_of_friend': None,
                'friend_of_friend_of_friend_eats': None,
            },
            {
                'name': 'Big Bear',
                'friend_of_friend_of_friend': None,
                'friend_of_friend_of_friend_eats': None,
            },
            {
                'name': 'Big Bear',
                'friend_of_friend_of_friend': None,
                'friend_of_friend_of_friend_eats': None,
            },
            {
                'name': 'Big Bear',
                'friend_of_friend_of_friend': 'Medium Bear',
                'friend_of_friend_of_friend_eats': 'Gummy Bears'
            },
        ]
        params = {
            '$name': 'Big Bear'
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)
