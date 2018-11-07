# Copyright 2018-present Kensho Technologies, LLC.
import sqlite3
import unittest

import six
from sqlalchemy import text

from .. import exceptions, graphql_to_sql
from ..compiler import compile_graphql_to_sql
from ..compiler.ir_lowering_sql.metadata import CompilerMetadata
from ..tests.test_helpers import create_misconfigured_sqlite_db, create_sqlite_db, get_schema


class SqlQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine, metadata = create_sqlite_db()
        compiler_metadata = CompilerMetadata(engine.dialect.name, metadata)
        cls.compiler_metadata = compiler_metadata
        cls.engine = engine
        cls.metadata = metadata
        cls.schema = get_schema()
        cls.maxDiff = None

    def assertQueryOutputEquals(self, graphql_string, params, expected_results):
        """Sort both query results and expected results deterministically before comparing."""
        query = self.compile_query(graphql_string, params)

        results = [dict(result) for result in self.engine.execute(query)]
        sort_order = []
        if len(expected_results) > 0:
            sort_order = sorted(six.iterkeys(expected_results[0]))

        def sort_key(result):
            """Convert None/Not None to avoid comparisons to None to a non None type"""
            return tuple((result[col] is not None, result[col]) for col in sort_order)

        results = sorted(results, key=sort_key)
        expected_results = sorted(expected_results, key=sort_key)
        self.assertListEqual(expected_results, results)

    def compile_query(self, graphql_string, query_params):
        compilation_result = graphql_to_sql(
            self.schema, graphql_string, query_params, self.compiler_metadata)
        return compilation_result.query

    def test_sqlite(self):
        list(self.engine.execute(text('SELECT 1')))

    def test_sqlite_cte(self):
        list(self.engine.execute(text('WITH result AS (SELECT 1 as num) SELECT num FROM result')))

    def test_sqlite_version(self):
        # this is the version of Sqlite that introduced CTEs
        self.assertGreaterEqual(sqlite3.sqlite_version_info, (3, 8, 3))

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

    def test_typename_error(self):
        # the __typename metafield is currently unsupported
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                __typename @output(out_name: "animal_type")
            }
        }
        '''
        with self.assertRaises(exceptions.GraphQLNotSupportedByBackendError):
            self.compile_query(graphql_string, {})

    def test_unsupported_filter(self):
        # intersects is not a supported filtering operation
        graphql_string = '''
        {
            Animal {
                alias @output(out_name: "alias")
                      @filter(op_name: "intersects", value: ["$collection"])
            }
        }
        '''
        with self.assertRaises(exceptions.GraphQLNotSupportedByBackendError):
            self.compile_query(graphql_string, {})

    def test_unsupported_filter_on_edge(self):
        graphql_string = '''
        {
            Species {
                name @output(out_name: "species_name")

                in_Animal_OfSpecies {
                    name @output(out_name: "parent_name")

                    in_Animal_ParentOf @filter(op_name: "has_edge_degree", value: ["$child_count"])
                                       @optional {
                        name @output(out_name: "child_name")
                    }
                }
            }
        }
        '''
        with self.assertRaises(exceptions.GraphQLNotSupportedByBackendError):
            compile_graphql_to_sql(self.schema, graphql_string, self.compiler_metadata)

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
            'name': 'Big Bear'
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
            'lower': 'Big Bear',
            'upper': 'Biggest Bear',
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

    def test_out_edge_equivalent_in_edge(self):
        expected_results = [
            {'name': 'Big Bear', 'location_name': 'Wisconsin'},
        ]
        params = {
            'name': 'Big Bear'
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
            'names': ['Biggest Bear', 'Big Bear']
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
            'names': ['Biggest Bear', 'Big Bear'],
            'lower': 'Wisconsin',
            'upper': 'Wisconsin',
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
            'names': ['Biggest Bear', 'Big Bear']
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
            # Big Bear has parent Biggest Bear, who does not satisfy the out_Animal_LivesIn edge
            {'name': 'Biggest Bear', 'parent_location_name': None},
            {'name': 'Medium Bear', 'parent_location_name': 'Wisconsin'}
        ]
        params = {
            'names': ['Biggest Bear', 'Big Bear', 'Medium Bear']
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
            # Medium bear has parent Big Bear, who lives in Wisconsin (not the filtered Michigan)
            {'name': 'Biggest Bear', 'parent_location_name': None},
        ]
        params = {
            'names': ['Biggest Bear', 'Big Bear', 'Medium Bear'],
            'location': 'Michigan'
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

    def test_basic_self_edge_in(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "child_name")
                in_Animal_ParentOf {
                    name @output(out_name: "parent_name")
                }
            }
        }
        '''
        expected_results = [
            {'parent_name': 'Big Bear', 'child_name': 'Medium Bear'},
            {'parent_name': 'Biggest Bear', 'child_name': 'Big Bear'},
            {'parent_name': 'Medium Bear', 'child_name': 'Little Bear'},
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
            'bear_name': 'Little Bear'
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
            'bear_name': 'Little Bear',
            'ancestor_name': 'Biggest Bear'
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
            'bear_name': 'Little Bear',
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
            'bear_name': 'Little Bear'
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
                out_Animal_ParentOf @recurse(depth: 4){
                    name @output(out_name: "descendant")
                }
            }
        }
        '''
        params = {
            'bear_name': 'Biggest Bear'
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
            'bear_name': 'Big Bear'
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
            'bear_names': ['Biggest Bear', 'Big Bear']
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
            'bear_name': 'Biggest Bear'
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
            'bear_names': ['Biggest Bear', 'Little Bear']
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
            'bear_names': ['Biggest Bear', 'Little Bear']
        }
        expected_results = [
            {'name': 'Biggest Bear', 'child_or_descendant': 'Big Bear'},
            {'name': 'Little Bear', 'child_or_descendant': None},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_nested_optional(self):
        graphql_string = '''{
            Animal {
                name @output(out_name: "animal_name")
                in_Animal_ParentOf @optional {
                    name @output(out_name: "parent_name")
                    out_Animal_ParentOf @optional {
                        name @output(out_name: "animal_name_again")
                        out_Animal_OfSpecies @optional {
                            name @output(out_name: "animal_species")
                                 @filter(op_name: "has_substring", value: ["$species_substring"])
                        }
                    }
                }
            }
        }'''
        params = {'species_substring': 'ear'}
        expected_results = [
            {
                'animal_name': 'Biggest Bear',
                'parent_name': None,
                'animal_name_again': None,
                'animal_species': None,
            },
            {
                'animal_name': 'Big Bear',
                'parent_name': 'Biggest Bear',
                'animal_name_again': 'Big Bear',
                'animal_species': 'Bear'
            },
            {
                'animal_name': 'Medium Bear',
                'parent_name': 'Big Bear',
                'animal_name_again': 'Medium Bear',
                'animal_species': 'Bear'
            },
            # little bear does not have a species recorded
            {
                'animal_name': 'Little Bear',
                'parent_name': 'Medium Bear',
                'animal_name_again': 'Little Bear',
                'animal_species': None,
            },
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_nested_recurse_with_optional_tag_junction(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$bear_names"])
                     out_Animal_OfSpecies @optional {
                        name @output(out_name: "species_name")
                             @tag(tag_name: "species_name")
                     }
                out_Animal_FriendsWith {
                    name @output(out_name: "friend_name")
                    out_Animal_FriendsWith @recurse(depth: 1){
                        name @output(out_name: "friend_or_friend_of_friend")
                             @filter(op_name: "=", value: ["%species_name"])
                    }
                }
            }
        }
        '''
        params = {
            'bear_names': ['Biggest Bear', 'Little Bear']
        }
        # only results starting with Little Bear are kept because Little Bear has no species
        # Biggest Bear has a species Bear which does not equal any animal names
        expected_results = [
            {
                'friend_name': 'Big Bear',
                'friend_or_friend_of_friend': 'Big Bear',
                'name': 'Little Bear',
                'species_name': None,
            },
            {
                'friend_name': 'Biggest Bear',
                'friend_or_friend_of_friend': 'Medium Bear',
                'name': 'Little Bear',
                'species_name': None,
            },
            {
                'friend_name': 'Biggest Bear',
                'friend_or_friend_of_friend': 'Biggest Bear',
                'name': 'Little Bear',
                'species_name': None,
            },
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
            'bear_names': ['Biggest Bear', 'Little Bear']
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
            'bear_name': 'Biggest Bear'
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
            'bear_name': 'Biggest Bear'
        }
        expected_results = [
            {'name': 'Biggest Bear', 'descendant': 'Big Bear', 'descendant_child': 'Medium Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_basic_recurse_with_nested_expansion_filtered_tag(self):
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
            'bear_name': 'Biggest Bear',
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
                        out_Animal_ImportantEvent @optional {
                            ... on Event {
                                name @output(out_name: "ancestor_or_ancestor_child_event_name")
                                     @filter(op_name: "has_substring", value: ["$eats_substring"])
                            }
                        }
                    }
                }
            }
        }
        '''
        params = {
            'bear_name': 'Little Bear',
            'eats_substring': 'Morn',
        }
        expected_results = [
            {
                'name': 'Little Bear',
                'ancestor': 'Little Bear',
                'ancestor_or_ancestor_child': 'Little Bear',
                'ancestor_or_ancestor_child_event_name': None
            },
            {
                'name': 'Little Bear',
                'ancestor': 'Medium Bear',
                'ancestor_or_ancestor_child': 'Little Bear',
                'ancestor_or_ancestor_child_event_name': None
            },
            {
                'name': 'Little Bear',
                'ancestor': 'Medium Bear',
                'ancestor_or_ancestor_child': 'Medium Bear',
                'ancestor_or_ancestor_child_event_name': 'Morning Feed Event'
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
            'bear_name': 'Little Bear'
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
            'bear_name': 'Little Bear'
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
                out_Animal_ImportantEvent {
                    ... on Event {
                        name @output(out_name: "event_name")
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'event_name': 'Morning Feed Event'},
            {'name': 'Big Bear', 'event_name': 'Afternoon Feed Event'},
            {'name': 'Big Bear', 'event_name': 'Night Feed Event'},
        ]
        params = {
            'name': 'Big Bear'
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
            'name': 'Big Bear'
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_union(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                out_Animal_ImportantEvent {
                    ... on Event {
                        name @output(out_name: "event_name")
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Medium Bear', 'event_name': 'Morning Feed Event'},
        ]
        params = {
            'name': 'Medium Bear'
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_union_optional(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$names"])
                out_Animal_ImportantEvent @optional {
                    ... on Event {
                        name @output(out_name: "event_name")
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Medium Bear', 'event_name': 'Morning Feed Event'},
            {'name': 'Biggest Bear', 'event_name': None},
        ]
        params = {
            'names': ['Medium Bear', 'Biggest Bear']
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_basic_optional(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$names"])
                out_Animal_ImportantEvent @optional {
                    ... on Event {
                        name @output(out_name: "event_name")
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'event_name': 'Morning Feed Event'},
            {'name': 'Big Bear', 'event_name': 'Afternoon Feed Event'},
            {'name': 'Big Bear', 'event_name': 'Night Feed Event'},
            {'name': 'Little Bear', 'event_name': None}
        ]
        params = {
            'names': ['Big Bear', 'Little Bear']
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_tag(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                     @tag(tag_name: "animal_name")
                out_Animal_ImportantEvent {
                    ... on Event {
                        name @output(out_name: "event_name")
                             @filter(op_name: "<", value: ["%animal_name"])
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'event_name': 'Afternoon Feed Event'},
        ]
        params = {
            'name': 'Big Bear'
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

        graphql_string = '''
        {
            Event {
                name @output(out_name: "event_name")
                     @tag(tag_name: "event_name")
                in_Animal_ImportantEvent {
                    name @output(out_name: "name")
                         @filter(op_name: "=", value: ["$name"])
                         @filter(op_name: ">", value: ["%event_name"])
                }
            }
        }
        '''
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_tag_flipped(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                     @tag(tag_name: "animal_name")
                out_Animal_ImportantEvent {
                    ... on Event {
                        name @output(out_name: "event_name")
                             @filter(op_name: "<", value: ["%animal_name"])
                    }
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Big Bear', 'event_name': 'Afternoon Feed Event'},
        ]
        params = {
            'name': 'Big Bear'
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
            'name': 'Little Bear',
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_self_union(self):
        graphql_string = '''
        {
            Species {
                name @output(out_name: "name")
                out_Species_Eats @optional {
                    ... on Species {
                        name @output(out_name: "eats")
                    }
                }
                in_Species_Eats @optional {
                    name @output(out_name: "eaten_by")
                }
                out_Species_EatenBy @optional {
                    name @output(out_name: "eaten_by_other_way")
                }
            }
        }
        '''
        expected_results = [
            {'name': 'Bear', 'eats': 'Rabbit', 'eaten_by': None, 'eaten_by_other_way': None},
            {'name': 'Rabbit', 'eats': None, 'eaten_by': 'Bear', 'eaten_by_other_way': 'Bear'},
        ]
        self.assertQueryOutputEquals(graphql_string, {}, expected_results)

    def test_many_to_many_junction_recursive_basic_cycle(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                out_Animal_FriendsWith @recurse(depth: 3) {
                    name @output(out_name: "self_or_friend_name")
                }
            }
        }
        '''
        expected_results = [
            # Biggest bear
            {'name': 'Biggest Bear', 'self_or_friend_name': 'Biggest Bear'},
            # Biggest bear -> Medium bear
            {'name': 'Biggest Bear', 'self_or_friend_name': 'Medium Bear'},
            # Biggest bear -> Medium bear -> Medium bear
            {'name': 'Biggest Bear', 'self_or_friend_name': 'Medium Bear'},
            # Biggest bear -> Medium bear -> Biggest bear
            {'name': 'Biggest Bear', 'self_or_friend_name': 'Biggest Bear'},
            # Biggest bear -> Medium bear -> Medium bear -> Medium Bear
            {'name': 'Biggest Bear', 'self_or_friend_name': 'Medium Bear'},
            # Biggest bear -> Medium bear -> Medium bear -> Biggest Bear
            {'name': 'Biggest Bear', 'self_or_friend_name': 'Biggest Bear'},
            # Biggest bear -> Medium bear -> Biggest bear -> Medium Bear
            {'name': 'Biggest Bear', 'self_or_friend_name': 'Medium Bear'},
        ]
        params = {
            'name': 'Biggest Bear',
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_recursive_multiple_cycles(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                out_Animal_FriendsWith @recurse(depth: 3) {
                    name @output(out_name: "self_or_friend_name")
                }
            }
        }
        '''
        expected_results = [
            # Base case
            {'name': 'Little Bear', 'self_or_friend_name': 'Little Bear'},
            # Little Bear -> Big Bear
            {'name': 'Little Bear', 'self_or_friend_name': 'Big Bear'},
            # Little Bear -> Biggest Bear
            {'name': 'Little Bear', 'self_or_friend_name': 'Biggest Bear'},
            # Little Bear -> Biggest Bear -> Medium Bear
            {'name': 'Little Bear', 'self_or_friend_name': 'Medium Bear'},
            # Little Bear -> Biggest Bear -> Medium Bear -> Medium Bear
            {'name': 'Little Bear', 'self_or_friend_name': 'Medium Bear'},
            # Little Bear -> Biggest Bear -> Medium Bear -> Biggest Bear
            {'name': 'Little Bear', 'self_or_friend_name': 'Biggest Bear'},
        ]
        params = {
            'name': 'Little Bear',
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
                    out_Animal_ImportantEvent {
                        ... on Event {
                            name @output(out_name: "self_or_friend_event")
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
                'self_or_friend_event': 'Morning Feed Event',
            },
        ]
        params = {
            'name': 'Biggest Bear',
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_optional_tag(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
                in_Animal_FriendsWith @optional {
                    out_Animal_FriendsWith @optional {
                        out_Animal_FriendsWith @optional {
                            name @output(out_name: "friend_of_friend_of_friend")
                            out_Animal_ImportantEvent @optional {
                                ... on Event {
                                    name @output(out_name: "friend_of_friend_of_friend_event")
                                         @tag(tag_name: "friend_of_friend_of_friend_event")
                                }
                            }
                        }
                    }
                }
                out_Animal_ImportantEvent @optional {
                    ... on Event {
                        name @filter(op_name: "=", value: ["%friend_of_friend_of_friend_event"])
                    }
                }
            }
        }
        '''
        expected_results = [
            {
                'name': 'Big Bear',
                'friend_of_friend_of_friend': None,
                'friend_of_friend_of_friend_event': None,
            },
            {
                'name': 'Big Bear',
                'friend_of_friend_of_friend': None,
                'friend_of_friend_of_friend_event': None,
            },
            {
                'name': 'Big Bear',
                'friend_of_friend_of_friend': None,
                'friend_of_friend_of_friend_event': None,
            },
            {
                'name': 'Big Bear',
                'friend_of_friend_of_friend': 'Medium Bear',
                'friend_of_friend_of_friend_event': 'Morning Feed Event'
            },
        ]
        params = {
            'name': 'Big Bear'
        }
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_required_edges_after_optional_out(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                out_Animal_ParentOf @optional {
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
            # Little Bear does not satisfy the first optional edge, so the result is not filtered
            {
                'name': 'Little Bear',
                'child_name': None,
                'grandchild_name': None,
                'great_grandchild_name': None,
            },
            # All other bears are filtered because they satisfy the optional, but they do not have
            # the required depth of descendants
        ]
        self.assertQueryOutputEquals(graphql_string, {}, expected_results)

    def test_required_edges_after_optional_in(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                in_Animal_ParentOf @optional {
                    name @output(out_name: "parent_name")
                    in_Animal_ParentOf {
                        name @output(out_name: "grandparent_name")
                        in_Animal_ParentOf {
                            name @output(out_name: "great_grandparent_name")
                        }
                    }
                }
            }
        }
        '''
        expected_results = [
            {
                'great_grandparent_name': 'Biggest Bear',
                'grandparent_name': 'Big Bear',
                'parent_name': 'Medium Bear',
                'name': 'Little Bear'
            },
            # Biggest Bear does not satisfy the first optional edge, so the result is not filtered
            {
                'name': 'Biggest Bear',
                'grandparent_name': None,
                'parent_name': None,
                'great_grandparent_name': None,
            },
            # All other bears are filtered because they satisfy the optional, but they do not have
            # the required depth of ancestors
        ]
        self.assertQueryOutputEquals(graphql_string, {}, expected_results)

    def test_many_to_many_junction_required_edge_after_optional(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$animal_names"])
                out_Animal_ParentOf @optional {
                    name @output(out_name: "child_name")
                    out_Animal_FriendsWith {
                        name @output(out_name: "child_friend_name")
                    }
                }
            }
        }
        '''
        params = {
            'animal_names': ['Little Bear', 'Biggest Bear']
        }
        expected_results = [
            # Biggest Bear has child Big Bear, who has no friends, causing the result to be excluded
            {'name': 'Little Bear', 'child_name': None, 'child_friend_name': None},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_required_edge_after_optional_in(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$animal_names"])
                out_Animal_ParentOf @optional {
                    name @output(out_name: "child_name")
                    in_Animal_FriendsWith {
                        name @output(out_name: "child_friend_name")
                    }
                }
            }
        }
        '''
        params = {
            'animal_names': ['Little Bear', 'Medium Bear']
        }
        expected_results = [
            # Medium Bear is the parent of Little Bear, but no one is friends with Little Bear
            # This result is dropped
            {'name': 'Little Bear', 'child_name': None, 'child_friend_name': None},
        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)

    def test_many_to_many_junction_required_edge_after_optional_deep(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "in_collection", value: ["$animal_names"])
                out_Animal_ParentOf @optional {
                    name @output(out_name: "child_name")
                    out_Animal_FriendsWith @optional{
                        name @output(out_name: "child_friend_name")
                        in_Animal_ParentOf {
                            name @output(out_name: "child_friend_parent")
                        }
                    }
                }
            }
        }
        '''
        params = {
            'animal_names': ['Big Bear', 'Little Bear', 'Biggest Bear']
        }
        expected_results = [
            {
                'name': 'Little Bear',
                'child_name': None,
                'child_friend_name': None,
                'child_friend_parent': None
            },
            # Biggest Bear's child Big Bear has no friends
            {
                'name': 'Biggest Bear',
                'child_name': 'Big Bear',
                'child_friend_name': None,
                'child_friend_parent': None
            },
            # Big Bear's child Medium Bear is friends with Biggest Bear and himself. Biggest bear
            # doesn't have a parent so this result is excluded.
            {
                'name': 'Big Bear',
                'child_name': 'Medium Bear',
                'child_friend_name': 'Medium Bear',
                'child_friend_parent': 'Big Bear'
            },


        ]
        self.assertQueryOutputEquals(graphql_string, params, expected_results)


class SqlConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine, metadata = create_misconfigured_sqlite_db()
        compiler_metadata = CompilerMetadata(engine.dialect.name, metadata)
        cls.compiler_metadata = compiler_metadata
        cls.engine = engine
        cls.metadata = metadata
        cls.schema = get_schema()
        cls.maxDiff = None

    def compile_query(self, graphql_string, query_params):
        compilation_result = graphql_to_sql(
            self.schema, graphql_string, query_params, self.compiler_metadata)
        return compilation_result.query

    def test_ambiguous_junction_table(self):
        graphql_string = '''
        {
            Animal {
                out_Animal_ImportantEvent {
                    ... on Event {
                        name @output(out_name: "event_name")
                    }
                }
            }
        }
        '''
        params = {}
        with self.assertRaises(exceptions.GraphQLCompilationError):
            self.compile_query(graphql_string, params)

    def test_incorrect_junction_column_name(self):
        graphql_string = '''
        {
            Animal {
                out_Animal_FriendsWith {
                    name @output(out_name: "event_name")
                }
            }
        }
        '''
        params = {}
        with self.assertRaises(exceptions.GraphQLCompilationError):
            self.compile_query(graphql_string, params)

    def test_table_with_composite_primary_key(self):
        graphql_string = '''
        {
            Species {
                in_Animal_OfSpecies {
                    name @output(out_name: "animal_name")
                }
            }
        }
        '''
        params = {}
        with self.assertRaises(exceptions.GraphQLCompilationError):
            self.compile_query(graphql_string, params)

    def test_table_with_incorrect_column_name(self):
        graphql_string = '''
        {
            Event {
                name @output(out_name: "event_name")
            }
        }
        '''
        with self.assertRaises(exceptions.GraphQLCompilationError):
            self.compile_query(graphql_string, {})

    def test_field_missing_from_table_error(self):
        # color is not a column on the animal table
        graphql_string = '''
        {
            Animal {
                color @output(out_name: "color")
            }
        }
        '''
        with self.assertRaises(exceptions.GraphQLCompilationError):
            self.compile_query(graphql_string, {})

    def test_query_no_table(self):
        graphql_string = '''
        {
            Entity {
                name @output(out_name: "name")
            }
        }
        '''
        with self.assertRaises(exceptions.GraphQLCompilationError):
            self.compile_query(graphql_string, {})

    def test_table_with_two_pks_out(self):
        graphql_string = '''
        {
            Animal {
                out_Animal_FedAt {
                    event_date @output(out_name: "fed_at_date")
                }
            }
        }
        '''
        with self.assertRaises(exceptions.GraphQLCompilationError):
            self.compile_query(graphql_string, {})

    def test_table_with_two_pks_in(self):
        graphql_string = '''
        {
            Event {
                in_Animal_FedAt {
                    name @output(out_name: "animal_name")
                }
            }
        }
        '''
        with self.assertRaises(exceptions.GraphQLCompilationError):
            self.compile_query(graphql_string, {})
