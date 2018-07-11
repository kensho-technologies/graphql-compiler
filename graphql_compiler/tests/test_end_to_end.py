# Copyright 2017-present Kensho Technologies, LLC.
from decimal import Decimal
import unittest

import pytest
from sqlalchemy import text, select, literal_column

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
        base_query = (
            select([
                ancestor.c.animal_id,
                ancestor.c.parent_id])
            .select_from(ancestor.join(root_query, root_query.c.animal_id == ancestor.c.animal_id))
        )
        ancestor_cte = base_query.cte(recursive=True)
        recursive_query = (
            select([
                ancestor_cte.c.animal_id,
                animal.c.parent_id])
                .select_from(animal.join(ancestor_cte, animal.c.animal_id == ancestor_cte.c.parent_id)))
        query = ancestor_cte.union_all(recursive_query)
        query = select([root_query.c.name, ancestor.c.animal_name.label('ancestor')]).select_from(
            root_query.join(query, query.c.animal_id == root_query.c.animal_id).join(ancestor, ancestor.c.animal_id == query.c.parent_id)
        )

        expected_results = [
            {'name': 'Little Bear', 'ancestor': 'Big Bear'},
            {'name': 'Little Bear', 'ancestor': 'Biggest Bear'},
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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string, self.compiler_metadata)
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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string, self.compiler_metadata)
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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string, self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Big Bear', 'location_name': 'Wisconsin'},
        ]
        params = {
            '$name': 'Big Bear'
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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string, self.compiler_metadata)
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
                        name @output(out_name: "child_name")
                    }
                }
            }
        }
        '''
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string, self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Big Bear', 'child_name': 'Little Bear'},
            {'name': 'Biggest Bear', 'child_name': 'Medium Bear'},
        ]
        results = self.run_query(query, ['name', 'child_name'])
        self.assertListEqual(expected_results, results)

    @pytest.mark.skip(reason="Recursion is being developed.")
    def test_basic_recurse_out(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                out_Animal_ParentOf @recurse(depth: 1){
                    name @output(out_name: "child_name")
                }
            }
        }
        '''
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string, self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Big Bear', 'child_name': 'Little Bear'},
        ]
        results = self.run_query(query, ['name', 'child_name'])
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
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string, self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Big Bear', 'parent_name': 'Biggest Bear'},
            {'name': 'Little Bear', 'parent_name': 'Medium Bear'},
            {'name': 'Medium Bear', 'parent_name': 'Big Bear'},
        ]
        results = self.run_query(query, ['name', 'parent_name'])
        self.assertListEqual(expected_results, results)

    @pytest.mark.skip(reason="Recursion is being developed.")
    def test_basic_in_edge_recurse(self):
        graphql_string = '''
        {
            Animal {
                name @output(out_name: "name")
                in_Animal_ParentOf @recurse(depth: 1) {
                    name @output(out_name: "parent_name")
                }
            }
        }
        '''
        compilation_result = compile_graphql_to_sql(self.schema, graphql_string, self.compiler_metadata)
        query = compilation_result.query
        expected_results = [
            {'name': 'Little Bear', 'parent_name': 'Medium Bear'},
            {'name': 'Medium Bear', 'parent_name': 'Big Bear'},
        ]
        results = self.run_query(query, ['name', 'parent_name'])
        self.assertListEqual(expected_results, results)






