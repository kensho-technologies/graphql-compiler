# Copyright 2017-present Kensho Technologies, LLC.
from decimal import Decimal
import unittest

import pytest
from sqlalchemy import text, select, literal_column, func, case, Integer, cast, String

from .. import graphql_to_gremlin, graphql_to_match
from ..compiler import compile_graphql_to_gremlin, compile_graphql_to_match, compile_graphql_to_sql
from ..compiler.ir_lowering_sql.metadata import CompilerMetadata
from ..exceptions import GraphQLInvalidArgumentError
from ..query_formatting import insert_arguments_into_query
from .test_helpers import (
    compare_gremlin, compare_match, get_schema, create_sqlite_db, get_test_sql_config
)

EXAMPLE_GRAPHQL_QUERY = '''{
    Animal @filter(op_name: "name_or_alias", value: ["$wanted_name"]) {
        name @output(out_name: "name")
        net_worth @filter(op_name: ">=", value: ["$min_worth"])
    }
}'''


class QueryFormattingTests(unittest.TestCase):
    def test_correct_arguments(self):
        wanted_name = 'Top Cat'
        min_worth = Decimal('123456789.0123456')
        expected_match = '''
            SELECT Animal___1.name AS `name` FROM (
                MATCH {
                    class: Animal,
                    where: ((
                        ((name = "Top Cat") OR (alias CONTAINS "Top Cat")) AND
                        (net_worth >= decimal("123456789.0123456"))
                    )),
                    as: Animal___1
                } RETURN $matches
            )
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> (
                ((it.name == 'Top Cat') || it.alias.contains('Top Cat')) &&
                (it.net_worth >= 123456789.0123456G)
            )}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name
            ])}
        '''
        arguments = {
            'wanted_name': wanted_name,
            'min_worth': min_worth,
        }
        schema = get_schema()

        actual_match = insert_arguments_into_query(
            compile_graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY), arguments)
        compare_match(self, expected_match, actual_match, parameterized=False)

        actual_match = graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY, arguments).query
        compare_match(self, expected_match, actual_match, parameterized=False)

        actual_gremlin = insert_arguments_into_query(
            compile_graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY), arguments)
        compare_gremlin(self, expected_gremlin, actual_gremlin)

        actual_gremlin = graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY, arguments).query
        compare_gremlin(self, expected_gremlin, actual_gremlin)

    def test_missing_argument(self):
        schema = get_schema()
        compiled_match_result = compile_graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY)
        compiled_gremlin_result = compile_graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY)

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_match_result, {})

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY, {})

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_gremlin_result, {})

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY, {})

    def test_surplus_argument(self):
        schema = get_schema()
        compiled_match_result = compile_graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY)
        compiled_gremlin_result = compile_graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY)
        arguments = {
            'wanted_name': 'Top Cat',
            'foobar': 123
        }

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_match_result, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_gremlin_result, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY, arguments)

    def test_misnamed_argument(self):
        schema = get_schema()
        compiled_match_result = compile_graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY)
        compiled_gremlin_result = compile_graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY)
        arguments = {
            'foobar': 123
        }

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_match_result, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            insert_arguments_into_query(compiled_gremlin_result, arguments)

        with self.assertRaises(GraphQLInvalidArgumentError):
            graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY, {})

    def test_wrong_argument_type(self):
        schema = get_schema()
        compiled_match_result = compile_graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY)
        compiled_gremlin_result = compile_graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY)

        wrong_argument_types = [
            {
                'wanted_name': 123
            }, {
                'wanted_name': ['abc', 'def', 'ghi']
            }, {
                'wanted_name': ['abc']
            }, {
                'wanted_name': None
            }, {
                'wanted_name': [1, 2, 3]
            }
        ]

        for arguments in wrong_argument_types:
            with self.assertRaises(GraphQLInvalidArgumentError):
                insert_arguments_into_query(compiled_match_result, arguments)

            with self.assertRaises(GraphQLInvalidArgumentError):
                graphql_to_match(schema, EXAMPLE_GRAPHQL_QUERY, arguments)

            with self.assertRaises(GraphQLInvalidArgumentError):
                insert_arguments_into_query(compiled_gremlin_result, arguments)

            with self.assertRaises(GraphQLInvalidArgumentError):
                graphql_to_gremlin(schema, EXAMPLE_GRAPHQL_QUERY, {})


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


    def test_db_recurse(self):
        animal_table = self.metadata.tables['animal']
        animal = animal_table.alias()
        ancestor = animal_table.alias()
        root_query = (
            select([animal.c.animal_id, animal.c.animal_name.label('name')])
                .select_from(animal).where(animal.c.animal_name == 'Little Bear')
        ).cte()
        primary_key = [column for column in ancestor.c if column.primary_key][0]
        distinct_column_query = select([root_query.c.animal_id]).alias()
        anchor_query = (
            select([
                primary_key,
                primary_key.label('parent_id'),
                primary_key.concat(',').label('path'),
                # literal_column(0, type_=Integer()).label('has_cycle')
            ])
                .select_from(
                ancestor.join(distinct_column_query, distinct_column_query.c.animal_id == ancestor.c.animal_id)
            )
        )
        ancestor_cte = anchor_query.cte(recursive=True)
        recursive_query = (
            select([
                ancestor_cte.c.animal_id,
                animal.c.parent_id,
                ancestor_cte.c.path.concat(animal.c.parent_id).concat(',').label('path'),
            ])
                .select_from(
                animal.join(ancestor_cte, animal.c.animal_id == ancestor_cte.c.parent_id))
                .where(case(
                    [
                        (ancestor_cte.c.path.contains(cast(animal.c.parent_id, String())), 1)
                    ],
                    else_=0
                ) == 0)
        )
        query = ancestor_cte.union_all(recursive_query)
        query = select([root_query.c.name, ancestor.c.animal_name.label('ancestor')]).select_from(
            root_query.join(query, query.c.animal_id == root_query.c.animal_id).join(ancestor,
                                                                                     ancestor.c.animal_id == query.c.parent_id)
        )

        expected_results = [

            {'name': 'Little Bear', 'ancestor': 'Big Bear'},
            {'name': 'Little Bear', 'ancestor': 'Biggest Bear'},
            {'name': 'Little Bear', 'ancestor': 'Little Bear'},
            {'name': 'Little Bear', 'ancestor': 'Medium Bear'},

        ]
        results = self.run_query(query, ['name', 'ancestor'])
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
