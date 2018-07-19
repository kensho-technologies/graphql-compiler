import unittest

from sqlalchemy import text, select, case, cast, String

from graphql_compiler.compiler import compile_graphql_to_sql
from graphql_compiler.compiler.ir_lowering_sql.metadata import CompilerMetadata
from graphql_compiler.tests.test_helpers import create_sqlite_db, get_test_sql_config, get_schema


class SqlQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine, metadata = create_sqlite_db()
        config = get_test_sql_config()
        compiler_metadata = CompilerMetadata(config, engine.dialect.name, metadata)
        cls.compiler_metadata = compiler_metadata
        cls.engine = engine
        cls.metadata = metadata
        cls.schema = get_schema()

    def run_query(self, query, sort_order, **params):
        results = (dict(result) for result in self.engine.execute(query.params(**params)))
        return sorted(results, key=lambda result: tuple(result[col] for col in sort_order))

    def test_db(self):
        query = text('''
        SELECT animal_name FROM animal
        ''')
        expected_results = [
            {'animal_name': 'Big Bear'},
            {'animal_name': 'Biggest Bear'},
            {'animal_name': 'Little Bear'},
            {'animal_name': 'Medium Bear'},
        ]
        results = self.run_query(query, ['animal_name'])
        self.assertListEqual(expected_results, results)

    def test_basic_query(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
            }
        }
        '''
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Big Bear'},
            {'name': 'Biggest Bear'},
            {'name': 'Little Bear'},
            {'name': 'Medium Bear'},
        ]
        results = self.run_query(query, ['name'])
        self.assertListEqual(expected_results, results)

    def test_basic_filter(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$name"])
            }
        }
        '''
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Big Bear'},
        ]
        params = {
            '$name': 'Big Bear'
        }
        results = self.run_query(query, ['name'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'parent_name': 'Big Bear', 'child_name': 'Medium Bear'},
        ]
        results = self.run_query(query, ['child_name'])
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'parent_name': 'Big Bear', 'child_name': 'Medium Bear'},
            {'parent_name': 'Little Bear', 'child_name': None},
        ]
        results = self.run_query(query, ['parent_name'])
        self.assertListEqual(expected_results, results)

    def test_basic_out_edge(self):
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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Big Bear', 'location_name': 'Wisconsin'},
        ]
        params = {
            '$name': 'Big Bear'
        }
        results = self.run_query(query, ['name'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Big Bear', 'location_name': 'Wisconsin'},
            {'name': 'Biggest Bear', 'location_name': None},
        ]
        params = {
            '$names': ['Biggest Bear', 'Big Bear']
        }
        results = self.run_query(query, ['name'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Big Bear', 'location_name': 'Wisconsin', 'parent_name': 'Biggest Bear'},
            {'name': 'Biggest Bear', 'location_name': None, 'parent_name': None},
        ]
        params = {
            '$names': ['Biggest Bear', 'Big Bear']
        }
        results = self.run_query(query, ['name'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Big Bear', 'parent_location_name': None},
            {'name': 'Biggest Bear', 'parent_location_name': None},
            {'name': 'Medium Bear', 'parent_location_name': 'Wisconsin'}
        ]
        params = {
            '$names': ['Biggest Bear', 'Big Bear', 'Medium Bear']
        }
        results = self.run_query(query, ['name'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
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
        results = self.run_query(query, ['name'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Big Bear', 'child_name': 'Medium Bear'},
            {'name': 'Biggest Bear', 'child_name': 'Big Bear'},
            {'name': 'Medium Bear', 'child_name': 'Little Bear'},
        ]
        results = self.run_query(query, ['name', 'child_name'])
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Big Bear', 'grandchild_name': 'Little Bear'},
            {'name': 'Biggest Bear', 'grandchild_name': 'Medium Bear'},
        ]
        results = self.run_query(query, ['name', 'grandchild_name'])
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Biggest Bear', 'child_name': 'Big Bear', 'grandchild_name': 'Medium Bear',
             'great_grandchild_name': 'Little Bear'},
        ]
        results = self.run_query(query, ['name', 'child_name'])
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        params = {
            '$bear_name': 'Little Bear'
        }
        expected_results = [
            {'name': 'Little Bear', 'ancestor': 'Big Bear'},
            {'name': 'Little Bear', 'ancestor': 'Biggest Bear'},
            {'name': 'Little Bear', 'ancestor': 'Little Bear'},
            {'name': 'Little Bear', 'ancestor': 'Medium Bear'},
        ]
        results = self.run_query(query, ['name', 'ancestor'], **params)
        self.assertListEqual(expected_results, results)

    # def test_basic_fold(self):
    #     graphql_string = '''
    #     {
    #         Animal {
    #             name @filter(op_name: "=", value: ["$bear_name"])
    #             out_Animal_LivesIn @fold {
    #                 name @output(out_name: "locations")
    #             }
    #         }
    #     }
    #     '''
    #     compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
    #                                                 self.compiler_metadata)
    #     query = compilation_result.query
    #     params = {
    #         '$bear_name': 'Medium Bear'
    #     }
    #     expected_results = [
    #         {'name': 'Medium Bear', 'ancestor': 'Big Bear'},
    #     ]
    #     results = self.run_query(query, ['name', 'ancestor'], **params)
    #     self.assertListEqual(expected_results, results)


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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        params = {
            '$bear_name': 'Little Bear',
            '$ancestor_name': 'Biggest Bear'
        }
        expected_results = [
            {'name': 'Little Bear', 'ancestor': 'Biggest Bear'},
        ]
        results = self.run_query(query, ['name', 'ancestor'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        params = {
            '$bear_name': 'Little Bear'
        }
        expected_results = [
            {'name': 'Little Bear', 'ancestor': 'Little Bear'},
            {'name': 'Little Bear', 'ancestor': 'Medium Bear'},
        ]
        results = self.run_query(query, ['name', 'ancestor'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        params = {
            '$bear_name': 'Biggest Bear'
        }
        expected_results = [
            {'name': 'Biggest Bear', 'descendant': 'Big Bear'},
            {'name': 'Biggest Bear', 'descendant': 'Biggest Bear'},
            {'name': 'Biggest Bear', 'descendant': 'Little Bear'},
            {'name': 'Biggest Bear', 'descendant': 'Medium Bear'},
        ]
        results = self.run_query(query, ['name', 'descendant'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        params = {
            '$bear_name': 'Big Bear'
        }
        expected_results = [
            {'name': 'Big Bear', 'descendant': 'Big Bear', 'home': 'Wisconsin'},
            {'name': 'Big Bear', 'descendant': 'Little Bear', 'home': 'Wisconsin'},
            {'name': 'Big Bear', 'descendant': 'Medium Bear', 'home': 'Wisconsin'},
        ]
        results = self.run_query(query, ['name', 'descendant'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
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
        results = self.run_query(query, ['name', 'descendant'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        params = {
            '$bear_name': 'Biggest Bear'
        }
        expected_results = [
            {'name': 'Biggest Bear', 'child': 'Big Bear', 'child_or_descendant': 'Big Bear'},
            {'name': 'Biggest Bear', 'child': 'Big Bear', 'child_or_descendant': 'Little Bear'},
            {'name': 'Biggest Bear', 'child': 'Big Bear', 'child_or_descendant': 'Medium Bear'},
        ]
        results = self.run_query(query, ['name', 'child', 'child_or_descendant'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
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
        results = self.run_query(query, ['name', 'descendant', 'ancestor'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Big Bear', 'parent_name': 'Biggest Bear'},
            {'name': 'Little Bear', 'parent_name': 'Medium Bear'},
            {'name': 'Medium Bear', 'parent_name': 'Big Bear'},
        ]
        results = self.run_query(query, ['name', 'parent_name'])
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        params = {
            '$bear_name': 'Biggest Bear'
        }
        expected_results = [
            {'name': 'Biggest Bear', 'descendant': 'Big Bear', 'descendant_parent': 'Biggest Bear'},
            {'name': 'Biggest Bear', 'descendant': 'Biggest Bear', 'descendant_parent': None},
            {'name': 'Biggest Bear', 'descendant': 'Little Bear',
             'descendant_parent': 'Medium Bear'},
            {'name': 'Biggest Bear', 'descendant': 'Medium Bear', 'descendant_parent': 'Big Bear'},
        ]
        results = self.run_query(query, ['name', 'descendant'], **params)
        self.assertListEqual(expected_results, results)

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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        params = {
            '$bear_name': 'Biggest Bear'
        }
        expected_results = [
            {'name': 'Biggest Bear', 'descendant': 'Big Bear', 'descendant_child': 'Medium Bear'},
        ]
        results = self.run_query(query, ['name', 'descendant'], **params)
        self.assertListEqual(expected_results, results)

    def test_basic_recurse_with_nested_expansion(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                out_Animal_ParentOf @recurse(depth: 3){
                    name @output(out_name: "descendant")
                    in_Animal_ParentOf @optional {
                        name @output(out_name: "descendant_parent")
                        out_Animal_ParentOf {
                            name @output(out_name: "same_as_descendant")
                        }
                    }
                }
            }
        }
        '''
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        params = {
            '$bear_name': 'Biggest Bear'
        }
        expected_results = [
            {'name': 'Biggest Bear', 'descendant': 'Big Bear', 'same_as_descendant': 'Big Bear',
             'descendant_parent': 'Biggest Bear', },
            {'name': 'Biggest Bear', 'descendant': 'Biggest Bear', 'same_as_descendant': None,
             'descendant_parent': None},
            {'name': 'Biggest Bear', 'descendant': 'Little Bear',
             'same_as_descendant': 'Little Bear', 'descendant_parent': 'Medium Bear'},
            {'name': 'Biggest Bear', 'descendant': 'Medium Bear',
             'same_as_descendant': 'Medium Bear', 'descendant_parent': 'Big Bear'},
        ]
        results = self.run_query(query, ['name', 'descendant', 'same_as_descendant'], **params)
        self.assertListEqual(expected_results, results)

    def test_recursion_in_recursion(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                in_Animal_ParentOf @recurse(depth: 1){
                    name @output(out_name: "ancestor")
                    out_Animal_ParentOf @recurse(depth: 1) {
                        name @output(out_name: "ancestor_or_ancestor_child")
                    }
                }
            }
        }
        '''
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        params = {
            '$bear_name': 'Little Bear'
        }
        expected_results = [
            {'name': 'Little Bear', 'ancestor': 'Little Bear',
             'ancestor_or_ancestor_child': 'Little Bear'},
            {'name': 'Little Bear', 'ancestor': 'Medium Bear',
             'ancestor_or_ancestor_child': 'Little Bear'},
            {'name': 'Little Bear', 'ancestor': 'Medium Bear',
             'ancestor_or_ancestor_child': 'Medium Bear'},
        ]
        results = self.run_query(query, ['name', 'ancestor', 'ancestor_or_ancestor_child'],
                                 **params)
        self.assertListEqual(expected_results, results)

    def test_double_recursion_in_recursion(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                     @filter(op_name: "=", value: ["$bear_name"])
                in_Animal_ParentOf @recurse(depth: 1){
                    name @output(out_name: "self_or_ancestor")
                    out_Animal_ParentOf @recurse(depth: 1) {
                        name @output(out_name: "ancestor_or_ancestor_child")
                    }
                    in_Animal_ParentOf @recurse(depth: 1) {
                        name @output(out_name: "ancestor_or_ancestor_parent")
                    }
                }
            }
        }
        '''
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string,
                                                    self.compiler_metadata)
        query = compilation_result.query
        params = {
            '$bear_name': 'Little Bear'
        }
        expected_results = [
            {'name': 'Little Bear',
             'self_or_ancestor': 'Little Bear',
             'ancestor_or_ancestor_child': 'Little Bear',
             'ancestor_or_ancestor_parent': 'Little Bear'},
            {'name': 'Little Bear',
             'self_or_ancestor': 'Little Bear',
             'ancestor_or_ancestor_child': 'Little Bear',
             'ancestor_or_ancestor_parent': 'Medium Bear'},
            {'name': 'Little Bear',
             'self_or_ancestor': 'Medium Bear',
             'ancestor_or_ancestor_child': 'Little Bear',
             'ancestor_or_ancestor_parent': 'Big Bear'},
            {'name': 'Little Bear',
             'self_or_ancestor': 'Medium Bear',
             'ancestor_or_ancestor_child': 'Little Bear',
             'ancestor_or_ancestor_parent': 'Medium Bear'},
            {'name': 'Little Bear',
             'self_or_ancestor': 'Medium Bear',
             'ancestor_or_ancestor_child': 'Medium Bear',
             'ancestor_or_ancestor_parent': 'Big Bear'},
            {'name': 'Little Bear',
             'self_or_ancestor': 'Medium Bear',
             'ancestor_or_ancestor_child': 'Medium Bear',
             'ancestor_or_ancestor_parent': 'Medium Bear'},
        ]
        results = self.run_query(query, ['name', 'self_or_ancestor', 'ancestor_or_ancestor_child',
                                         'ancestor_or_ancestor_parent'], **params)
        self.assertListEqual(expected_results, results)