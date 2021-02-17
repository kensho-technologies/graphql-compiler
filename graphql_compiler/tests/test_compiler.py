# Copyright 2017-present Kensho Technologies, LLC.
"""End-to-end tests of the GraphQL compiler."""
from functools import partial
import os
from typing import Callable, Dict, Optional, Type, Union, cast
import unittest

from funcy import identity, rpartial
from graphql import (
    GraphQLID,
    GraphQLInterfaceType,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLString,
    GraphQLUnionType,
)
import six
from sqlalchemy.sql.selectable import Select

from . import test_input_data
from ..compiler import (
    CompilationResult,
    OutputMetadata,
    compile_graphql_to_cypher,
    compile_graphql_to_gremlin,
    compile_graphql_to_match,
    compile_graphql_to_sql,
)
from ..compiler.sqlalchemy_extensions import print_sqlalchemy_query_string
from ..exceptions import GraphQLCompilationError, GraphQLValidationError
from ..schema import TypeEquivalenceHintsType
from ..schema.schema_info import CommonSchemaInfo
from .test_helpers import (
    SKIP_TEST,
    compare_cypher,
    compare_gremlin,
    compare_input_metadata,
    compare_match,
    compare_sql,
    get_schema,
    get_sqlalchemy_schema_info,
)


def _check_expected_output_for_language(
    test_case: unittest.TestCase,
    test_data: test_input_data.CommonTestData,
    compiler_func: Callable[[str], CompilationResult],
    query_printer_func: Callable[[Union[str, Select]], str],
    output_equality_assertion_func: Callable[[unittest.TestCase, str, str], None],
    expected_output: Union[str, Type[NotImplementedError]],
) -> None:
    """Assert that the provided GraphQL input produces the expected compiler output."""
    graphql_query = test_data.graphql_input

    if expected_output == SKIP_TEST:
        # This test is skipped.
        pass
    elif expected_output == NotImplementedError:
        # This test is expected to raise an error that indicates the functionality is unsupported.
        unsupported_errors = (NotImplementedError, GraphQLValidationError, GraphQLCompilationError)
        with test_case.assertRaises(unsupported_errors):
            compiler_func(graphql_query)
    elif isinstance(expected_output, str):
        # This test is expected to compile properly and produce the given input.
        result = compiler_func(graphql_query)
        compiled_query = query_printer_func(result.query)

        output_equality_assertion_func(test_case, expected_output, compiled_query)
        test_case.assertEqual(test_data.expected_output_metadata, result.output_metadata)
        compare_input_metadata(test_case, test_data.expected_input_metadata, result.input_metadata)
    else:
        raise AssertionError(f"Received unexpected value for expected_output: {expected_output}")


def check_test_data(
    test_case: "CompilerTests",
    test_data: test_input_data.CommonTestData,
    expected_match: Union[str, Type[NotImplementedError]],
    expected_gremlin: Union[str, Type[NotImplementedError]],
    expected_mssql: Union[str, Type[NotImplementedError]],
    expected_cypher: Union[str, Type[NotImplementedError]],
    expected_postgresql: Union[str, Type[NotImplementedError]],
) -> None:
    """Assert that the GraphQL input generates all expected output queries data."""
    schema_based_type_equivalence_hints: Optional[TypeEquivalenceHintsType]
    if test_data.type_equivalence_hints:
        # For test convenience, we accept the type equivalence hints in string form.
        # Here, we convert them to the required GraphQL types.
        schema_based_type_equivalence_hints = {
            cast(
                Union[GraphQLInterfaceType, GraphQLObjectType], test_case.schema.get_type(key)
            ): cast(GraphQLUnionType, test_case.schema.get_type(value))
            for key, value in six.iteritems(test_data.type_equivalence_hints)
        }
    else:
        schema_based_type_equivalence_hints = None

    common_schema_info = CommonSchemaInfo(test_case.schema, schema_based_type_equivalence_hints)

    match_compiler_func = partial(compile_graphql_to_match, common_schema_info)
    gremlin_compiler_func = partial(compile_graphql_to_gremlin, common_schema_info)
    cypher_compiler_func = partial(compile_graphql_to_cypher, common_schema_info)
    mssql_compiler_func = partial(compile_graphql_to_sql, test_case.mssql_schema_info)
    postgresql_compiler_func = partial(compile_graphql_to_sql, test_case.postgresql_schema_info)

    mssql_printer_func = rpartial(
        print_sqlalchemy_query_string, test_case.mssql_schema_info.dialect
    )
    postgresql_printer_func = rpartial(
        print_sqlalchemy_query_string, test_case.postgresql_schema_info.dialect
    )

    # compare_match() takes an optional kwarg that means its signature is not representable
    # using the Callable[] syntax. We don't use that kwarg, so fix the signature with a cast.
    compare_parameterized_match = cast(Callable[[unittest.TestCase, str, str], None], compare_match)

    language_configurations = [
        ("MATCH", match_compiler_func, identity, compare_parameterized_match, expected_match),
        ("Gremlin", gremlin_compiler_func, identity, compare_gremlin, expected_gremlin),
        ("Cypher", cypher_compiler_func, identity, compare_cypher, expected_cypher),
        ("MS SQL", mssql_compiler_func, mssql_printer_func, compare_sql, expected_mssql),
        (
            "PostgreSQL",
            postgresql_compiler_func,
            postgresql_printer_func,
            compare_sql,
            expected_postgresql,
        ),
    ]

    for configuration in language_configurations:
        (
            _,
            compiler_func,
            query_printer_func,
            equality_assertion_func,
            expected_output,
        ) = configuration
        _check_expected_output_for_language(
            test_case,
            test_data,
            compiler_func,
            query_printer_func,
            equality_assertion_func,
            expected_output,
        )


class CompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.schema = get_schema()
        self.mssql_schema_info = get_sqlalchemy_schema_info(dialect="mssql")
        self.postgresql_schema_info = get_sqlalchemy_schema_info(dialect="postgresql")

    def test_immediate_output(self) -> None:
        test_data = test_input_data.immediate_output()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            RETURN Animal___1.name AS `animal_name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name
            FROM
                schema_1."Animal" AS "Animal_1"
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_immediate_output_custom_scalars(self) -> None:
        test_data = test_input_data.immediate_output_custom_scalars()

        expected_match = """
            SELECT
                Animal___1.birthday.format("yyyy-MM-dd") AS `birthday`,
                Animal___1.net_worth AS `net_worth`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                birthday: m.Animal___1.birthday.format("yyyy-MM-dd"),
                net_worth: m.Animal___1.net_worth
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].birthday AS birthday,
                [Animal_1].net_worth AS net_worth
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "Animal_1".birthday AS birthday,
                "Animal_1".net_worth AS net_worth
            FROM
                schema_1."Animal" AS "Animal_1"
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_immediate_output_with_custom_scalar_filter(self) -> None:
        test_data = test_input_data.immediate_output_with_custom_scalar_filter()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((net_worth >= {min_worth})),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (it.net_worth >= $min_worth)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                [Animal_1].net_worth >= :min_worth
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                "Animal_1".net_worth >= :min_worth
        """
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_colocated_filter_and_tag(self) -> None:
        test_data = test_input_data.colocated_filter_and_tag()

        expected_match = """
            SELECT Animal__out_Entity_Related___1.name AS `related_name` FROM (MATCH {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal___1
            }}.out('Entity_Related') {{
                class: Entity,
                where: ((alias CONTAINS name)),
                as: Animal__out_Entity_Related___1
            }} RETURN $matches)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .out('Entity_Related')
                .filter{it, m -> it.alias.contains(it.name)}
                .as('Animal__out_Entity_Related___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                related_name: m.Animal__out_Entity_Related___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)-[:Entity_Related]->(Animal__out_Entity_Related___1:Entity)
                WHERE (Animal__out_Entity_Related___1.name IN Animal__out_Entity_Related___1.alias)
            RETURN Animal__out_Entity_Related___1.name AS `related_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_colocated_filter_with_differently_named_column_and_tag(self) -> None:
        test_data = test_input_data.colocated_filter_with_differently_named_column_and_tag()

        expected_match = """
            SELECT Animal__out_Entity_Related___1.name AS `related_name` FROM (MATCH {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal___1
            }}.out('Entity_Related') {{
                class: Entity,
                where: ((alias CONTAINS name)),
                as: Animal__out_Entity_Related___1
            }} RETURN $matches)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .out('Entity_Related')
                .filter{it, m -> it.alias.contains(it.name)}
                .as('Animal__out_Entity_Related___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                related_name: m.Animal__out_Entity_Related___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)-[:Entity_Related]->(Animal__out_Entity_Related___1:Entity)
                WHERE (Animal__out_Entity_Related___1.name IN Animal__out_Entity_Related___1.alias)
            RETURN Animal__out_Entity_Related___1.name AS `related_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_colocated_filter_and_tag_sharing_name_with_other_column(self) -> None:
        test_data = test_input_data.colocated_filter_and_tag_sharing_name_with_other_column()

        expected_match = """
            SELECT Animal__out_Entity_Related___1.name AS `related_name` FROM (MATCH {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal___1
            }}.out('Entity_Related') {{
                class: Entity,
                where: ((alias CONTAINS name)),
                as: Animal__out_Entity_Related___1
            }} RETURN $matches)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .out('Entity_Related')
                .filter{it, m -> it.alias.contains(it.name)}
                .as('Animal__out_Entity_Related___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                related_name: m.Animal__out_Entity_Related___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)-[:Entity_Related]->(Animal__out_Entity_Related___1:Entity)
                WHERE (Animal__out_Entity_Related___1.name IN Animal__out_Entity_Related___1.alias)
            RETURN Animal__out_Entity_Related___1.name AS `related_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_colocated_out_of_order_filter_and_tag(self) -> None:
        test_data = test_input_data.colocated_out_of_order_filter_and_tag()

        expected_match = """
            SELECT Animal__out_Entity_Related___1.name AS `related_name` FROM (MATCH {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal___1
            }}.out('Entity_Related') {{
                class: Entity,
                where: ((alias CONTAINS name)),
                as: Animal__out_Entity_Related___1
            }} RETURN $matches)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .out('Entity_Related')
                .filter{it, m -> it.alias.contains(it.name)}
                .as('Animal__out_Entity_Related___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                related_name: m.Animal__out_Entity_Related___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)-[:Entity_Related]->(Animal__out_Entity_Related___1:Entity)
                WHERE (Animal__out_Entity_Related___1.name IN Animal__out_Entity_Related___1.alias)
            RETURN Animal__out_Entity_Related___1.name AS `related_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_immediate_filter_and_output(self) -> None:
        # Ensure that all basic comparison operators output correct code in this simple case.
        comparison_operators = {"=", "!=", ">", "<", ">=", "<="}

        for operator in comparison_operators:
            graphql_input = """{
                Animal {
                    name @filter(op_name: "%s", value: ["$wanted"]) @output(out_name: "animal_name")
                }
            }""" % (
                operator,
            )

            # In MATCH, inequality comparisons use the SQL standard "<>" rather than "!=".
            match_operator = "<>" if operator == "!=" else operator
            expected_match = """
                SELECT
                    Animal___1.name AS `animal_name`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((name %(operator)s {wanted})),
                        as: Animal___1
                    }}
                    RETURN $matches
                )
            """ % {  # nosec, the operators are hardcoded above
                "operator": match_operator
            }

            # In Gremlin, equality comparisons use two equal signs instead of one.
            gremlin_operator = "==" if operator == "=" else operator
            expected_gremlin = """
                g.V('@class', 'Animal')
                .filter{it, m -> (it.name %(operator)s $wanted)}
                .as('Animal___1')
                .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                    animal_name: m.Animal___1.name
                ])}
            """ % {  # nosec, the operators are hardcoded above
                "operator": gremlin_operator
            }

            expected_mssql = """
                SELECT
                    [Animal_1].name AS animal_name
                FROM
                    db_1.schema_1.[Animal] AS [Animal_1]
                WHERE
                    [Animal_1].name %(operator)s :wanted
            """ % {  # nosec, the operators are hardcoded above
                "operator": operator
            }

            # In Cypher, inequality comparisons use "<>" instead of "!=".
            cypher_operator = "<>" if operator == "!=" else operator
            expected_cypher = """
                MATCH (Animal___1:Animal)
                    WHERE (Animal___1.name %(operator)s $wanted)
                RETURN Animal___1.name AS `animal_name`
            """ % {  # nosec, the operators are hardcoded above
                "operator": cypher_operator
            }

            expected_output_metadata = {
                "animal_name": OutputMetadata(type=GraphQLString, optional=False, folded=False),
            }
            expected_input_metadata = {
                "wanted": GraphQLString,
            }
            test_data = test_input_data.CommonTestData(
                graphql_input=graphql_input,
                expected_output_metadata=expected_output_metadata,
                expected_input_metadata=expected_input_metadata,
                type_equivalence_hints=None,
            )

            expected_postgresql = """
                SELECT
                    "Animal_1".name AS animal_name
                FROM
                    schema_1."Animal" AS "Animal_1"
                WHERE
                    "Animal_1".name %(operator)s :wanted
            """ % {  # nosec, the operators are hardcoded above
                "operator": operator,
            }

            check_test_data(
                self,
                test_data,
                expected_match,
                expected_gremlin,
                expected_mssql,
                expected_cypher,
                expected_postgresql,
            )

    def test_multiple_filters(self) -> None:
        test_data = test_input_data.multiple_filters()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: (((name >= {lower_bound}) AND (name < {upper_bound}))),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> ((it.name >= $lower_bound) && (it.name < $upper_bound))}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                [Animal_1].name >= :lower_bound
                AND [Animal_1].name < :upper_bound
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE (
                    (Animal___1.name >= $lower_bound) AND
                    (Animal___1.name < $upper_bound)
                )
            RETURN Animal___1.name AS `animal_name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                "Animal_1".name >= :lower_bound
                AND "Animal_1".name < :upper_bound
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_traverse_and_output(self) -> None:
        test_data = test_input_data.traverse_and_output()

        expected_match = """
            SELECT
                Animal__out_Animal_ParentOf___1.name AS `parent_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    class: Animal,
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_ParentOf')
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                parent_name: m.Animal__out_Animal_ParentOf___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS parent_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_2]
                JOIN db_1.schema_1.[Animal] AS [Animal_1]
                    ON [Animal_2].uuid = [Animal_1].parent
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            RETURN Animal__out_Animal_ParentOf___1.name AS `parent_name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS parent_name
            FROM
                schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_1"
                    ON "Animal_2".uuid = "Animal_1".parent
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_optional_traverse_after_mandatory_traverse(self) -> None:
        test_data = test_input_data.optional_traverse_after_mandatory_traverse()

        expected_match = """
            SELECT
                if(eval("(Animal__out_Animal_ParentOf___1 IS NOT null)"),
                    Animal__out_Animal_ParentOf___1.name, null) AS `child_name`,
                Animal__out_Animal_OfSpecies___1.name AS `species_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_OfSpecies') {{
                    class: Species,
                    as: Animal__out_Animal_OfSpecies___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    optional: true,
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            WHERE ( (
                (Animal___1.out_Animal_ParentOf IS null)
                OR
                (Animal___1.out_Animal_ParentOf.size() = 0)
            )
                OR
                (Animal__out_Animal_ParentOf___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_OfSpecies')
            .as('Animal__out_Animal_OfSpecies___1')
            .back('Animal___1')
            .as('Animal___2')
            .ifThenElse{it.out_Animal_ParentOf == null}{null}{it.out('Animal_ParentOf')}
            .as('Animal__out_Animal_ParentOf___1')
            .optional('Animal___2')
            .as('Animal___3')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_name: ((m.Animal__out_Animal_ParentOf___1 != null) ?
                    m.Animal__out_Animal_ParentOf___1.name : null),
                species_name: m.Animal__out_Animal_OfSpecies___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS child_name,
                [Species_1].name AS species_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_2]
                JOIN db_1.schema_1.[Species] AS [Species_1]
                    ON [Animal_2].species = [Species_1].uuid
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_1]
                    ON [Animal_2].uuid = [Animal_1].parent
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)-[:Animal_OfSpecies]->(Animal__out_Animal_OfSpecies___1:Species)
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            RETURN
                (
                    CASE WHEN (Animal__out_Animal_ParentOf___1 IS NOT null)
                    THEN Animal__out_Animal_ParentOf___1.name
                    ELSE null
                    END
                ) AS `child_name`,
                Animal__out_Animal_OfSpecies___1.name AS `species_name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS child_name,
                "Species_1".name AS species_name
            FROM
                schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Species" AS "Species_1"
                    ON "Animal_2".species = "Species_1".uuid
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_1"
                    ON "Animal_2".uuid = "Animal_1".parent
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_traverse_filter_and_output(self) -> None:
        test_data = test_input_data.traverse_filter_and_output()

        expected_match = """
            SELECT
                Animal__out_Animal_ParentOf___1.name AS `parent_name`
            FROM (
                MATCH {{
                    where: ((@this INSTANCEOF 'Animal')),
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    class: Animal,
                    where: (((name = {wanted}) OR (alias CONTAINS {wanted}))),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_ParentOf')
            .filter{it, m -> ((it.name == $wanted) || it.alias.contains($wanted))}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                parent_name: m.Animal__out_Animal_ParentOf___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
                WHERE (
                    (Animal__out_Animal_ParentOf___1.name = $wanted) OR
                    ($wanted IN Animal__out_Animal_ParentOf___1.alias)
                )
            RETURN Animal__out_Animal_ParentOf___1.name AS `parent_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_name_or_alias_filter_on_interface_type(self) -> None:
        test_data = test_input_data.name_or_alias_filter_on_interface_type()

        expected_match = """
            SELECT
                Animal__out_Entity_Related___1.name AS `related_entity`
            FROM (
                MATCH {{
                    where: ((@this INSTANCEOF 'Animal')),
                    as: Animal___1
                }}.out('Entity_Related') {{
                    class: Entity,
                    where: (((name = {wanted}) OR (alias CONTAINS {wanted}))),
                    as: Animal__out_Entity_Related___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Entity_Related')
            .filter{it, m -> ((it.name == $wanted) || it.alias.contains($wanted))}
            .as('Animal__out_Entity_Related___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                related_entity: m.Animal__out_Entity_Related___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)-[:Entity_Related]->(Animal__out_Entity_Related___1:Entity)
                WHERE (
                    (Animal__out_Entity_Related___1.name = $wanted) OR
                    ($wanted IN Animal__out_Entity_Related___1.alias)
                )
            RETURN Animal__out_Entity_Related___1.name AS `related_entity`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_output_source_and_complex_output(self) -> None:
        test_data = test_input_data.output_source_and_complex_output()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                Animal__out_Animal_ParentOf___1.name AS `parent_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((name = {wanted})),
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (it.name == $wanted)}
            .as('Animal___1')
            .out('Animal_ParentOf')
            .as('Animal__out_Animal_ParentOf___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                parent_name: m.Animal__out_Animal_ParentOf___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE (Animal___1.name = $wanted)
            MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            RETURN
                Animal___1.name AS `animal_name`,
                Animal__out_Animal_ParentOf___1.name AS `parent_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_filter_on_optional_variable_equality(self) -> None:
        # The operand in the @filter directive originates from an optional block.
        test_data = test_input_data.filter_on_optional_variable_equality()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    class: Animal,
                    as: Animal__out_Animal_ParentOf___1
                }}.out('Animal_FedAt') {{
                    optional: true,
                    as: Animal__out_Animal_ParentOf__out_Animal_FedAt___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_FedAt') {{
                    where: ((
                        ($matched.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS null) OR
                        (name = $matched.Animal__out_Animal_ParentOf__out_Animal_FedAt___1.name)
                    )),
                    as: Animal__out_Animal_FedAt___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (Animal__out_Animal_ParentOf___1.out_Animal_FedAt IS null)
                    OR
                    (Animal__out_Animal_ParentOf___1.out_Animal_FedAt.size() = 0)
                )
                OR
                (Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_ParentOf')
            .as('Animal__out_Animal_ParentOf___1')
            .ifThenElse{it.out_Animal_FedAt == null}{null}{it.out('Animal_FedAt')}
            .as('Animal__out_Animal_ParentOf__out_Animal_FedAt___1')
            .optional('Animal__out_Animal_ParentOf___1')
            .as('Animal__out_Animal_ParentOf___2')
            .back('Animal___1')
            .out('Animal_FedAt')
            .filter{it, m -> (
                (m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 == null) ||
                (it.name == m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1.name)
            )}
            .as('Animal__out_Animal_FedAt___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_filter_on_optional_variable_name_or_alias(self) -> None:
        # The operand in the @filter directive originates from an optional block.
        test_data = test_input_data.filter_on_optional_variable_name_or_alias()

        expected_match = """
            SELECT
                Animal__out_Animal_ParentOf___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    optional: true,
                    as: Animal__in_Animal_ParentOf___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    where: ((
                        ($matched.Animal__in_Animal_ParentOf___1 IS null) OR
                        (
                            (name = $matched.Animal__in_Animal_ParentOf___1.name) OR
                            (alias CONTAINS $matched.Animal__in_Animal_ParentOf___1.name)
                        )
                    )),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (Animal___1.in_Animal_ParentOf IS null)
                    OR
                    (Animal___1.in_Animal_ParentOf.size() = 0)
                )
                OR
                (Animal__in_Animal_ParentOf___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
            .as('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .out('Animal_ParentOf')
            .filter{it, m -> (
                (m.Animal__in_Animal_ParentOf___1 == null) ||
                (
                    (it.name == m.Animal__in_Animal_ParentOf___1.name) ||
                    it.alias.contains(m.Animal__in_Animal_ParentOf___1.name)
                )
            )}
            .as('Animal__out_Animal_ParentOf___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal__out_Animal_ParentOf___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_filter_in_optional_block(self) -> None:
        test_data = test_input_data.filter_in_optional_block()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                if(eval("(Animal__out_Animal_ParentOf___1 IS NOT null)"),
                   Animal__out_Animal_ParentOf___1.name, null) AS `parent_name`,
                if(eval("(Animal__out_Animal_ParentOf___1 IS NOT null)"),
                   Animal__out_Animal_ParentOf___1.uuid, null) AS `uuid`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    where: ((name = {name})),
                    optional: true,
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (Animal___1.out_Animal_ParentOf IS null)
                    OR
                    (Animal___1.out_Animal_ParentOf.size() = 0)
                )
                OR
                (Animal__out_Animal_ParentOf___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .ifThenElse{it.out_Animal_ParentOf == null}{null}{it.out('Animal_ParentOf')}
            .filter{it, m -> ((it == null) || (it.name == $name))}
            .as('Animal__out_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                parent_name: ((m.Animal__out_Animal_ParentOf___1 != null) ?
                                 m.Animal__out_Animal_ParentOf___1.name : null),
                uuid: ((m.Animal__out_Animal_ParentOf___1 != null) ?
                          m.Animal__out_Animal_ParentOf___1.uuid : null)
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                [Animal_2].name AS parent_name,
                [Animal_2].uuid AS uuid
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].uuid = [Animal_2].parent
            WHERE
                [Animal_2].name = :name OR [Animal_2].parent IS NULL
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            WITH
                Animal___1 AS Animal___1,
                Animal__out_Animal_ParentOf___1 AS Animal__out_Animal_ParentOf___1
            WHERE (
                (Animal__out_Animal_ParentOf___1 IS null) OR
                (Animal__out_Animal_ParentOf___1.name = $name)
            )
            RETURN
                Animal___1.name AS `animal_name`,
                (
                    CASE WHEN (Animal__out_Animal_ParentOf___1 IS NOT null)
                    THEN Animal__out_Animal_ParentOf___1.name
                    ELSE null
                    END
                ) AS `parent_name`,
                (
                    CASE WHEN (Animal__out_Animal_ParentOf___1 IS NOT null)
                    THEN Animal__out_Animal_ParentOf___1.uuid
                    ELSE null
                    END
                ) AS `uuid`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                "Animal_2".name AS parent_name,
                "Animal_2".uuid AS uuid
            FROM
                schema_1."Animal" AS "Animal_1"
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".uuid = "Animal_2".parent
            WHERE
                "Animal_2".name = :name OR "Animal_2".parent IS NULL
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_filter_in_optional_and_count(self) -> None:
        test_data = test_input_data.filter_in_optional_and_count()

        expected_match = """
            SELECT
                Species___1.name AS `species_name`
            FROM (
                MATCH {{
                    class: Species,
                    as: Species___1
                }}.in('Animal_OfSpecies') {{
                   where: ((name = {animal_name})),
                   optional: true,
                   as: Species__in_Animal_OfSpecies___1
                }}
                RETURN $matches
            )
            LET $Species___1___in_Species_Eats = Species___1.in("Species_Eats").asList()
            WHERE (
                (
                    $Species___1___in_Species_Eats.size() >= {predators}
                ) AND (
                    (
                        (
                            Species___1.in_Animal_OfSpecies IS null
                        ) OR (
                            Species___1.in_Animal_OfSpecies.size() = 0
                        )
                    ) OR (
                        Species__in_Animal_OfSpecies___1 IS NOT null
                    )
                )
            )
        """
        expected_gremlin = NotImplementedError
        expected_mssql = NotImplementedError
        expected_cypher = NotImplementedError
        expected_postgresql = """
            SELECT
                "Species_1".name AS species_name
            FROM schema_1."Species" AS "Species_1"
            LEFT OUTER JOIN schema_1."Animal" AS "Animal_1"
            ON "Species_1".uuid = "Animal_1".species
            LEFT OUTER JOIN (
                SELECT
                    "Species_2".uuid AS uuid,
                    coalesce(count(*), 0) AS fold_output__x_count
                FROM schema_1."Species" AS "Species_2"
                JOIN schema_1."Species" AS "Species_3"
                ON "Species_2".uuid = "Species_3".eats
                GROUP BY "Species_2".uuid
              ) AS folded_subquery_1
            ON "Species_1".uuid = folded_subquery_1.uuid
            WHERE
                ("Animal_1".name = :animal_name OR "Animal_1".species IS NULL) AND
                folded_subquery_1.fold_output__x_count >= :predators
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_between_filter_on_simple_scalar(self) -> None:
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a simple scalar (a String).
        test_data = test_input_data.between_filter_on_simple_scalar()

        expected_match = """
            SELECT
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((name BETWEEN {lower} AND {upper})),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> ((it.name >= $lower) && (it.name <= $upper))}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                [Animal_1].name >= :lower
                AND [Animal_1].name <= :upper
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE ((Animal___1.name >= $lower) AND (Animal___1.name <= $upper))
            RETURN
                Animal___1.name AS `name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS name
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                "Animal_1".name >= :lower
                AND "Animal_1".name <= :upper
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_between_filter_on_date(self) -> None:
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a custom scalar (Date).
        test_data = test_input_data.between_filter_on_date()

        expected_match = """
            SELECT
                Animal___1.birthday.format("yyyy-MM-dd") AS `birthday`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((
                        birthday BETWEEN
                            date({lower}, "yyyy-MM-dd") AND date({upper}, "yyyy-MM-dd")
                    )),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (
                (it.birthday >= Date.parse("yyyy-MM-dd", $lower)) &&
                (it.birthday <= Date.parse("yyyy-MM-dd", $upper))
            )}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                birthday: m.Animal___1.birthday.format("yyyy-MM-dd")
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].birthday AS birthday
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                [Animal_1].birthday >= :lower
                AND [Animal_1].birthday <= :upper
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE ((Animal___1.birthday >= $lower) AND
                       (Animal___1.birthday <= $upper))
            RETURN
                Animal___1.birthday AS `birthday`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".birthday AS birthday
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                "Animal_1".birthday >= :lower
                AND "Animal_1".birthday <= :upper
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_between_filter_on_datetime(self) -> None:
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a custom scalar (DateTime).
        test_data = test_input_data.between_filter_on_datetime()

        expected_match = """
            SELECT
                Event___1.event_date.format("yyyy-MM-dd'T'HH:mm:ss") AS `event_date`
            FROM (
                MATCH {{
                    class: Event,
                    where: ((
                        event_date BETWEEN
                            date({lower}, "yyyy-MM-dd'T'HH:mm:ss")
                            AND date({upper}, "yyyy-MM-dd'T'HH:mm:ss")
                    )),
                    as: Event___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Event')
            .filter{it, m -> (
                (it.event_date >= Date.parse("yyyy-MM-dd'T'HH:mm:ss", $lower)) &&
                (it.event_date <= Date.parse("yyyy-MM-dd'T'HH:mm:ss", $upper))
            )}
            .as('Event___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                event_date: m.Event___1.event_date.format("yyyy-MM-dd'T'HH:mm:ss")
            ])}
        """
        expected_mssql = """
            SELECT
                [Event_1].event_date AS event_date
            FROM
                db_2.schema_1.[Event] AS [Event_1]
            WHERE
                [Event_1].event_date >= :lower
                AND [Event_1].event_date <= :upper
        """
        expected_cypher = """
            MATCH (Event___1:Event)
                WHERE ((Event___1.event_date >= $lower) AND
                       (Event___1.event_date <= $upper))
            RETURN
                Event___1.event_date AS `event_date`
        """
        expected_postgresql = """
            SELECT
                "Event_1".event_date AS event_date
            FROM
                schema_1."Event" AS "Event_1"
            WHERE
                "Event_1".event_date >= :lower
                AND "Event_1".event_date <= :upper
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_between_lowering_on_simple_scalar(self) -> None:
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a simple scalar (a String).
        test_data = test_input_data.between_lowering_on_simple_scalar()

        expected_match = """
            SELECT
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((name BETWEEN {lower} AND {upper})),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> ((it.name <= $upper) && (it.name >= $lower))}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                [Animal_1].name <= :upper
                AND [Animal_1].name >= :lower
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE ((Animal___1.name <= $upper) AND (Animal___1.name >= $lower))
            RETURN
                Animal___1.name AS `name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS name
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                "Animal_1".name <= :upper
                AND "Animal_1".name >= :lower
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_between_lowering_with_extra_filters(self) -> None:
        test_data = test_input_data.between_lowering_with_extra_filters()

        expected_match = """
            SELECT
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((
                        (name BETWEEN {lower} AND {upper})
                        AND
                        (
                            (name LIKE ('%' + ({substring} + '%')))
                            AND
                            ({fauna} CONTAINS name)
                        )
                    )),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (
                (
                    ((it.name <= $upper) && it.name.contains($substring))
                    &&
                    $fauna.contains(it.name)
                )
                &&
                (it.name >= $lower)
            )}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                [Animal_1].name <= :upper
                AND ([Animal_1].name LIKE '%' + :substring + '%')
                AND [Animal_1].name IN :fauna
                AND [Animal_1].name >= :lower
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE (
                    (
                        ((Animal___1.name <= $upper) AND (Animal___1.name CONTAINS $substring)) AND
                        (Animal___1.name IN $fauna)
                    ) AND (Animal___1.name >= $lower)
                )
            RETURN
                Animal___1.name AS `name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS name
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                "Animal_1".name <= :upper
                AND ("Animal_1".name LIKE '%%' || :substring || '%%')
                AND "Animal_1".name IN :fauna
                AND "Animal_1".name >= :lower
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_no_between_lowering_on_simple_scalar(self) -> None:
        test_data = test_input_data.no_between_lowering_on_simple_scalar()

        expected_match = """
            SELECT
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((((name <= {upper}) AND (name >= {lower0})) AND (name >= {lower1}))),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
           g.V('@class', 'Animal')
           .filter{it, m -> (((it.name <= $upper) && (it.name >= $lower0)) && (it.name >= $lower1))}
           .as('Animal___1')
           .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
               name: m.Animal___1.name
           ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                [Animal_1].name <= :upper
                AND [Animal_1].name >= :lower0
                AND [Animal_1].name >= :lower1
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE (
                    ((Animal___1.name <= $upper) AND (Animal___1.name >= $lower0)) AND
                    (Animal___1.name >= $lower1)
                )
            RETURN
                Animal___1.name AS `name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS name
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                "Animal_1".name <= :upper
                AND "Animal_1".name >= :lower0
                AND "Animal_1".name >= :lower1
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_complex_optional_variables(self) -> None:
        # The operands in the @filter directives originate from an optional block,
        # in addition to having very complex filtering logic.
        test_data = test_input_data.complex_optional_variables()

        expected_match = """
            SELECT
                if(
                    eval("(Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)"),
                    Animal__out_Animal_ParentOf__out_Animal_FedAt___1.event_date
                        .format("yyyy-MM-dd'T'HH:mm:ss"),
                    null
                ) AS `child_fed_at`,
                Animal__in_Animal_ParentOf__out_Animal_FedAt___1
                    .event_date.format("yyyy-MM-dd'T'HH:mm:ss") AS `grandparent_fed_at`,
                if(
                    eval("(Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        IS NOT null)"),
                    Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        .event_date.format("yyyy-MM-dd'T'HH:mm:ss"),
                    null
                ) AS `other_parent_fed_at`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    class: Animal,
                    as: Animal__out_Animal_ParentOf___1
                }}.out('Animal_FedAt') {{
                    optional: true,
                    as: Animal__out_Animal_ParentOf__out_Animal_FedAt___1
                }} , {{
                    class: Animal,
                    as: Animal__out_Animal_ParentOf___1
                }}.in('Animal_ParentOf') {{
                    class: Animal,
                    as: Animal__out_Animal_ParentOf__in_Animal_ParentOf___1
                }}.out('Animal_FedAt') {{
                    optional: true,
                    as: Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    class: Animal,
                    as: Animal__in_Animal_ParentOf___1
                }}.out('Animal_FedAt') {{
                    where: ((
                        (
                            ($matched.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS null)
                            OR
                            (name = $matched.Animal__out_Animal_ParentOf__out_Animal_FedAt___1.name)
                        )
                        AND
                        (
                            (
                                ($matched.Animal__out_Animal_ParentOf__in_Animal_ParentOf
                                        __out_Animal_FedAt___1
                                    IS null)
                                OR
                                (event_date >= $matched.Animal__out_Animal_ParentOf
                                    __in_Animal_ParentOf__out_Animal_FedAt___1 .event_date)
                            )
                            AND
                            (
                                ($matched.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS null)
                                OR
                                (event_date <= $matched.Animal__out_Animal_ParentOf
                                    __out_Animal_FedAt___1.event_date)
                            )
                        )
                    )),
                    as: Animal__in_Animal_ParentOf__out_Animal_FedAt___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (
                        (Animal__out_Animal_ParentOf__in_Animal_ParentOf___1
                            .out_Animal_FedAt IS null)
                        OR
                        (Animal__out_Animal_ParentOf__in_Animal_ParentOf___1
                            .out_Animal_FedAt.size() = 0)
                    )
                    OR
                    (Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        IS NOT null)
                )
                AND
                (
                    (
                        (Animal__out_Animal_ParentOf___1.out_Animal_FedAt IS null)
                        OR
                        (Animal__out_Animal_ParentOf___1.out_Animal_FedAt.size() = 0)
                    )
                    OR
                    (Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)
                )
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .out('Animal_ParentOf')
                .as('Animal__out_Animal_ParentOf___1')
                    .ifThenElse{it.out_Animal_FedAt == null}{null}{it.out('Animal_FedAt')}
                    .as('Animal__out_Animal_ParentOf__out_Animal_FedAt___1')
                .optional('Animal__out_Animal_ParentOf___1')
                .as('Animal__out_Animal_ParentOf___2')
                    .in('Animal_ParentOf')
                    .as('Animal__out_Animal_ParentOf__in_Animal_ParentOf___1')
                        .ifThenElse{it.out_Animal_FedAt == null}{null}{it.out('Animal_FedAt')}
                        .as('Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1')
                    .optional('Animal__out_Animal_ParentOf__in_Animal_ParentOf___1')
                    .as('Animal__out_Animal_ParentOf__in_Animal_ParentOf___2')
                .back('Animal__out_Animal_ParentOf___2')
            .back('Animal___1')
                .in('Animal_ParentOf')
                .as('Animal__in_Animal_ParentOf___1')
                    .out('Animal_FedAt')
                    .filter{it, m -> (
                        (
                            (m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 == null) ||
                            (it.name == m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1.name)
                        )
                        &&
                        (
                            (
                                (m.Animal__out_Animal_ParentOf__in_Animal_ParentOf
                                    __out_Animal_FedAt___1 == null)
                                ||
                                (it.event_date >= m.Animal__out_Animal_ParentOf
                                    __in_Animal_ParentOf__out_Animal_FedAt___1.event_date)
                            )
                            &&
                            (
                                (m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 == null)
                                ||
                                (it.event_date <= m.Animal__out_Animal_ParentOf
                                    __out_Animal_FedAt___1.event_date)
                            )
                        )
                    )}
                    .as('Animal__in_Animal_ParentOf__out_Animal_FedAt___1')
                .back('Animal__in_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_fed_at: (
                    (m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 != null) ?
                    m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1.event_date
                        .format("yyyy-MM-dd'T'HH:mm:ss") :
                    null
                ),
                grandparent_fed_at: m.Animal__in_Animal_ParentOf__out_Animal_FedAt___1.event_date
                    .format("yyyy-MM-dd'T'HH:mm:ss"),
                other_parent_fed_at: (
                    (m.Animal__out_Animal_ParentOf__in_Animal_ParentOf
                        __out_Animal_FedAt___1 != null) ?
                    m.Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        .event_date.format("yyyy-MM-dd'T'HH:mm:ss") :
                    null
                )
            ])}
        """
        expected_mssql = """
            SELECT
                [FeedingEvent_1].event_date AS child_fed_at,
                [FeedingEvent_2].event_date AS grandparent_fed_at,
                [FeedingEvent_3].event_date AS other_parent_fed_at
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].uuid = [Animal_2].parent
                LEFT OUTER JOIN db_2.schema_1.[FeedingEvent] AS [FeedingEvent_1]
                    ON [Animal_2].fed_at = [FeedingEvent_1].uuid
                JOIN db_1.schema_1.[Animal] AS [Animal_3]
                    ON [Animal_2].parent = [Animal_3].uuid
                LEFT OUTER JOIN db_2.schema_1.[FeedingEvent] AS [FeedingEvent_3]
                    ON [Animal_3].fed_at = [FeedingEvent_3].uuid
                JOIN db_1.schema_1.[Animal] AS [Animal_4]
                    ON [Animal_1].parent = [Animal_4].uuid
                JOIN db_2.schema_1.[FeedingEvent] AS [FeedingEvent_2]
                    ON [Animal_4].fed_at = [FeedingEvent_2].uuid
            WHERE (
                [FeedingEvent_1].uuid IS NULL OR
                [FeedingEvent_2].name = [FeedingEvent_1].name
            ) AND (
                [FeedingEvent_3].uuid IS NULL OR
                [FeedingEvent_2].event_date >= [FeedingEvent_3].event_date
            ) AND (
                [FeedingEvent_1].uuid IS NULL OR
                [FeedingEvent_2].event_date <= [FeedingEvent_1].event_date
            )
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH (Animal__out_Animal_ParentOf___1)-[:Animal_FedAt]->
                (Animal__out_Animal_ParentOf__out_Animal_FedAt___1:FeedingEvent)
            MATCH (Animal__out_Animal_ParentOf___1)<-[:Animal_ParentOf]-
                (Animal__out_Animal_ParentOf__in_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH (Animal__out_Animal_ParentOf__in_Animal_ParentOf___1)-[:Animal_FedAt]->
                (Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1:FeedingEvent)
            MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            MATCH (Animal__in_Animal_ParentOf___1)-[:Animal_FedAt]->
                (Animal__in_Animal_ParentOf__out_Animal_FedAt___1:FeedingEvent)
                WHERE (
                    (
                        (Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS null) OR
                        (Animal__in_Animal_ParentOf__out_Animal_FedAt___1.name =
                            Animal__out_Animal_ParentOf__out_Animal_FedAt___1.name)
                    ) AND (
                        (
                            (Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                                IS null)
                            OR
                            (Animal__in_Animal_ParentOf__out_Animal_FedAt___1.event_date >=
                                Animal__out_Animal_ParentOf
                                __in_Animal_ParentOf__out_Animal_FedAt___1.event_date)
                        )
                        AND
                        (
                            (Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS null)
                            OR
                            (Animal__in_Animal_ParentOf__out_Animal_FedAt___1.event_date <=
                                Animal__out_Animal_ParentOf__out_Animal_FedAt___1.event_date)
                        )
                    )
                )
            RETURN
                (
                    CASE WHEN (Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)
                    THEN Animal__out_Animal_ParentOf__out_Animal_FedAt___1.event_date
                    ELSE null
                    END
                ) AS `child_fed_at`,
                Animal__in_Animal_ParentOf__out_Animal_FedAt___1.event_date AS `grandparent_fed_at`,
                (
                    CASE WHEN (
                        Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        IS NOT null
                    )
                    THEN Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        .event_date
                    ELSE null
                    END
                ) AS `other_parent_fed_at`
        """
        expected_postgresql = """
            SELECT
                "FeedingEvent_1".event_date AS child_fed_at,
                "FeedingEvent_2".event_date AS grandparent_fed_at,
                "FeedingEvent_3".event_date AS other_parent_fed_at
            FROM
                schema_1."Animal" AS "Animal_1"
                JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".uuid = "Animal_2".parent
                LEFT OUTER JOIN schema_1."FeedingEvent" AS "FeedingEvent_1"
                    ON "Animal_2".fed_at = "FeedingEvent_1".uuid
                JOIN schema_1."Animal" AS "Animal_3"
                    ON "Animal_2".parent = "Animal_3".uuid
                LEFT OUTER JOIN schema_1."FeedingEvent" AS "FeedingEvent_3"
                    ON "Animal_3".fed_at = "FeedingEvent_3".uuid
                JOIN schema_1."Animal" AS "Animal_4"
                    ON "Animal_1".parent = "Animal_4".uuid
                JOIN schema_1."FeedingEvent" AS "FeedingEvent_2"
                    ON "Animal_4".fed_at = "FeedingEvent_2".uuid
            WHERE (
                "FeedingEvent_1".uuid IS NULL OR
                "FeedingEvent_2".name = "FeedingEvent_1".name
            ) AND (
                "FeedingEvent_3".uuid IS NULL OR
                "FeedingEvent_2".event_date >= "FeedingEvent_3".event_date
            ) AND (
                "FeedingEvent_1".uuid IS NULL OR
                "FeedingEvent_2".event_date <= "FeedingEvent_1".event_date
            )
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_complex_optional_variables_with_starting_filter(self) -> None:
        # The operands in the @filter directives originate from an optional block,
        # in addition to having very complex filtering logic.
        test_data = test_input_data.complex_optional_variables_with_starting_filter()

        expected_match = """
            SELECT
                if(
                    eval("(Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)"),
                    Animal__out_Animal_ParentOf__out_Animal_FedAt___1.event_date
                        .format("yyyy-MM-dd'T'HH:mm:ss"),
                    null
                ) AS `child_fed_at`,
                Animal__in_Animal_ParentOf__out_Animal_FedAt___1
                    .event_date.format("yyyy-MM-dd'T'HH:mm:ss") AS `grandparent_fed_at`,
                if(
                    eval("(Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        IS NOT null)"),
                    Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        .event_date.format("yyyy-MM-dd'T'HH:mm:ss"),
                    null
                ) AS `other_parent_fed_at`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((name = {animal_name})),
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    as: Animal__out_Animal_ParentOf___1
                }}.out('Animal_FedAt') {{
                    optional: true,
                    as: Animal__out_Animal_ParentOf__out_Animal_FedAt___1
                }} , {{
                    where: ((@this INSTANCEOF 'Animal')),
                    as: Animal__out_Animal_ParentOf___1
                }}.in('Animal_ParentOf') {{
                    as: Animal__out_Animal_ParentOf__in_Animal_ParentOf___1
                }}.out('Animal_FedAt') {{
                    optional: true,
                    as: Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    as: Animal__in_Animal_ParentOf___1
                }}.out('Animal_FedAt') {{
                    where: ((
                        (
                            ($matched.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS null)
                            OR
                            (name = $matched.Animal__out_Animal_ParentOf__out_Animal_FedAt___1.name)
                        )
                        AND
                        (
                            (
                                ($matched.Animal__out_Animal_ParentOf__in_Animal_ParentOf
                                        __out_Animal_FedAt___1
                                    IS null)
                                OR
                                (event_date >= $matched.Animal__out_Animal_ParentOf
                                    __in_Animal_ParentOf__out_Animal_FedAt___1 .event_date)
                            )
                            AND
                            (
                                ($matched.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS null)
                                OR
                                (event_date <= $matched.Animal__out_Animal_ParentOf
                                    __out_Animal_FedAt___1.event_date)
                            )
                        )
                    )),
                    as: Animal__in_Animal_ParentOf__out_Animal_FedAt___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (
                        (Animal__out_Animal_ParentOf__in_Animal_ParentOf___1
                            .out_Animal_FedAt IS null)
                        OR
                        (Animal__out_Animal_ParentOf__in_Animal_ParentOf___1
                            .out_Animal_FedAt.size() = 0)
                    )
                    OR
                    (Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        IS NOT null)
                )
                AND
                (
                    (
                        (Animal__out_Animal_ParentOf___1.out_Animal_FedAt IS null)
                        OR
                        (Animal__out_Animal_ParentOf___1.out_Animal_FedAt.size() = 0)
                    )
                    OR
                    (Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)
                )
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (it.name == $animal_name)}
            .as('Animal___1')
                .out('Animal_ParentOf')
                .as('Animal__out_Animal_ParentOf___1')
                    .ifThenElse{it.out_Animal_FedAt == null}{null}{it.out('Animal_FedAt')}
                    .as('Animal__out_Animal_ParentOf__out_Animal_FedAt___1')
                .optional('Animal__out_Animal_ParentOf___1')
                .as('Animal__out_Animal_ParentOf___2')
                    .in('Animal_ParentOf')
                    .as('Animal__out_Animal_ParentOf__in_Animal_ParentOf___1')
                        .ifThenElse{it.out_Animal_FedAt == null}{null}{it.out('Animal_FedAt')}
                        .as('Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1')
                    .optional('Animal__out_Animal_ParentOf__in_Animal_ParentOf___1')
                    .as('Animal__out_Animal_ParentOf__in_Animal_ParentOf___2')
                .back('Animal__out_Animal_ParentOf___2')
            .back('Animal___1')
                .in('Animal_ParentOf')
                .as('Animal__in_Animal_ParentOf___1')
                    .out('Animal_FedAt')
                    .filter{it, m -> (
                        (
                            (m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 == null) ||
                            (it.name == m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1.name)
                        )
                        &&
                        (
                            (
                                (m.Animal__out_Animal_ParentOf__in_Animal_ParentOf
                                    __out_Animal_FedAt___1 == null)
                                ||
                                (it.event_date >= m.Animal__out_Animal_ParentOf
                                    __in_Animal_ParentOf__out_Animal_FedAt___1.event_date)
                            )
                            &&
                            (
                                (m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 == null)
                                ||
                                (it.event_date <= m.Animal__out_Animal_ParentOf
                                    __out_Animal_FedAt___1.event_date)
                            )
                        )
                    )}
                    .as('Animal__in_Animal_ParentOf__out_Animal_FedAt___1')
                .back('Animal__in_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_fed_at: (
                    (m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 != null) ?
                    m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1.event_date
                        .format("yyyy-MM-dd'T'HH:mm:ss") :
                    null
                ),
                grandparent_fed_at: m.Animal__in_Animal_ParentOf__out_Animal_FedAt___1.event_date
                    .format("yyyy-MM-dd'T'HH:mm:ss"),
                other_parent_fed_at: (
                    (m.Animal__out_Animal_ParentOf__in_Animal_ParentOf
                        __out_Animal_FedAt___1 != null) ?
                    m.Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        .event_date.format("yyyy-MM-dd'T'HH:mm:ss") :
                    null
                )
            ])}
        """
        expected_mssql = """
            SELECT
                [FeedingEvent_1].event_date AS child_fed_at,
                [FeedingEvent_2].event_date AS grandparent_fed_at,
                [FeedingEvent_3].event_date AS other_parent_fed_at
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].uuid = [Animal_2].parent
                LEFT OUTER JOIN db_2.schema_1.[FeedingEvent] AS [FeedingEvent_1]
                    ON [Animal_2].fed_at = [FeedingEvent_1].uuid
                JOIN db_1.schema_1.[Animal] AS [Animal_3]
                    ON [Animal_2].parent = [Animal_3].uuid
                LEFT OUTER JOIN db_2.schema_1.[FeedingEvent] AS [FeedingEvent_3]
                    ON [Animal_3].fed_at = [FeedingEvent_3].uuid
                JOIN db_1.schema_1.[Animal] AS [Animal_4]
                    ON [Animal_1].parent = [Animal_4].uuid
                JOIN db_2.schema_1.[FeedingEvent] AS [FeedingEvent_2]
                    ON [Animal_4].fed_at = [FeedingEvent_2].uuid
            WHERE
                [Animal_1].name = :animal_name AND (
                    [FeedingEvent_1].uuid IS NULL OR
                    [FeedingEvent_2].name = [FeedingEvent_1].name
                ) AND (
                    [FeedingEvent_3].uuid IS NULL OR
                    [FeedingEvent_2].event_date >= [FeedingEvent_3].event_date
                ) AND (
                    [FeedingEvent_1].uuid IS NULL OR
                    [FeedingEvent_2].event_date <= [FeedingEvent_1].event_date
                )
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "FeedingEvent_1".event_date AS child_fed_at,
                "FeedingEvent_2".event_date AS grandparent_fed_at,
                "FeedingEvent_3".event_date AS other_parent_fed_at
            FROM
                schema_1."Animal" AS "Animal_1"
                JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".uuid = "Animal_2".parent
                LEFT OUTER JOIN schema_1."FeedingEvent" AS "FeedingEvent_1"
                    ON "Animal_2".fed_at = "FeedingEvent_1".uuid
                JOIN schema_1."Animal" AS "Animal_3"
                    ON "Animal_2".parent = "Animal_3".uuid
                LEFT OUTER JOIN schema_1."FeedingEvent" AS "FeedingEvent_3"
                    ON "Animal_3".fed_at = "FeedingEvent_3".uuid
                JOIN schema_1."Animal" AS "Animal_4"
                    ON "Animal_1".parent = "Animal_4".uuid
                JOIN schema_1."FeedingEvent" AS "FeedingEvent_2"
                    ON "Animal_4".fed_at = "FeedingEvent_2".uuid
            WHERE
                "Animal_1".name = :animal_name AND (
                    "FeedingEvent_1".uuid IS NULL OR
                    "FeedingEvent_2".name = "FeedingEvent_1".name
                ) AND (
                    "FeedingEvent_3".uuid IS NULL OR
                    "FeedingEvent_2".event_date >= "FeedingEvent_3".event_date
                ) AND (
                    "FeedingEvent_1".uuid IS NULL OR
                    "FeedingEvent_2".event_date <= "FeedingEvent_1".event_date
                )
        """
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_simple_fragment(self) -> None:
        test_data = test_input_data.simple_fragment()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                Animal__out_Entity_Related___1.name AS `related_animal_name`,
                Animal__out_Entity_Related__out_Animal_OfSpecies___1.name
                    AS `related_animal_species`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Entity_Related') {{
                    class: Animal,
                    as: Animal__out_Entity_Related___1
                }}.out('Animal_OfSpecies') {{
                    class: Species,
                    as: Animal__out_Entity_Related__out_Animal_OfSpecies___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Entity_Related')
            .filter{it, m -> ['Animal'].contains(it['@class'])}
            .as('Animal__out_Entity_Related___1')
            .out('Animal_OfSpecies')
            .as('Animal__out_Entity_Related__out_Animal_OfSpecies___1')
            .back('Animal__out_Entity_Related___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                related_animal_name: m.Animal__out_Entity_Related___1.name,
                related_animal_species: m.Animal__out_Entity_Related__out_Animal_OfSpecies___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_typename_output(self) -> None:
        test_data = test_input_data.typename_output()

        expected_match = """
            SELECT
                Animal___1.@class AS `base_cls`,
                Animal__out_Animal_OfSpecies___1.@class AS `child_cls`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_OfSpecies') {{
                    class: Species,
                    as: Animal__out_Animal_OfSpecies___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_OfSpecies')
            .as('Animal__out_Animal_OfSpecies___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                base_cls: m.Animal___1['@class'],
                child_cls: m.Animal__out_Animal_OfSpecies___1['@class']
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_typename_filter(self) -> None:
        test_data = test_input_data.typename_filter()

        expected_match = """
            SELECT
                Entity___1.name AS `entity_name`
            FROM (
                MATCH {{
                    class: Entity,
                    where: ((@class = {base_cls})),
                    as: Entity___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Entity')
            .filter{it, m -> (it['@class'] == $base_cls)}
            .as('Entity___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                entity_name: m.Entity___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_simple_recurse(self) -> None:
        test_data = test_input_data.simple_recurse()

        expected_match = """
            SELECT
                Animal__out_Animal_ParentOf___1.name AS `relation_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    while: ($depth < 1),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .copySplit(
                _(),
                _().out('Animal_ParentOf')
            )
            .exhaustMerge
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                relation_name: m.Animal__out_Animal_ParentOf___1.name
            ])}
        """
        expected_mssql = """
            WITH anon_1(name, parent, uuid, __cte_key, __cte_depth) AS (
                SELECT
                    [Animal_2].name AS name,
                    [Animal_2].parent AS parent,
                    [Animal_2].uuid AS uuid,
                    [Animal_2].uuid AS __cte_key,
                    0 AS __cte_depth
                FROM
                    db_1.schema_1.[Animal] AS [Animal_2]
                UNION ALL
                SELECT
                    [Animal_3].name AS name,
                    [Animal_3].parent AS parent,
                    [Animal_3].uuid AS uuid,
                    anon_1.__cte_key AS __cte_key,
                    anon_1.__cte_depth + 1 AS __cte_depth
                FROM
                    anon_1
                    JOIN db_1.schema_1.[Animal] AS [Animal_3]
                        ON anon_1.uuid = [Animal_3].parent
                WHERE
                    anon_1.__cte_depth < 1
            )
            SELECT
                anon_1.name AS relation_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                JOIN anon_1
                    ON [Animal_1].uuid = anon_1.__cte_key
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)-[:Animal_ParentOf*0..1]->(Animal__out_Animal_ParentOf___1:Animal)
            RETURN Animal__out_Animal_ParentOf___1.name AS `relation_name`
        """
        expected_postgresql = """
            WITH RECURSIVE anon_1(name, parent, uuid, __cte_key, __cte_depth) AS (
                SELECT
                    "Animal_2".name AS name,
                    "Animal_2".parent AS parent,
                    "Animal_2".uuid AS uuid,
                    "Animal_2".uuid AS __cte_key,
                    0 AS __cte_depth
                FROM
                    schema_1."Animal" AS "Animal_2"
                UNION ALL
                SELECT
                    "Animal_3".name AS name,
                    "Animal_3".parent AS parent,
                    "Animal_3".uuid AS uuid,
                    anon_1.__cte_key AS __cte_key,
                    anon_1.__cte_depth + 1 AS __cte_depth
                FROM
                    anon_1
                    JOIN schema_1."Animal" AS "Animal_3"
                        ON anon_1.uuid = "Animal_3".parent
                WHERE anon_1.__cte_depth < 1
            )
            SELECT
                anon_1.name AS relation_name
            FROM
                schema_1."Animal" AS "Animal_1"
                JOIN anon_1
                    ON "Animal_1".uuid = anon_1.__cte_key
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_inwards_recurse_after_traverse(self) -> None:
        test_data = test_input_data.inwards_recurse_after_traverse()

        expected_match = SKIP_TEST
        expected_gremlin = SKIP_TEST
        expected_mssql = """
            WITH anon_2 AS (
                SELECT
                    [Species_1].name AS [Species__name],
                    [Species_1].uuid AS [Species__uuid],
                    [Animal_1].name AS [Species_in_Animal_OfSpecies__name],
                    [Animal_1].parent AS [Species_in_Animal_OfSpecies__parent],
                    [Animal_1].species AS [Species_in_Animal_OfSpecies__species],
                    [Animal_1].uuid AS [Species_in_Animal_OfSpecies__uuid]
                FROM
                    db_1.schema_1.[Species] AS [Species_1]
                    JOIN db_1.schema_1.[Animal] AS [Animal_1]
                        ON [Species_1].uuid = [Animal_1].species
            ),
            anon_1(name, parent, uuid, __cte_key, __cte_depth) AS (
                SELECT
                    [Animal_2].name AS name,
                    [Animal_2].parent AS parent,
                    [Animal_2].uuid AS uuid,
                    [Animal_2].uuid AS __cte_key,
                    0 AS __cte_depth
                FROM
                    db_1.schema_1.[Animal] AS [Animal_2]
                WHERE
                    [Animal_2].uuid IN (
                        SELECT anon_2.[Species_in_Animal_OfSpecies__uuid] FROM anon_2
                    )
                UNION ALL
                    SELECT
                        [Animal_3].name AS name,
                        [Animal_3].parent AS parent,
                        [Animal_3].uuid AS uuid,
                        anon_1.__cte_key AS __cte_key,
                        anon_1.__cte_depth + 1 AS __cte_depth
                    FROM
                        anon_1
                        JOIN db_1.schema_1.[Animal] AS [Animal_3]
                            ON anon_1.parent = [Animal_3].uuid
                    WHERE anon_1.__cte_depth < 1
            )
            SELECT
                anon_1.name AS ancestor_name,
                anon_2.[Species_in_Animal_OfSpecies__name] AS animal_name,
                anon_2.[Species__name] AS species_name
            FROM
                anon_2
                JOIN anon_1
                    ON anon_2.[Species_in_Animal_OfSpecies__uuid] = anon_1.__cte_key
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
        WITH RECURSIVE anon_2 AS (
            SELECT
                "Species_1".name AS "Species__name",
                "Species_1".uuid AS "Species__uuid",
                "Animal_1".name AS "Species_in_Animal_OfSpecies__name",
                "Animal_1".parent AS "Species_in_Animal_OfSpecies__parent",
                "Animal_1".species AS "Species_in_Animal_OfSpecies__species",
                "Animal_1".uuid AS "Species_in_Animal_OfSpecies__uuid"
            FROM
                schema_1."Species" AS "Species_1"
                JOIN schema_1."Animal" AS "Animal_1"
                    ON "Species_1".uuid = "Animal_1".species),
        anon_1(name, parent, uuid, __cte_key, __cte_depth) AS (
            SELECT
                "Animal_2".name AS name,
                "Animal_2".parent AS parent,
                "Animal_2".uuid AS uuid,
                "Animal_2".uuid AS __cte_key,
                0 AS __cte_depth
            FROM
                schema_1."Animal" AS "Animal_2"
            WHERE
                "Animal_2".uuid IN (SELECT anon_2."Species_in_Animal_OfSpecies__uuid" FROM anon_2)
            UNION ALL
            SELECT
                "Animal_3".name AS name,
                "Animal_3".parent AS parent,
                "Animal_3".uuid AS uuid,
                anon_1.__cte_key AS __cte_key,
                anon_1.__cte_depth + 1 AS __cte_depth
            FROM
                anon_1
                JOIN schema_1."Animal" AS "Animal_3"
                    ON anon_1.parent = "Animal_3".uuid
            WHERE anon_1.__cte_depth < 1
        )
        SELECT
            anon_1.name AS ancestor_name,
            anon_2."Species_in_Animal_OfSpecies__name" AS animal_name,
            anon_2."Species__name" AS species_name
        FROM
            anon_2
            JOIN anon_1
                ON anon_2."Species_in_Animal_OfSpecies__uuid" = anon_1.__cte_key
        """
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_recurse_with_new_output_inside_recursion_and_filter_at_root(self) -> None:
        test_data = test_input_data.recurse_with_new_output_inside_recursion_and_filter_at_root()

        expected_match = SKIP_TEST
        expected_gremlin = SKIP_TEST
        expected_mssql = """
            WITH anon_2 AS (
                SELECT
                    [Animal_1].name AS [Animal__name],
                    [Animal_1].uuid AS [Animal__uuid]
                FROM
                    db_1.schema_1.[Animal] AS [Animal_1]
                WHERE
                    [Animal_1].name = :animal_name),
            anon_1(color, name, parent, uuid, __cte_key, __cte_depth) AS (
                SELECT
                    [Animal_2].color AS color,
                    [Animal_2].name AS name,
                    [Animal_2].parent AS parent,
                    [Animal_2].uuid AS uuid,
                    [Animal_2].uuid AS __cte_key,
                    0 AS __cte_depth
                FROM
                    db_1.schema_1.[Animal] AS [Animal_2]
                WHERE
                    [Animal_2].uuid IN (SELECT anon_2.[Animal__uuid] FROM anon_2)
                UNION ALL
                SELECT
                    [Animal_3].color AS color,
                    [Animal_3].name AS name,
                    [Animal_3].parent AS parent,
                    [Animal_3].uuid AS uuid,
                    anon_1.__cte_key AS __cte_key,
                    anon_1.__cte_depth + 1 AS __cte_depth
                FROM
                    anon_1
                JOIN db_1.schema_1.[Animal] AS [Animal_3] ON
                    anon_1.uuid = [Animal_3].parent
                WHERE
                    anon_1.__cte_depth < 1)
            SELECT
                anon_1.color AS animal_color,
                anon_1.name AS relation_name
            FROM
                anon_2
                JOIN anon_1
                    ON anon_2.[Animal__uuid] = anon_1.__cte_key
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_filter_then_recurse(self) -> None:
        test_data = test_input_data.filter_then_recurse()

        expected_match = SKIP_TEST
        expected_gremlin = SKIP_TEST
        expected_mssql = """
            WITH anon_2 AS (
                SELECT
                    [Animal_1].name AS [Animal__name],
                    [Animal_1].uuid AS [Animal__uuid]
                FROM
                    db_1.schema_1.[Animal] AS [Animal_1]
                WHERE
                    [Animal_1].name = :animal_name),
            anon_1(name, parent, uuid, __cte_key, __cte_depth) AS (
                SELECT
                    [Animal_2].name AS name,
                    [Animal_2].parent AS parent,
                    [Animal_2].uuid AS uuid,
                    [Animal_2].uuid AS __cte_key,
                    0 AS __cte_depth
                FROM
                    db_1.schema_1.[Animal] AS [Animal_2]
                WHERE
                    [Animal_2].uuid IN (SELECT anon_2.[Animal__uuid] FROM anon_2)
                UNION ALL
                SELECT
                    [Animal_3].name AS name,
                    [Animal_3].parent AS parent,
                    [Animal_3].uuid AS uuid,
                    anon_1.__cte_key AS __cte_key,
                    anon_1.__cte_depth + 1 AS __cte_depth
                FROM
                    anon_1
                    JOIN db_1.schema_1.[Animal] AS [Animal_3]
                        ON anon_1.uuid = [Animal_3].parent
                WHERE
                    anon_1.__cte_depth < 1)
            SELECT
                anon_1.name AS relation_name
            FROM
                anon_2
                JOIN anon_1
                    ON anon_2.[Animal__uuid] = anon_1.__cte_key
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_traverse_then_recurse(self) -> None:
        test_data = test_input_data.traverse_then_recurse()

        expected_match = """
            SELECT
                Animal__out_Animal_ParentOf___1.name AS `ancestor_name`,
                Animal___1.name AS `animal_name`,
                Animal__out_Animal_ImportantEvent___1.name AS `important_event`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ImportantEvent') {{
                    class: Event,
                    as: Animal__out_Animal_ImportantEvent___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    while: ($depth < 2),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_ImportantEvent')
            .filter{it, m -> ['Event'].contains(it['@class'])}
            .as('Animal__out_Animal_ImportantEvent___1')
            .back('Animal___1')
            .copySplit(
                _(),
                _().out('Animal_ParentOf'),
                _().out('Animal_ParentOf').out('Animal_ParentOf')
            )
            .exhaustMerge
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                ancestor_name: m.Animal__out_Animal_ParentOf___1.name,
                animal_name: m.Animal___1.name,
                important_event: m.Animal__out_Animal_ImportantEvent___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH
                (Animal___1)-[:Animal_ImportantEvent]->(Animal__out_Animal_ImportantEvent___1:Event)
            MATCH (Animal___1)-[:Animal_ParentOf*0..2]->(Animal__out_Animal_ParentOf___1:Animal)
            RETURN
                Animal__out_Animal_ParentOf___1.name AS `ancestor_name`,
                Animal___1.name AS `animal_name`,
                Animal__out_Animal_ImportantEvent___1.name AS `important_event`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_filter_then_traverse_and_recurse(self) -> None:
        test_data = test_input_data.filter_then_traverse_and_recurse()

        expected_match = """
            SELECT
                Animal__out_Animal_ParentOf___1.name AS `ancestor_name`,
                Animal___1.name AS `animal_name`,
                Animal__out_Animal_ImportantEvent___1.name AS `important_event`
            FROM (
                MATCH {{
                    class: Animal,
                    where: (
                        (
                            (name = {animal_name_or_alias})
                            OR
                            (alias CONTAINS {animal_name_or_alias})
                        )
                    ),
                    as: Animal___1
                }}.out('Animal_ImportantEvent') {{
                    where: ((@this INSTANCEOF 'Event')),
                    as: Animal__out_Animal_ImportantEvent___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    while: ($depth < 2),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (
                (it.name == $animal_name_or_alias) || it.alias.contains($animal_name_or_alias)
            )}
            .as('Animal___1')
            .out('Animal_ImportantEvent')
            .filter{it, m -> ['Event'].contains(it['@class'])}
            .as('Animal__out_Animal_ImportantEvent___1')
            .back('Animal___1')
            .copySplit(
                _(),
                _().out('Animal_ParentOf'),
                _().out('Animal_ParentOf').out('Animal_ParentOf')
            )
            .exhaustMerge
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                ancestor_name: m.Animal__out_Animal_ParentOf___1.name,
                animal_name: m.Animal___1.name,
                important_event: m.Animal__out_Animal_ImportantEvent___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE (
                    (Animal___1.name = $animal_name_or_alias) OR
                    ($animal_name_or_alias IN Animal___1.alias)
                )
            MATCH
                (Animal___1)-[:Animal_ImportantEvent]->(Animal__out_Animal_ImportantEvent___1:Event)
            MATCH (Animal___1)-[:Animal_ParentOf*0..2]->(Animal__out_Animal_ParentOf___1:Animal)
            RETURN
                Animal__out_Animal_ParentOf___1.name AS `ancestor_name`,
                Animal___1.name AS `animal_name`,
                Animal__out_Animal_ImportantEvent___1.name AS `important_event`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_two_consecutive_recurses(self) -> None:
        test_data = test_input_data.two_consecutive_recurses()

        expected_match = """
            SELECT
                Animal__out_Animal_ParentOf___1.name AS `ancestor_name`,
                Animal___1.name AS `animal_name`,
                Animal__in_Animal_ParentOf___1.name AS `descendent_name`,
                Animal__out_Animal_ImportantEvent___1.name AS `important_event`
            FROM (
                MATCH {{
                    class: Animal,
                    where: (
                        (
                            (name = {animal_name_or_alias})
                            OR
                            (alias CONTAINS {animal_name_or_alias})
                        )
                    ),
                    as: Animal___1
                }}.out('Animal_ImportantEvent') {{
                    where: ((@this INSTANCEOF 'Event')),
                    as: Animal__out_Animal_ImportantEvent___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    while: ($depth < 2),
                    as: Animal__out_Animal_ParentOf___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    while: ($depth < 2),
                    as: Animal__in_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (
                (it.name == $animal_name_or_alias) || it.alias.contains($animal_name_or_alias)
            )}
            .as('Animal___1')
            .out('Animal_ImportantEvent')
            .filter{it, m -> ['Event'].contains(it['@class'])}
            .as('Animal__out_Animal_ImportantEvent___1')
            .back('Animal___1')
            .copySplit(
                _(),
                _().out('Animal_ParentOf'),
                _().out('Animal_ParentOf').out('Animal_ParentOf')
            )
            .exhaustMerge
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .copySplit(
                _(),
                _().in('Animal_ParentOf'),
                _().in('Animal_ParentOf').in('Animal_ParentOf')
            )
            .exhaustMerge
            .as('Animal__in_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                ancestor_name: m.Animal__out_Animal_ParentOf___1.name,
                animal_name: m.Animal___1.name,
                descendent_name: m.Animal__in_Animal_ParentOf___1.name,
                important_event: m.Animal__out_Animal_ImportantEvent___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE (
                    (Animal___1.name = $animal_name_or_alias) OR
                    ($animal_name_or_alias IN Animal___1.alias)
                )
            MATCH
                (Animal___1)-[:Animal_ImportantEvent]->(Animal__out_Animal_ImportantEvent___1:Event)
            MATCH (Animal___1)-[:Animal_ParentOf*0..2]->(Animal__out_Animal_ParentOf___1:Animal)
            MATCH (Animal___1)<-[:Animal_ParentOf*0..2]-(Animal__in_Animal_ParentOf___1:Animal)
            RETURN
                Animal__out_Animal_ParentOf___1.name AS `ancestor_name`,
                Animal___1.name AS `animal_name`,
                Animal__in_Animal_ParentOf___1.name AS `descendent_name`,
                Animal__out_Animal_ImportantEvent___1.name AS `important_event`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_recurse_within_fragment(self) -> None:
        test_data = test_input_data.recurse_within_fragment()

        expected_match = """
            SELECT
                Food__in_Entity_Related___1.name AS `animal_name`,
                Food___1.name AS `food_name`,
                Food__in_Entity_Related__out_Animal_ParentOf___1.name AS `relation_name`
            FROM (
                MATCH {{
                    class: Food,
                    as: Food___1
                }}.in('Entity_Related') {{
                    class: Animal,
                    as: Food__in_Entity_Related___1
                }}.out('Animal_ParentOf') {{
                    while: ($depth < 3),
                    as: Food__in_Entity_Related__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Food')
            .as('Food___1')
            .in('Entity_Related')
            .filter{it, m -> ['Animal'].contains(it['@class'])}
            .as('Food__in_Entity_Related___1')
            .copySplit(
                _(),
                _().out('Animal_ParentOf'),
                _().out('Animal_ParentOf').out('Animal_ParentOf'),
                _().out('Animal_ParentOf').out('Animal_ParentOf').out('Animal_ParentOf')
            )
            .exhaustMerge
            .as('Food__in_Entity_Related__out_Animal_ParentOf___1')
            .back('Food__in_Entity_Related___1')
            .back('Food___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Food__in_Entity_Related___1.name,
                food_name: m.Food___1.name,
                relation_name: m.Food__in_Entity_Related__out_Animal_ParentOf___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_filter_within_recurse(self) -> None:
        test_data = test_input_data.filter_within_recurse()

        expected_match = """
            SELECT
                Animal__out_Animal_ParentOf___1.name AS `relation_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    while: ($depth < 3),
                    where: ((color = {wanted})),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .copySplit(
                _(),
                _().out('Animal_ParentOf'),
                _().out('Animal_ParentOf').out('Animal_ParentOf'),
                _().out('Animal_ParentOf').out('Animal_ParentOf').out('Animal_ParentOf')
            )
            .exhaustMerge
            .filter{it, m -> (it.color == $wanted)}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                relation_name: m.Animal__out_Animal_ParentOf___1.name
            ])}
        """
        expected_mssql = """
            WITH anon_1(color, name, parent, uuid, __cte_key, __cte_depth) AS (
                SELECT
                    [Animal_2].color AS color,
                    [Animal_2].name AS name,
                    [Animal_2].parent AS parent,
                    [Animal_2].uuid AS uuid,
                    [Animal_2].uuid AS __cte_key,
                    0 AS __cte_depth
                FROM
                    db_1.schema_1.[Animal] AS [Animal_2]
                UNION ALL
                SELECT
                    [Animal_3].color AS color,
                    [Animal_3].name AS name,
                    [Animal_3].parent AS parent,
                    [Animal_3].uuid AS uuid,
                    anon_1.__cte_key AS __cte_key,
                    anon_1.__cte_depth + 1 AS __cte_depth
                FROM
                    anon_1
                JOIN db_1.schema_1.[Animal] AS [Animal_3] ON
                    anon_1.uuid = [Animal_3].parent
                WHERE
                    anon_1.__cte_depth < 3)
            SELECT
                anon_1.name AS relation_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                JOIN anon_1 ON
                    [Animal_1].uuid = anon_1.__cte_key
            WHERE
                anon_1.color = :wanted
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            WITH RECURSIVE anon_1(color, name, parent, uuid, __cte_key, __cte_depth) AS (
                SELECT
                    "Animal_2".color AS color,
                    "Animal_2".name AS name,
                    "Animal_2".parent AS parent,
                    "Animal_2".uuid AS uuid,
                    "Animal_2".uuid AS __cte_key,
                    0 AS __cte_depth
                FROM
                    schema_1."Animal" AS "Animal_2"
                UNION ALL
                SELECT
                    "Animal_3".color AS color,
                    "Animal_3".name AS name,
                    "Animal_3".parent AS parent,
                    "Animal_3".uuid AS uuid,
                    anon_1.__cte_key AS __cte_key,
                    anon_1.__cte_depth + 1 AS __cte_depth
                FROM
                    anon_1
                    JOIN schema_1."Animal" AS "Animal_3"
                        ON anon_1.uuid = "Animal_3".parent
                WHERE anon_1.__cte_depth < 3)
            SELECT
                anon_1.name AS relation_name
            FROM
                schema_1."Animal" AS "Animal_1"
                JOIN anon_1
                    ON "Animal_1".uuid = anon_1.__cte_key
            WHERE
                anon_1.color = :wanted
        """
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_recurse_with_immediate_type_coercion(self) -> None:
        test_data = test_input_data.recurse_with_immediate_type_coercion()

        expected_match = """
            SELECT
                Animal__in_Entity_Related___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Entity_Related') {{
                    while: ($depth < 4),
                    where: ((@this INSTANCEOF 'Animal')),
                    as: Animal__in_Entity_Related___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .copySplit(
                _(),
                _().in('Entity_Related'),
                _().in('Entity_Related').in('Entity_Related'),
                _().in('Entity_Related').in('Entity_Related').in('Entity_Related'),
                _().in('Entity_Related').in('Entity_Related')
                   .in('Entity_Related').in('Entity_Related')
            )
            .exhaustMerge
            .filter{it, m -> ['Animal'].contains(it['@class'])}
            .as('Animal__in_Entity_Related___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal__in_Entity_Related___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_recurse_with_immediate_type_coercion_and_filter(self) -> None:
        test_data = test_input_data.recurse_with_immediate_type_coercion_and_filter()

        expected_match = """
            SELECT
                Animal__in_Entity_Related___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Entity_Related') {{
                    while: ($depth < 4),
                    where: (((@this INSTANCEOF 'Animal') AND (color = {color}))),
                    as: Animal__in_Entity_Related___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .copySplit(
                _(),
                _().in('Entity_Related'),
                _().in('Entity_Related').in('Entity_Related'),
                _().in('Entity_Related').in('Entity_Related').in('Entity_Related'),
                _().in('Entity_Related').in('Entity_Related')
                   .in('Entity_Related').in('Entity_Related')
            )
            .exhaustMerge
            .filter{it, m -> (['Animal'].contains(it['@class']) && (it.color == $color))}
            .as('Animal__in_Entity_Related___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal__in_Entity_Related___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_in_collection_op_filter_with_variable(self) -> None:
        test_data = test_input_data.in_collection_op_filter_with_variable()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: (({wanted} CONTAINS name)),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> $wanted.contains(it.name)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                [Animal_1].name IN :wanted
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE (Animal___1.name IN $wanted)
            RETURN
                Animal___1.name AS `animal_name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                "Animal_1".name IN :wanted
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_in_collection_op_filter_with_tag(self) -> None:
        test_data = test_input_data.in_collection_op_filter_with_tag()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    where: (($matched.Animal___1.alias CONTAINS name)),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_ParentOf')
            .filter{it, m -> m.Animal___1.alias.contains(it.name)}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
                WHERE (Animal__out_Animal_ParentOf___1.name IN Animal___1.alias)
            RETURN
                Animal___1.name AS `animal_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_in_collection_op_filter_with_optional_tag(self) -> None:
        test_data = test_input_data.in_collection_op_filter_with_optional_tag()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    optional: true,
                    as: Animal__in_Animal_ParentOf___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    where: ((
                         ($matched.Animal__in_Animal_ParentOf___1 IS null)
                         OR
                         ($matched.Animal__in_Animal_ParentOf___1.alias CONTAINS name)
                    )),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (Animal___1.in_Animal_ParentOf IS null)
                    OR
                    (Animal___1.in_Animal_ParentOf.size() = 0)
                )
                OR
                (Animal__in_Animal_ParentOf___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
            .as('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .out('Animal_ParentOf')
            .filter{it, m -> (
                (m.Animal__in_Animal_ParentOf___1 == null) ||
                m.Animal__in_Animal_ParentOf___1.alias.contains(it.name)
            )}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
                WHERE ((Animal__in_Animal_ParentOf___1 IS null) OR
                    (Animal__out_Animal_ParentOf___1.name IN Animal__in_Animal_ParentOf___1.alias))
            RETURN
                Animal___1.name AS `animal_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_not_in_collection_op_filter_with_variable(self) -> None:
        test_data = test_input_data.not_in_collection_op_filter_with_variable()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((NOT ({wanted} CONTAINS name))),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> !$wanted.contains(it.name)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                [Animal_1].name NOT IN :wanted
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE (NOT(Animal___1.name IN $wanted))
            RETURN
                Animal___1.name AS `animal_name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                "Animal_1".name NOT IN :wanted
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_not_in_collection_op_filter_with_tag(self) -> None:
        test_data = test_input_data.not_in_collection_op_filter_with_tag()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    where: ((NOT ($matched.Animal___1.alias CONTAINS name))),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_ParentOf')
            .filter{it, m -> !m.Animal___1.alias.contains(it.name)}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
                WHERE (NOT(Animal__out_Animal_ParentOf___1.name IN Animal___1.alias))
            RETURN
                Animal___1.name AS `animal_name`
        """
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_not_in_collection_op_filter_with_optional_tag(self) -> None:
        test_data = test_input_data.not_in_collection_op_filter_with_optional_tag()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    optional: true,
                    as: Animal__in_Animal_ParentOf___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    where: ((
                         ($matched.Animal__in_Animal_ParentOf___1 IS null)
                         OR
                         (NOT ($matched.Animal__in_Animal_ParentOf___1.alias CONTAINS name))
                    )),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (Animal___1.in_Animal_ParentOf IS null)
                    OR
                    (Animal___1.in_Animal_ParentOf.size() = 0)
                )
                OR
                (Animal__in_Animal_ParentOf___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
            .as('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .out('Animal_ParentOf')
            .filter{it, m -> (
                (m.Animal__in_Animal_ParentOf___1 == null) ||
                !m.Animal__in_Animal_ParentOf___1.alias.contains(it.name)
            )}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
                WHERE ((Animal__in_Animal_ParentOf___1 IS null) OR
                    (NOT(Animal__out_Animal_ParentOf___1.name IN
                        Animal__in_Animal_ParentOf___1.alias)))
            RETURN
                Animal___1.name AS `animal_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_intersects_op_filter_with_variable(self) -> None:
        test_data = test_input_data.intersects_op_filter_with_variable()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((intersect(alias, {wanted}).asList().size() > 0)),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (!it.alias.intersect($wanted).empty)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_intersects_op_filter_with_tag(self) -> None:
        test_data = test_input_data.intersects_op_filter_with_tag()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    where: ((intersect(alias, $matched.Animal___1.alias).asList().size() > 0)),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_ParentOf')
            .filter{it, m -> (!it.alias.intersect(m.Animal___1.alias).empty)}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_intersects_op_filter_with_optional_tag(self) -> None:
        test_data = test_input_data.intersects_op_filter_with_optional_tag()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    optional: true,
                    as: Animal__in_Animal_ParentOf___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    where: ((
                         ($matched.Animal__in_Animal_ParentOf___1 IS null)
                         OR
                         (intersect(alias, $matched.Animal__in_Animal_ParentOf___1.alias)
                         .asList().size() > 0))
                    ),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (Animal___1.in_Animal_ParentOf IS null)
                    OR
                    (Animal___1.in_Animal_ParentOf.size() = 0)
                )
                OR
                (Animal__in_Animal_ParentOf___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
            .as('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .out('Animal_ParentOf')
            .filter{it, m -> (
                (m.Animal__in_Animal_ParentOf___1 == null) ||
                (!it.alias.intersect(m.Animal__in_Animal_ParentOf___1.alias).empty)
            )}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_contains_op_filter_with_variable(self) -> None:
        test_data = test_input_data.contains_op_filter_with_variable()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((alias CONTAINS {wanted})),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> it.alias.contains($wanted)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        # the alias list valued column is not yet supported by the SQL backend
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE ($wanted IN Animal___1.alias)
            RETURN
                Animal___1.name AS `animal_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_contains_op_filter_with_tag(self) -> None:
        test_data = test_input_data.contains_op_filter_with_tag()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    where: ((alias CONTAINS $matched.Animal___1.name)),
                    as: Animal__in_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .in('Animal_ParentOf')
                .filter{it, m -> it.alias.contains(m.Animal___1.name)}
                .as('Animal__in_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
                WHERE (Animal___1.name IN Animal__in_Animal_ParentOf___1.alias)
            RETURN
                Animal___1.name AS `animal_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_contains_op_filter_with_optional_tag(self) -> None:
        test_data = test_input_data.contains_op_filter_with_optional_tag()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    optional: true,
                    as: Animal__in_Animal_ParentOf___1
                }} ,
                {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    where: ((
                        ($matched.Animal__in_Animal_ParentOf___1 IS null)
                        OR
                        (alias CONTAINS $matched.Animal__in_Animal_ParentOf___1.name))),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (Animal___1.in_Animal_ParentOf IS null)
                    OR
                    (Animal___1.in_Animal_ParentOf.size() = 0)
                )
                OR
                (Animal__in_Animal_ParentOf___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
                .out('Animal_ParentOf')
                .filter{it, m -> (
                        (m.Animal__in_Animal_ParentOf___1 == null)
                        ||
                        it.alias.contains(m.Animal__in_Animal_ParentOf___1.name)
                    )
                }
                .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
                WHERE ((Animal__in_Animal_ParentOf___1 IS null) OR
                    (Animal__in_Animal_ParentOf___1.name IN Animal__out_Animal_ParentOf___1.alias))
            RETURN
                Animal___1.name AS `animal_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_not_contains_op_filter_with_variable(self) -> None:
        test_data = test_input_data.not_contains_op_filter_with_variable()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((NOT (alias CONTAINS {wanted}))),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> !it.alias.contains($wanted)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        # the alias list valued column is not yet supported by the SQL backend
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE (NOT($wanted IN Animal___1.alias))
            RETURN
                Animal___1.name AS `animal_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_not_contains_op_filter_with_tag(self) -> None:
        test_data = test_input_data.not_contains_op_filter_with_tag()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    where: ((NOT (alias CONTAINS $matched.Animal___1.name))),
                    as: Animal__in_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .in('Animal_ParentOf')
                .filter{it, m -> !it.alias.contains(m.Animal___1.name)}
                .as('Animal__in_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
                WHERE (NOT(Animal___1.name IN Animal__in_Animal_ParentOf___1.alias))
            RETURN
                Animal___1.name AS `animal_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_not_contains_op_filter_with_optional_tag(self) -> None:
        test_data = test_input_data.not_contains_op_filter_with_optional_tag()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    optional: true,
                    as: Animal__in_Animal_ParentOf___1
                }} ,
                {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    where: ((
                        ($matched.Animal__in_Animal_ParentOf___1 IS null)
                        OR
                        (NOT (alias CONTAINS $matched.Animal__in_Animal_ParentOf___1.name)))),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (Animal___1.in_Animal_ParentOf IS null)
                    OR
                    (Animal___1.in_Animal_ParentOf.size() = 0)
                )
                OR
                (Animal__in_Animal_ParentOf___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
                .out('Animal_ParentOf')
                .filter{it, m -> (
                        (m.Animal__in_Animal_ParentOf___1 == null)
                        ||
                        !it.alias.contains(m.Animal__in_Animal_ParentOf___1.name)
                    )
                }
                .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
                WHERE ((Animal__in_Animal_ParentOf___1 IS null) OR
                    (NOT(Animal__in_Animal_ParentOf___1.name IN
                        Animal__out_Animal_ParentOf___1.alias)))
            RETURN
                Animal___1.name AS `animal_name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_starts_with_op_filter(self) -> None:
        test_data = test_input_data.starts_with_op_filter()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((name LIKE ({wanted} + '%'))),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> it.name.startsWith($wanted)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                ([Animal_1].name LIKE :wanted + '%')
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE (Animal___1.name STARTS WITH $wanted)
            RETURN
                Animal___1.name AS `animal_name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                ("Animal_1".name LIKE :wanted || '%%')
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_ends_with_op_filter(self) -> None:
        test_data = test_input_data.ends_with_op_filter()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((name LIKE ('%' + {wanted}))),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> it.name.endsWith($wanted)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                ([Animal_1].name LIKE '%' + :wanted)
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE (Animal___1.name ENDS WITH $wanted)
            RETURN
                Animal___1.name AS `animal_name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                ("Animal_1".name LIKE '%%' || :wanted)
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_has_substring_op_filter(self) -> None:
        test_data = test_input_data.has_substring_op_filter()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((name LIKE ('%' + ({wanted} + '%')))),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> it.name.contains($wanted)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                ([Animal_1].name LIKE '%' + :wanted + '%')
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE (Animal___1.name CONTAINS $wanted)
            RETURN
                Animal___1.name AS `animal_name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                ("Animal_1".name LIKE '%%' || :wanted || '%%')
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_has_substring_op_filter_with_variable(self) -> None:
        graphql_input = """{
            Animal {
                name @filter(op_name: "has_substring", value: ["$wanted"])
                     @output(out_name: "animal_name")
            }
        }"""

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((name LIKE ('%' + ({wanted} + '%')))),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> it.name.contains($wanted)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                ([Animal_1].name LIKE '%' + :wanted + '%')
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                ("Animal_1".name LIKE '%%' || :wanted || '%%')
        """

        expected_output_metadata = {
            "animal_name": OutputMetadata(type=GraphQLString, optional=False, folded=False),
        }
        expected_input_metadata = {
            "wanted": GraphQLString,
        }

        test_data = test_input_data.CommonTestData(
            graphql_input=graphql_input,
            expected_output_metadata=expected_output_metadata,
            expected_input_metadata=expected_input_metadata,
            type_equivalence_hints=None,
        )

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_has_substring_op_filter_with_tag(self) -> None:
        graphql_input = """{
            Animal {
                name @output(out_name: "animal_name") @tag(tag_name: "root_name")
                out_Animal_ParentOf {
                    name @filter(op_name: "has_substring", value: ["%root_name"])
                }
            }
        }"""

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    where: ((name LIKE ('%' + ($matched.Animal___1.name + '%')))),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_ParentOf')
            .filter{it, m -> it.name.contains(m.Animal___1.name)}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_output_metadata = {
            "animal_name": OutputMetadata(type=GraphQLString, optional=False, folded=False),
        }
        expected_input_metadata: Dict[str, GraphQLScalarType] = {}

        test_data = test_input_data.CommonTestData(
            graphql_input=graphql_input,
            expected_output_metadata=expected_output_metadata,
            expected_input_metadata=expected_input_metadata,
            type_equivalence_hints=None,
        )

        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].uuid = [Animal_2].parent
            WHERE
                ([Animal_2].name LIKE '%' + [Animal_1].name + '%')
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name
            FROM
                schema_1."Animal" AS "Animal_1"
                JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".uuid = "Animal_2".parent
            WHERE
                ("Animal_2".name LIKE '%%' || "Animal_1".name || '%%')
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_has_substring_op_filter_with_optional_tag(self) -> None:
        graphql_input = """{
            Animal {
                name @output(out_name: "animal_name")
                in_Animal_ParentOf @optional {
                    name @tag(tag_name: "parent_name")
                }
                out_Animal_ParentOf {
                    name @filter(op_name: "has_substring", value: ["%parent_name"])
                }
            }
        }"""

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    optional: true,
                    as: Animal__in_Animal_ParentOf___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    where: ((
                        ($matched.Animal__in_Animal_ParentOf___1 IS null) OR
                        (name LIKE ('%' + ($matched.Animal__in_Animal_ParentOf___1.name + '%')))
                    )),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (Animal___1.in_Animal_ParentOf IS null)
                    OR
                    (Animal___1.in_Animal_ParentOf.size() = 0)
                )
                OR
                (Animal__in_Animal_ParentOf___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
            .as('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .out('Animal_ParentOf')
            .filter{it, m -> (
                (m.Animal__in_Animal_ParentOf___1 == null) ||
                it.name.contains(m.Animal__in_Animal_ParentOf___1.name)
            )}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_output_metadata = {
            "animal_name": OutputMetadata(type=GraphQLString, optional=False, folded=False),
        }
        expected_input_metadata: Dict[str, GraphQLScalarType] = {}

        test_data = test_input_data.CommonTestData(
            graphql_input=graphql_input,
            expected_output_metadata=expected_output_metadata,
            expected_input_metadata=expected_input_metadata,
            type_equivalence_hints=None,
        )

        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].parent = [Animal_2].uuid
                JOIN db_1.schema_1.[Animal] AS [Animal_3]
                    ON [Animal_1].uuid = [Animal_3].parent
            WHERE
                [Animal_2].uuid IS NULL OR
                ([Animal_3].name LIKE '%' + [Animal_2].name + '%')
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name
            FROM
                schema_1."Animal" AS "Animal_1"
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".parent = "Animal_2".uuid
                JOIN schema_1."Animal" AS "Animal_3"
                    ON "Animal_1".uuid = "Animal_3".parent
            WHERE
                "Animal_2".uuid IS NULL OR
                ("Animal_3".name LIKE '%%' || "Animal_2".name || '%%')
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_has_edge_degree_op_filter(self) -> None:
        test_data = test_input_data.has_edge_degree_op_filter()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                Animal__in_Animal_ParentOf___1.name AS `child_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((
                        (({child_count} = 0) AND (in_Animal_ParentOf IS null)) OR
                        ((in_Animal_ParentOf IS NOT null) AND
                            (in_Animal_ParentOf.size() = {child_count}))
                    )),
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    as: Animal__in_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (
                (($child_count == 0) && (it.in_Animal_ParentOf == null)) ||
                ((it.in_Animal_ParentOf != null) &&
                    (it.in_Animal_ParentOf.count() == $child_count))
            )}
            .as('Animal___1')
            .in('Animal_ParentOf')
            .as('Animal__in_Animal_ParentOf___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_name: m.Animal__in_Animal_ParentOf___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_has_edge_degree_op_filter_with_optional(self) -> None:
        test_data = test_input_data.has_edge_degree_op_filter_with_optional()

        expected_match = """
            SELECT
                if(eval("(Species__in_Animal_OfSpecies__in_Animal_ParentOf___1 IS NOT null)"),
                   Species__in_Animal_OfSpecies__in_Animal_ParentOf___1.name,
                   null
                ) AS `child_name`,
                Species__in_Animal_OfSpecies___1.name AS `parent_name`,
                Species___1.name AS `species_name`
            FROM (
                MATCH {{
                    where: ((@this INSTANCEOF 'Species')),
                    as: Species___1
                }}.in('Animal_OfSpecies') {{
                    class: Animal,
                    where: ((
                        (({child_count} = 0) AND (in_Animal_ParentOf IS null)) OR
                        ((in_Animal_ParentOf IS NOT null) AND
                            (in_Animal_ParentOf.size() = {child_count}))
                    )),
                    as: Species__in_Animal_OfSpecies___1
                }}.in('Animal_ParentOf') {{
                    optional: true,
                    as: Species__in_Animal_OfSpecies__in_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (Species__in_Animal_OfSpecies___1.in_Animal_ParentOf IS null)
                    OR
                    (Species__in_Animal_OfSpecies___1.in_Animal_ParentOf.size() = 0)
                )
                OR
                (Species__in_Animal_OfSpecies__in_Animal_ParentOf___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Species')
            .as('Species___1')
            .in('Animal_OfSpecies')
            .filter{it, m -> (
                (($child_count == 0) && (it.in_Animal_ParentOf == null)) ||
                ((it.in_Animal_ParentOf != null) &&
                    (it.in_Animal_ParentOf.count() == $child_count))
            )}
            .as('Species__in_Animal_OfSpecies___1')
            .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
            .as('Species__in_Animal_OfSpecies__in_Animal_ParentOf___1')
            .optional('Species__in_Animal_OfSpecies___1')
            .as('Species__in_Animal_OfSpecies___2')
            .back('Species___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_name: (
                    (m.Species__in_Animal_OfSpecies__in_Animal_ParentOf___1 != null) ?
                    m.Species__in_Animal_OfSpecies__in_Animal_ParentOf___1.name : null),
                parent_name: m.Species__in_Animal_OfSpecies___1.name,
                species_name: m.Species___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_has_edge_degree_op_filter_with_optional_and_between(self) -> None:
        test_data = test_input_data.has_edge_degree_op_filter_with_optional_and_between()

        expected_match = """
            SELECT EXPAND($result)
            LET
                $optional__0 = (
                    SELECT
                        Animal___1.name AS `animal_name`
                    FROM (
                        MATCH {{
                            class: Animal,
                            where: ((
                                (
                                    (uuid BETWEEN {uuid_lower_bound} AND {uuid_upper_bound}) AND
                                    (
                                        (
                                            ({number_of_edges} = 0) AND
                                            (in_Animal_ParentOf IS null)
                                        ) OR (
                                            (in_Animal_ParentOf IS NOT null) AND
                                            (in_Animal_ParentOf.size() = {number_of_edges})
                                        )
                                    )
                                ) AND (
                                    (in_Animal_ParentOf IS null) OR
                                    (in_Animal_ParentOf.size() = 0)
                                )
                            )),
                            as: Animal___1
                        }}
                        RETURN $matches
                    )
                ),
                $optional__1 = (
                    SELECT
                        Animal___1.name AS `animal_name`,
                        Animal__in_Animal_ParentOf__out_Entity_Related___1.name AS `related_event`
                    FROM (
                        MATCH {{
                            class: Animal,
                            where: ((
                                (uuid BETWEEN {uuid_lower_bound} AND {uuid_upper_bound}) AND
                                (
                                    (
                                        ({number_of_edges} = 0) AND
                                        (in_Animal_ParentOf IS null)
                                    ) OR (
                                        (in_Animal_ParentOf IS NOT null) AND
                                        (in_Animal_ParentOf.size() = {number_of_edges})
                                    )
                                )
                            )),
                            as: Animal___1
                        }}.in('Animal_ParentOf') {{
                            as: Animal__in_Animal_ParentOf___1
                        }}.out('Entity_Related') {{
                            where: ((@this INSTANCEOF 'Event')),
                            as: Animal__in_Animal_ParentOf__out_Entity_Related___1
                        }} RETURN $matches
                    )
                ),
                $result = UNIONALL($optional__0, $optional__1)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (
                (
                    (
                        ($number_of_edges == 0) &&
                        (it.in_Animal_ParentOf == null)
                    ) || (
                        (it.in_Animal_ParentOf != null) &&
                        (it.in_Animal_ParentOf.count() == $number_of_edges)
                    )
                ) && (
                    (it.uuid >= $uuid_lower_bound) && (it.uuid <= $uuid_upper_bound)
                )
            )}
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{it.out('Entity_Related')}
                    .filter{it, m -> ((it == null) || ['Event'].contains(it['@class']))}
                    .as('Animal__in_Animal_ParentOf__out_Entity_Related___1')
                .back('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                related_event: (
                    (m.Animal__in_Animal_ParentOf__out_Entity_Related___1 != null) ?
                    m.Animal__in_Animal_ParentOf__out_Entity_Related___1.name :
                    null
                )
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_has_edge_degree_op_filter_with_fold(self) -> None:
        test_data = test_input_data.has_edge_degree_op_filter_with_fold()

        expected_match = """
            SELECT
                $Species__in_Animal_OfSpecies___1___in_Animal_ParentOf.name AS `child_names`,
                Species__in_Animal_OfSpecies___1.name AS `parent_name`,
                Species___1.name AS `species_name`
            FROM (
                MATCH {{
                    where: ((@this INSTANCEOF 'Species')),
                    as: Species___1
                }}.in('Animal_OfSpecies') {{
                    class: Animal,
                    where: ((
                        (({child_count} = 0) AND (in_Animal_ParentOf IS null)) OR
                        ((in_Animal_ParentOf IS NOT null) AND
                            (in_Animal_ParentOf.size() = {child_count}))
                    )),
                    as: Species__in_Animal_OfSpecies___1
                }}
                RETURN $matches
            ) LET
                $Species__in_Animal_OfSpecies___1___in_Animal_ParentOf =
                    Species__in_Animal_OfSpecies___1.in("Animal_ParentOf").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Species')
            .as('Species___1')
            .in('Animal_OfSpecies')
            .filter{it, m -> (
                (($child_count == 0) && (it.in_Animal_ParentOf == null)) ||
                ((it.in_Animal_ParentOf != null) &&
                    (it.in_Animal_ParentOf.count() == $child_count))
            )}
            .as('Species__in_Animal_OfSpecies___1')
            .back('Species___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_names: (
                    (m.Species__in_Animal_OfSpecies___1.in_Animal_ParentOf == null) ?
                    [] :
                    (m.Species__in_Animal_OfSpecies___1.in_Animal_ParentOf
                        .collect{entry -> entry.outV.next().name})
                ),
                parent_name: m.Species__in_Animal_OfSpecies___1.name,
                species_name: m.Species___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST  # has_edge_degree not implemented for Cypher yet.

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_is_null_op_filter(self) -> None:
        test_data = test_input_data.is_null_op_filter()

        expected_match = """
            SELECT
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((net_worth IS null)),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (it.net_worth == null)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT [Animal_1].name AS name
            FROM db_1.schema_1.[Animal] AS [Animal_1]
            WHERE [Animal_1].net_worth IS NULL
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            WHERE (Animal___1.net_worth IS null)
            RETURN Animal___1.name AS `name`
        """
        expected_postgresql = """
            SELECT "Animal_1".name AS name
            FROM schema_1."Animal" AS "Animal_1"
            WHERE "Animal_1".net_worth IS NULL
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_is_not_null_op_filter(self) -> None:
        test_data = test_input_data.is_not_null_op_filter()

        expected_match = """
            SELECT
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((net_worth IS NOT null)),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (it.net_worth != null)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT [Animal_1].name AS name
            FROM db_1.schema_1.[Animal] AS [Animal_1]
            WHERE [Animal_1].net_worth IS NOT NULL
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            WHERE (Animal___1.net_worth IS NOT null)
            RETURN Animal___1.name AS `name`
        """
        expected_postgresql = """
            SELECT "Animal_1".name AS name
            FROM schema_1."Animal" AS "Animal_1"
            WHERE "Animal_1".net_worth IS NOT NULL
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_is_not_null_op_filter_missing_value_argument(self) -> None:
        test_data = test_input_data.is_not_null_op_filter_missing_value_argument()

        expected_match = """
            SELECT
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((net_worth IS NOT null)),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (it.net_worth != null)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT [Animal_1].name AS name
            FROM db_1.schema_1.[Animal] AS [Animal_1]
            WHERE [Animal_1].net_worth IS NOT NULL
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            WHERE (Animal___1.net_worth IS NOT null)
            RETURN Animal___1.name AS `name`
        """
        expected_postgresql = """
            SELECT "Animal_1".name AS name
            FROM schema_1."Animal" AS "Animal_1"
            WHERE "Animal_1".net_worth IS NOT NULL
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_is_null_op_filter_missing_value_argument(self) -> None:
        test_data = test_input_data.is_null_op_filter_missing_value_argument()

        expected_match = """
            SELECT
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((net_worth IS null)),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (it.net_worth == null)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT [Animal_1].name AS name
            FROM db_1.schema_1.[Animal] AS [Animal_1]
            WHERE [Animal_1].net_worth IS NULL
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            WHERE (Animal___1.net_worth IS null)
            RETURN Animal___1.name AS `name`
        """
        expected_postgresql = """
            SELECT "Animal_1".name AS name
            FROM schema_1."Animal" AS "Animal_1"
            WHERE "Animal_1".net_worth IS NULL
        """
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_simple_union(self) -> None:
        test_data = test_input_data.simple_union()

        expected_match = """
            SELECT
                Species__out_Species_Eats___1.name AS `food_name`,
                Species___1.name AS `species_name`
            FROM (
                MATCH {{
                    class: Species,
                    as: Species___1
                }}.out('Species_Eats') {{
                    class: Food,
                    as: Species__out_Species_Eats___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Species')
            .as('Species___1')
            .out('Species_Eats')
            .filter{it, m -> ['Food'].contains(it['@class'])}
            .as('Species__out_Species_Eats___1')
            .back('Species___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                food_name: m.Species__out_Species_Eats___1.name,
                species_name: m.Species___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_filter_then_apply_fragment(self) -> None:
        test_data = test_input_data.filter_then_apply_fragment()

        expected_match = """
            SELECT
                Species__out_Species_Eats___1.name AS `food_name`,
                Species___1.name AS `species_name`
            FROM (
                MATCH {{
                    class: Species,
                    where: (({species} CONTAINS name)),
                    as: Species___1
                }}.out('Species_Eats') {{
                    where: ((@this INSTANCEOF 'Food')),
                    as: Species__out_Species_Eats___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Species')
            .filter{it, m -> $species.contains(it.name)}
            .as('Species___1')
            .out('Species_Eats')
            .filter{it, m -> ['Food'].contains(it['@class'])}
            .as('Species__out_Species_Eats___1')
            .back('Species___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                food_name: m.Species__out_Species_Eats___1.name,
                species_name: m.Species___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_filter_then_apply_fragment_with_multiple_traverses(self) -> None:
        test_data = test_input_data.filter_then_apply_fragment_with_multiple_traverses()

        expected_match = """
            SELECT
                Species__out_Species_Eats__out_Entity_Related___1.name AS `entity_related_to_food`,
                Species__out_Species_Eats___1.name AS `food_name`,
                Species__out_Species_Eats__in_Entity_Related___1.name AS `food_related_to_entity`,
                Species___1.name AS `species_name`
            FROM (
                MATCH {{
                    class: Species,
                    where: (({species} CONTAINS name)),
                    as: Species___1
                }}.out('Species_Eats') {{
                    where: ((@this INSTANCEOF 'Food')),
                    as: Species__out_Species_Eats___1
                }}.out('Entity_Related') {{
                    as: Species__out_Species_Eats__out_Entity_Related___1
                }}, {{
                    as: Species__out_Species_Eats___1
                }}.in('Entity_Related') {{
                    as: Species__out_Species_Eats__in_Entity_Related___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Species')
            .filter{it, m -> $species.contains(it.name)}
            .as('Species___1')
            .out('Species_Eats')
            .filter{it, m -> ['Food'].contains(it['@class'])}
            .as('Species__out_Species_Eats___1')
            .out('Entity_Related')
            .as('Species__out_Species_Eats__out_Entity_Related___1')
            .back('Species__out_Species_Eats___1')
            .in('Entity_Related')
            .as('Species__out_Species_Eats__in_Entity_Related___1')
            .back('Species__out_Species_Eats___1')
            .back('Species___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                entity_related_to_food: m.Species__out_Species_Eats__out_Entity_Related___1.name,
                food_name: m.Species__out_Species_Eats___1.name,
                food_related_to_entity: m.Species__out_Species_Eats__in_Entity_Related___1.name,
                species_name: m.Species___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_filter_on_fragment_in_union(self) -> None:
        test_data = test_input_data.filter_on_fragment_in_union()

        expected_match = """
            SELECT
                Species__out_Species_Eats___1.name AS `food_name`,
                Species___1.name AS `species_name`
            FROM (
                MATCH {{
                    where: ((@this INSTANCEOF 'Species')),
                    as: Species___1
                }}.out('Species_Eats') {{
                    class: Food,
                    where: (((name = {wanted}) OR (alias CONTAINS {wanted}))),
                    as: Species__out_Species_Eats___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Species')
            .as('Species___1')
            .out('Species_Eats')
            .filter{it, m -> (['Food'].contains(it['@class']) &&
                             ((it.name == $wanted) || it.alias.contains($wanted)))}
            .as('Species__out_Species_Eats___1')
            .back('Species___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                food_name: m.Species__out_Species_Eats___1.name,
                species_name: m.Species___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_optional_on_union(self) -> None:
        test_data = test_input_data.optional_on_union()

        expected_match = """
            SELECT
                if(eval("(Species__out_Species_Eats___1 IS NOT null)"),
                    Species__out_Species_Eats___1.name,
                    null
                ) AS `food_name`,
                Species___1.name AS `species_name`
            FROM (
                MATCH {{
                    class: Species,
                    as: Species___1
                }}.out('Species_Eats') {{
                    class: Food,
                    optional: true,
                    as: Species__out_Species_Eats___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (Species___1.out_Species_Eats IS null)
                    OR
                    (Species___1.out_Species_Eats.size() = 0)
                )
                OR
                (Species__out_Species_Eats___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Species')
            .as('Species___1')
            .ifThenElse{it.out_Species_Eats == null}{null}{it.out('Species_Eats')}
            .filter{it, m -> ((it == null) || ['Food'].contains(it['@class']))}
            .as('Species__out_Species_Eats___1')
            .optional('Species___1')
            .as('Species___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                food_name: ((m.Species__out_Species_Eats___1 != null) ?
                            m.Species__out_Species_Eats___1.name : null),
                species_name: m.Species___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_gremlin_type_hints(self) -> None:
        graphql_input = """{
            Animal {
                out_Entity_Related {
                    ... on Event {
                        name @output(out_name: "related_event")
                    }
                }
            }
        }"""
        type_equivalence_hints = {"Event": "Union__BirthEvent__Event__FeedingEvent"}

        expected_match = """
            SELECT
                Animal__out_Entity_Related___1.name AS `related_event`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Entity_Related') {{
                    class: Event,
                    as: Animal__out_Entity_Related___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Entity_Related')
            .filter{it, m -> ['BirthEvent', 'Event', 'FeedingEvent'].contains(it['@class'])}
            .as('Animal__out_Entity_Related___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                related_event: m.Animal__out_Entity_Related___1.name
            ])}
        """
        expected_output_metadata = {
            "related_event": OutputMetadata(type=GraphQLString, optional=False, folded=False),
        }
        expected_input_metadata: Dict[str, GraphQLScalarType] = {}

        test_data = test_input_data.CommonTestData(
            graphql_input=graphql_input,
            expected_output_metadata=expected_output_metadata,
            expected_input_metadata=expected_input_metadata,
            type_equivalence_hints=type_equivalence_hints,
        )

        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_unnecessary_traversal_elimination(self) -> None:
        # This test case caught a bug in the optimization pass that eliminates unnecessary
        # traversals, where it would fail to remove part of the dead code
        # if there were more than two @optional traversals from the same location.
        #
        # The problem in the optimization pass was the following:
        # - N @optional traversals from a given location X, would generate N QueryRoot
        #   blocks at that location N;
        # - exactly 2 of those QueryRoots would be eliminated away, leaving (N - 2) behind
        # - each such QueryRoot would multiplicatively increase the complexity of the query
        #   by a linear term -- the number of entries at that QueryRoot.
        #
        # This test ensures that all N=3 of the QueryRoots are eliminated away, rather than just 2.
        # See the complementary optimization-pass-only version of the test
        # in test_ir_lowering.py for more details.
        graphql_input = """{
            Animal {
                uuid @filter(op_name: "=", value: ["$uuid"])
                out_Animal_ParentOf @optional {
                    uuid @output(out_name: "child_uuid")
                }
                out_Animal_OfSpecies @optional {
                    uuid @output(out_name: "species_uuid")
                }
                out_Animal_FedAt @optional {
                    uuid @output(out_name: "event_uuid")
                }
            }
        }"""

        expected_match = """
            SELECT
                if(eval("(Animal__out_Animal_ParentOf___1 IS NOT null)"),
                   Animal__out_Animal_ParentOf___1.uuid, null) AS `child_uuid`,
                if(eval("(Animal__out_Animal_FedAt___1 IS NOT null)"),
                   Animal__out_Animal_FedAt___1.uuid, null) AS `event_uuid`,
                if(eval("(Animal__out_Animal_OfSpecies___1 IS NOT null)"),
                   Animal__out_Animal_OfSpecies___1.uuid, null) AS `species_uuid`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((uuid = {uuid})),
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    optional: true,
                    as: Animal__out_Animal_ParentOf___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_OfSpecies') {{
                    optional: true,
                    as: Animal__out_Animal_OfSpecies___1
                }} , {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_FedAt') {{
                    optional: true,
                    as: Animal__out_Animal_FedAt___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (
                        (Animal___1.out_Animal_FedAt IS null)
                        OR
                        (Animal___1.out_Animal_FedAt.size() = 0)
                    )
                    OR
                    (Animal__out_Animal_FedAt___1 IS NOT null)
                )
                AND
                (
                    (
                        (
                            (Animal___1.out_Animal_OfSpecies IS null)
                            OR
                            (Animal___1.out_Animal_OfSpecies.size() = 0)
                        )
                        OR
                        (Animal__out_Animal_OfSpecies___1 IS NOT null)
                    )
                    AND
                    (
                        (
                            (Animal___1.out_Animal_ParentOf IS null)
                            OR
                            (Animal___1.out_Animal_ParentOf.size() = 0)
                        )
                        OR
                        (Animal__out_Animal_ParentOf___1 IS NOT null)
                    )
                )
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> (it.uuid == $uuid)}
            .as('Animal___1')
            .ifThenElse{it.out_Animal_ParentOf == null}{null}{it.out('Animal_ParentOf')}
            .as('Animal__out_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .ifThenElse{it.out_Animal_OfSpecies == null}{null}{it.out('Animal_OfSpecies')}
            .as('Animal__out_Animal_OfSpecies___1')
            .optional('Animal___2')
            .as('Animal___3')
            .ifThenElse{it.out_Animal_FedAt == null}{null}{it.out('Animal_FedAt')}
            .as('Animal__out_Animal_FedAt___1')
            .optional('Animal___3')
            .as('Animal___4')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_uuid: ((m.Animal__out_Animal_ParentOf___1 != null) ?
                               m.Animal__out_Animal_ParentOf___1.uuid : null),
                event_uuid: ((m.Animal__out_Animal_FedAt___1 != null) ?
                              m.Animal__out_Animal_FedAt___1.uuid : null),
                species_uuid: ((m.Animal__out_Animal_OfSpecies___1 != null) ?
                                m.Animal__out_Animal_OfSpecies___1.uuid : null)
            ])}
        """
        expected_output_metadata = {
            "child_uuid": OutputMetadata(type=GraphQLID, optional=True, folded=False),
            "event_uuid": OutputMetadata(type=GraphQLID, optional=True, folded=False),
            "species_uuid": OutputMetadata(type=GraphQLID, optional=True, folded=False),
        }
        expected_input_metadata = {
            "uuid": GraphQLID,
        }

        test_data = test_input_data.CommonTestData(
            graphql_input=graphql_input,
            expected_output_metadata=expected_output_metadata,
            expected_input_metadata=expected_input_metadata,
            type_equivalence_hints=None,
        )

        expected_mssql = """
            SELECT
                [Animal_1].uuid AS child_uuid,
                [FeedingEvent_1].uuid AS event_uuid,
                [Species_1].uuid AS species_uuid
            FROM
                db_1.schema_1.[Animal] AS [Animal_2]
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_1]
                    ON [Animal_2].uuid = [Animal_1].parent
                LEFT OUTER JOIN db_1.schema_1.[Species] AS [Species_1]
                    ON [Animal_2].species = [Species_1].uuid
                LEFT OUTER JOIN db_2.schema_1.[FeedingEvent] AS [FeedingEvent_1]
                    ON [Animal_2].fed_at = [FeedingEvent_1].uuid
            WHERE
                [Animal_2].uuid = :uuid
        """
        expected_cypher = SKIP_TEST

        expected_postgresql = """
        SELECT
            "Animal_1".uuid AS child_uuid,
            "FeedingEvent_1".uuid AS event_uuid,
            "Species_1".uuid AS species_uuid
        FROM
            schema_1."Animal" AS "Animal_2"
            LEFT OUTER JOIN schema_1."Animal" AS "Animal_1"
                ON "Animal_2".uuid = "Animal_1".parent
            LEFT OUTER JOIN schema_1."Species" AS "Species_1"
                ON "Animal_2".species = "Species_1".uuid
            LEFT OUTER JOIN schema_1."FeedingEvent" AS "FeedingEvent_1"
            ON "Animal_2".fed_at = "FeedingEvent_1".uuid
        WHERE
            "Animal_2".uuid = :uuid
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_on_output_variable(self) -> None:
        test_data = test_input_data.fold_on_output_variable()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___out_Animal_ParentOf.name AS `child_names_list`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___out_Animal_ParentOf =
                    Animal___1.out("Animal_ParentOf").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_names_list: (
                    (m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.out_Animal_ParentOf.collect{entry -> entry.inV.next().name}
                    )
                )
            ])}
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[]) AS child_names_list
            FROM
                schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3" ON "Animal_2".uuid = "Animal_3".parent
                GROUP BY
                    "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              collect(Animal__out_Animal_ParentOf___1) AS collected_Animal__out_Animal_ParentOf___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN collected_Animal__out_Animal_ParentOf___1 | x.name] AS `child_names_list`
        """
        expected_mssql = """
            SELECT
              [Animal_1].name AS animal_name,
              folded_subquery_1.fold_output_name AS child_names_list
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            JOIN (
                SELECT
                    [Animal_2].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Animal_3].name, '^', '^e'),
                                    '~',
                                    '^n'),
                                '|',
                                '^d'),
                            '~')
                        FROM
                            db_1.schema_1.[Animal] AS [Animal_3]
                        WHERE
                            [Animal_2].uuid = [Animal_3].parent FOR XML PATH('')
                    ), '') AS fold_output_name
                FROM
                    db_1.schema_1.[Animal] AS [Animal_2]
            ) AS folded_subquery_1 ON [Animal_1].uuid = folded_subquery_1.uuid
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_on_many_to_one_edge(self) -> None:
        test_data = test_input_data.fold_on_many_to_one_edge()

        # Even though out_Animal_LivesIn is a many to one edge, primary key should
        # be the join predicate for the folded subquery.
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[]) AS homes_list
            FROM
                schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Location_1".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Location" AS "Location_1" ON "Animal_2".lives_in = "Location_1".uuid
                GROUP BY
                    "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_name AS homes_list
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            JOIN (
                SELECT
                    [Animal_2].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Location_1].name, '^', '^e'),
                                    '~',
                                    '^n'),
                                '|',
                                '^d'),
                            '~')
                        FROM
                            db_1.schema_1.[Location] AS [Location_1]
                        WHERE
                            [Animal_2].lives_in = [Location_1].uuid FOR XML PATH('')
                    ), '') AS fold_output_name
                FROM
                    db_1.schema_1.[Animal] AS [Animal_2]
            ) AS folded_subquery_1 ON [Animal_1].uuid = folded_subquery_1.uuid
        """

        expected_match = SKIP_TEST
        expected_gremlin = SKIP_TEST
        expected_cypher = SKIP_TEST
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_after_recurse(self) -> None:
        # This is a regression test, checking that:
        # - the fold subquery picks the right column of the recursive cte to join to
        # - the recursive CTE exposes the columns needed to perform the folded traverse
        #
        # Testing in any of the SQL backends is sufficient.
        test_data = test_input_data.fold_after_recurse()

        expected_postgresql = SKIP_TEST
        expected_mssql = """

        WITH anon_1(lives_in, parent, uuid, __cte_key, __cte_depth) AS (
            SELECT
                [Animal_2].lives_in AS lives_in,
                [Animal_2].parent AS parent,
                [Animal_2].uuid AS uuid,
                [Animal_2].uuid AS __cte_key,
                0 AS __cte_depth
            FROM
                db_1.schema_1.[Animal] AS [Animal_2]
            UNION ALL
            SELECT
                [Animal_3].lives_in AS lives_in,
                [Animal_3].parent AS parent,
                [Animal_3].uuid AS uuid,
                anon_1.__cte_key AS __cte_key,
                anon_1.__cte_depth + 1 AS __cte_depth
            FROM
                anon_1
            JOIN db_1.schema_1.[Animal] AS [Animal_3] ON
                anon_1.uuid = [Animal_3].parent
            WHERE
                anon_1.__cte_depth < 3)
        SELECT
            [Animal_1].name AS animal_name,
            folded_subquery_1.fold_output_name AS homes_list
        FROM
            db_1.schema_1.[Animal] AS [Animal_1]
            JOIN anon_1
                ON [Animal_1].uuid = anon_1.__cte_key
            JOIN (
                SELECT
                    anon_2.uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Location_1].name, '^', '^e'),
                                    '~',
                                    '^n'),
                                '|',
                                '^d'),
                            '~')
                        FROM
                            db_1.schema_1.[Location] AS [Location_1]
                        WHERE
                            anon_2.lives_in = [Location_1].uuid FOR XML PATH ('')),
                   '') AS fold_output_name
                FROM anon_1 AS anon_2
            ) AS folded_subquery_1
                ON anon_1.uuid = folded_subquery_1.uuid
        """
        expected_match = SKIP_TEST
        expected_gremlin = SKIP_TEST
        expected_cypher = SKIP_TEST
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_on_two_output_variables(self) -> None:
        test_data = test_input_data.fold_on_two_output_variables()

        expected_postgresql = """
            SELECT
              "Animal_1".name AS animal_name,
              coalesce(folded_subquery_1.fold_output_color, ARRAY[]::VARCHAR[]) AS child_color_list,
              coalesce(
                folded_subquery_1.fold_output_name,
                ARRAY [] :: VARCHAR []
              ) AS child_names_list
            FROM
                schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".name) AS fold_output_name,
                    array_agg("Animal_3".color) AS fold_output_color
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3" ON "Animal_2".uuid = "Animal_3".parent
                GROUP BY
                    "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
        """
        expected_mssql = NotImplementedError
        expected_match = SKIP_TEST
        expected_gremlin = SKIP_TEST
        expected_cypher = SKIP_TEST
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_same_edge_type_in_different_locations(self) -> None:
        test_data = test_input_data.fold_same_edge_type_in_different_locations()

        expected_postgresql = """
            SELECT
              "Animal_1".name AS animal_name,
              coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                AS child_names_list,
              coalesce(folded_subquery_2.fold_output_name, ARRAY[]::VARCHAR[])
                AS sibling_and_self_names_list
            FROM
              schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".name) AS fold_output_name
                FROM
                  schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3" ON "Animal_2".uuid = "Animal_3".parent
                GROUP BY
                  "Animal_2".uuid
            ) AS folded_subquery_1 ON "Animal_1".uuid = folded_subquery_1.uuid
            JOIN schema_1."Animal" AS "Animal_4" ON "Animal_1".parent = "Animal_4".uuid
            LEFT OUTER JOIN (
                SELECT
                    "Animal_5".uuid AS uuid,
                    array_agg("Animal_6".name) AS fold_output_name
                FROM
                  schema_1."Animal" AS "Animal_5"
                JOIN schema_1."Animal" AS "Animal_6" ON "Animal_5".uuid = "Animal_6".parent
                GROUP BY
                  "Animal_5".uuid
            ) AS folded_subquery_2 ON "Animal_4".uuid = folded_subquery_2.uuid
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_name AS child_names_list,
                folded_subquery_2.fold_output_name AS sibling_and_self_names_list
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            JOIN (
                SELECT
                    [Animal_2].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Animal_3].name, '^', '^e'),
                                    '~',
                                    '^n'),
                                '|',
                                '^d'),
                            '~')
                        FROM
                            db_1.schema_1.[Animal] AS [Animal_3]
                        WHERE
                            [Animal_2].uuid = [Animal_3].parent FOR XML PATH('')),
                    '') AS fold_output_name
                FROM
                    db_1.schema_1.[Animal] AS [Animal_2]
            ) AS folded_subquery_1 ON [Animal_1].uuid = folded_subquery_1.uuid
            JOIN db_1.schema_1.[Animal] AS [Animal_4] ON [Animal_1].parent = [Animal_4].uuid
            JOIN (
                SELECT
                    [Animal_5].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Animal_6].name, '^', '^e'),
                                    '~',
                                    '^n'),
                                '|',
                                '^d'),
                            '~')
                        FROM
                            db_1.schema_1.[Animal] AS [Animal_6]
                        WHERE
                            [Animal_5].uuid = [Animal_6].parent FOR XML PATH('')),
                    '') AS fold_output_name
                FROM
                    db_1.schema_1.[Animal] AS [Animal_5]
            ) AS folded_subquery_2 ON [Animal_4].uuid = folded_subquery_2.uuid
        """

        expected_match = SKIP_TEST
        expected_gremlin = SKIP_TEST
        expected_cypher = SKIP_TEST
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_after_traverse(self) -> None:
        test_data = test_input_data.fold_after_traverse()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal__in_Animal_ParentOf___1___out_Animal_ParentOf.name
                    AS `sibling_and_self_names_list`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    class: Animal,
                    as: Animal__in_Animal_ParentOf___1
                }}
                RETURN $matches
            ) LET
                $Animal__in_Animal_ParentOf___1___out_Animal_ParentOf =
                    Animal__in_Animal_ParentOf___1.out("Animal_ParentOf").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .in('Animal_ParentOf')
            .as('Animal__in_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                sibling_and_self_names_list: (
                    (m.Animal__in_Animal_ParentOf___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal__in_Animal_ParentOf___1.out_Animal_ParentOf.collect{
                            entry -> entry.inV.next().name
                        }
                    )
                )
            ])}
        """
        expected_postgresql = """
            SELECT
              "Animal_1".name AS animal_name,
              coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                AS sibling_and_self_names_list
            FROM
              schema_1."Animal" AS "Animal_1"
            JOIN schema_1."Animal" AS "Animal_2"
            ON "Animal_1".parent = "Animal_2".uuid
            LEFT OUTER JOIN(
                SELECT
                    "Animal_3".uuid AS uuid,
                    array_agg("Animal_4".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_3"
                JOIN schema_1."Animal" AS "Animal_4"
                ON "Animal_3".uuid = "Animal_4".parent
                GROUP BY "Animal_3".uuid
            ) AS folded_subquery_1
            ON "Animal_2".uuid = folded_subquery_1.uuid
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH
              (Animal__in_Animal_ParentOf___1)-[:Animal_ParentOf]->
              (Animal__in_Animal_ParentOf__out_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              Animal__in_Animal_ParentOf___1 AS Animal__in_Animal_ParentOf___1,
              collect(Animal__in_Animal_ParentOf__out_Animal_ParentOf___1) AS
                collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1 | x.name] AS
                `sibling_and_self_names_list`
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_name AS sibling_and_self_names_list
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            JOIN db_1.schema_1.[Animal] AS [Animal_2] ON [Animal_1].parent = [Animal_2].uuid
            JOIN(
                SELECT
                    [Animal_3].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Animal_4].name, '^', '^e'),
                                    '~',
                                    '^n'),
                                '|',
                                '^d'),
                            '~')
                        FROM
                            db_1.schema_1.[Animal] AS [Animal_4]
                        WHERE
                            [Animal_3].uuid = [Animal_4].parent FOR XML PATH('')),
                    '') AS fold_output_name
                FROM
                    db_1.schema_1.[Animal] AS [Animal_3]
            ) AS folded_subquery_1 ON [Animal_2].uuid = folded_subquery_1.uuid
        """
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_after_traverse_different_types(self) -> None:
        test_data = test_input_data.fold_after_traverse_different_types()

        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_name AS neighbor_and_self_names_list
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            JOIN db_1.schema_1.[Location] AS [Location_1] ON [Animal_1].lives_in = [Location_1].uuid
            JOIN (
                SELECT
                    [Location_2].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Animal_2].name, '^', '^e'),
                                    '~',
                                    '^n'),
                                '|',
                                '^d'),
                            '~')
                        FROM
                            db_1.schema_1.[Animal] AS [Animal_2]
                        WHERE
                            [Location_2].uuid = [Animal_2].lives_in FOR XML PATH('')),
                    '') AS fold_output_name
                FROM
                    db_1.schema_1.[Location] AS [Location_2]
            ) AS folded_subquery_1 ON [Location_1].uuid = folded_subquery_1.uuid
        """
        expected_postgresql = """
            SELECT
              "Animal_1".name AS animal_name,
              coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                  AS neighbor_and_self_names_list
            FROM schema_1."Animal" AS "Animal_1"
            JOIN schema_1."Location" AS "Location_1"
            ON "Animal_1".lives_in = "Location_1".uuid
            LEFT OUTER JOIN (
                SELECT
                  "Location_2".uuid AS uuid,
                  array_agg("Animal_2".name) AS fold_output_name
                FROM schema_1."Location" AS "Location_2"
                JOIN schema_1."Animal" AS "Animal_2"
                ON "Location_2".uuid = "Animal_2".lives_in
                GROUP BY "Location_2".uuid
            ) AS folded_subquery_1
            ON "Location_1".uuid = folded_subquery_1.uuid
        """

        expected_match = SKIP_TEST
        expected_gremlin = SKIP_TEST
        expected_cypher = SKIP_TEST
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_after_traverse_no_output_on_root(self) -> None:
        test_data = test_input_data.fold_after_traverse_no_output_on_root()

        expected_postgresql = """
            SELECT
                "Location_1".name AS location_name,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                    AS neighbor_and_self_names_list
            FROM schema_1."Animal" AS "Animal_1"
            JOIN schema_1."Location" AS "Location_1"
            ON "Animal_1".lives_in = "Location_1".uuid
            LEFT OUTER JOIN (
                SELECT
                    "Location_2".uuid AS uuid,
                    array_agg("Animal_2".name) AS fold_output_name
                FROM schema_1."Location" AS "Location_2"
                JOIN schema_1."Animal" AS "Animal_2"
                ON "Location_2".uuid = "Animal_2".lives_in
                GROUP BY "Location_2".uuid
            ) AS folded_subquery_1
            ON "Location_1".uuid = folded_subquery_1.uuid
        """
        expected_mssql = """
            SELECT
                [Location_1].name AS location_name,
                folded_subquery_1.fold_output_name AS neighbor_and_self_names_list
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            JOIN db_1.schema_1.[Location] AS [Location_1] ON [Animal_1].lives_in = [Location_1].uuid
            JOIN (
                SELECT
                    [Location_2].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Animal_2].name, '^', '^e'),
                                    '~',
                                    '^n'),
                                '|',
                                '^d'),
                            '~')
                        FROM
                            db_1.schema_1.[Animal] AS [Animal_2]
                        WHERE
                            [Location_2].uuid = [Animal_2].lives_in FOR XML PATH('')),
                    '') AS fold_output_name
                FROM
                    db_1.schema_1.[Location] AS [Location_2]
            ) AS folded_subquery_1 ON [Location_1].uuid = folded_subquery_1.uuid
        """
        expected_match = SKIP_TEST
        expected_gremlin = SKIP_TEST
        expected_cypher = SKIP_TEST
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_and_traverse(self) -> None:
        test_data = test_input_data.fold_and_traverse()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___in_Animal_ParentOf.name
                    AS `sibling_and_self_names_list`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___in_Animal_ParentOf =
                    Animal___1.in("Animal_ParentOf").out("Animal_ParentOf").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                sibling_and_self_names_list: (
                    (m.Animal___1.in_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.in_Animal_ParentOf
                            .collect{
                                entry -> entry.outV.next()
                            }
                            .collectMany{
                                entry -> entry.out_Animal_ParentOf
                                    .collect{
                                        edge -> edge.inV.next()
                                    }
                            }
                            .collect{entry -> entry.name}
                    ))
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_name AS sibling_and_self_names_list
            FROM db_1.schema_1.[Animal] AS [Animal_1]
            JOIN (
                SELECT
                    [Animal_2].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Animal_3].name, '^', '^e'),
                                    '~', '^n'),
                                '|', '^d'),
                            '~')
                        FROM db_1.schema_1.[Animal] AS [Animal_4]
                        JOIN db_1.schema_1.[Animal] AS [Animal_3]
                        ON [Animal_4].uuid = [Animal_3].parent
                        WHERE [Animal_2].parent = [Animal_4].uuid
                        FOR XML PATH ('')
                    ), '') AS fold_output_name
                FROM db_1.schema_1.[Animal] AS [Animal_2]) AS folded_subquery_1
                ON [Animal_1].uuid = folded_subquery_1.uuid
            """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH
              (Animal__in_Animal_ParentOf___1)-[:Animal_ParentOf]->
              (Animal__in_Animal_ParentOf__out_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              collect(Animal__in_Animal_ParentOf___1) AS
                collected_Animal__in_Animal_ParentOf___1,
              collect(Animal__in_Animal_ParentOf__out_Animal_ParentOf___1) AS
                collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1 | x.name] AS
                `sibling_and_self_names_list`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                    AS sibling_and_self_names_list
            FROM
                schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_4"
                ON "Animal_2".parent = "Animal_4".uuid
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_4".uuid = "Animal_3".parent
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_and_deep_traverse(self) -> None:
        test_data = test_input_data.fold_and_deep_traverse()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___in_Animal_ParentOf.name AS `sibling_and_self_species_list`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___in_Animal_ParentOf =
                    Animal___1.in("Animal_ParentOf")
                              .out("Animal_ParentOf")
                              .out("Animal_OfSpecies")
                              .asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                sibling_and_self_species_list: (
                    (m.Animal___1.in_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.in_Animal_ParentOf
                            .collect{entry -> entry.outV.next()}
                            .collectMany{
                                entry -> entry.out_Animal_ParentOf
                                    .collect{edge -> edge.inV.next()}
                            }
                            .collectMany{
                                entry -> entry.out_Animal_OfSpecies
                                    .collect{edge -> edge.inV.next()}
                            }
                            .collect{entry -> entry.name}
                    )
                )
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_name AS sibling_and_self_species_list
            FROM db_1.schema_1.[Animal] AS [Animal_1]
            JOIN (
                SELECT
                    [Animal_2].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Species_1].name, '^', '^e'),
                                    '~', '^n'),
                                '|', '^d'),
                            '~')
                        FROM db_1.schema_1.[Animal] AS [Animal_3]
                        JOIN db_1.schema_1.[Animal] AS [Animal_4]
                        ON [Animal_3].uuid = [Animal_4].parent
                        JOIN db_1.schema_1.[Species] AS [Species_1]
                        ON [Animal_4].species = [Species_1].uuid
                        WHERE [Animal_2].parent = [Animal_3].uuid
                        FOR XML PATH ('')
                    ), '') AS fold_output_name
                FROM db_1.schema_1.[Animal] AS [Animal_2]
            ) AS folded_subquery_1
            ON [Animal_1].uuid = folded_subquery_1.uuid
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH
              (Animal__in_Animal_ParentOf___1)-[:Animal_ParentOf]->
              (Animal__in_Animal_ParentOf__out_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH
              (Animal__in_Animal_ParentOf__out_Animal_ParentOf___1)-[:Animal_OfSpecies]->
              (Animal__in_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1:Species)
            WITH
              Animal___1 AS Animal___1,
              collect(Animal__in_Animal_ParentOf___1) AS
                collected_Animal__in_Animal_ParentOf___1,
              collect(Animal__in_Animal_ParentOf__out_Animal_ParentOf___1) AS
                collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1,
              collect(Animal__in_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1) AS
                collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN
                collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1
                | x.name] AS `sibling_and_self_species_list`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                    AS sibling_and_self_species_list
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Species_1".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_2".parent = "Animal_3".uuid
                JOIN schema_1."Animal" AS "Animal_4"
                ON "Animal_3".uuid = "Animal_4".parent
                JOIN schema_1."Species" AS "Species_1"
                ON "Animal_4".species = "Species_1".uuid
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
            """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_traverse_and_fold_and_traverse(self) -> None:
        test_data = test_input_data.traverse_and_fold_and_traverse()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal__in_Animal_ParentOf___1___out_Animal_ParentOf.name
                    AS `sibling_and_self_species_list`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    class: Animal,
                    as: Animal__in_Animal_ParentOf___1
                }}
                RETURN $matches
            ) LET
                $Animal__in_Animal_ParentOf___1___out_Animal_ParentOf =
                    Animal__in_Animal_ParentOf___1
                        .out("Animal_ParentOf")
                        .out("Animal_OfSpecies").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .in('Animal_ParentOf')
                .as('Animal__in_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                sibling_and_self_species_list: (
                    (m.Animal__in_Animal_ParentOf___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal__in_Animal_ParentOf___1.out_Animal_ParentOf
                            .collect{
                                entry -> entry.inV.next()
                            }
                            .collectMany{
                                entry -> entry.out_Animal_OfSpecies
                                    .collect{
                                        edge -> edge.inV.next()
                                    }
                            }
                            .collect{entry -> entry.name}
                    ))
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_name AS sibling_and_self_species_list
            FROM db_1.schema_1.[Animal] AS [Animal_1]
            JOIN db_1.schema_1.[Animal] AS [Animal_2]
            ON [Animal_1].parent = [Animal_2].uuid
            JOIN (
                SELECT
                    [Animal_3].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Species_1].name, '^', '^e'),
                                    '~', '^n'),
                                '|', '^d'),
                            '~')
                        FROM db_1.schema_1.[Animal] AS [Animal_4]
                        JOIN db_1.schema_1.[Species] AS [Species_1]
                        ON [Animal_4].species = [Species_1].uuid
                        WHERE [Animal_3].uuid = [Animal_4].parent
                        FOR XML PATH ('')
                    ), '') AS fold_output_name
                FROM db_1.schema_1.[Animal] AS [Animal_3]
            ) AS folded_subquery_1 ON [Animal_2].uuid = folded_subquery_1.uuid
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH
              (Animal__in_Animal_ParentOf___1)-[:Animal_ParentOf]->
              (Animal__in_Animal_ParentOf__out_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH
              (Animal__in_Animal_ParentOf__out_Animal_ParentOf___1)-[:Animal_OfSpecies]->
              (Animal__in_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1:Species)
            WITH
              Animal___1 AS Animal___1,
              Animal__in_Animal_ParentOf___1 AS Animal__in_Animal_ParentOf___1,
              collect(Animal__in_Animal_ParentOf__out_Animal_ParentOf___1) AS
                collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1,
              collect(Animal__in_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1) AS
                collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN
                collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1
                | x.name] AS `sibling_and_self_species_list`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                    AS sibling_and_self_species_list
            FROM schema_1."Animal" AS "Animal_1"
            JOIN schema_1."Animal" AS "Animal_2"
            ON "Animal_1".parent = "Animal_2".uuid
            LEFT OUTER JOIN (
                SELECT
                    "Animal_3".uuid AS uuid,
                    array_agg("Species_1".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_3"
                JOIN schema_1."Animal" AS "Animal_4"
                ON "Animal_3".uuid = "Animal_4".parent
                JOIN schema_1."Species" AS "Species_1"
                ON "Animal_4".species = "Species_1".uuid
                GROUP BY "Animal_3".uuid
            ) AS folded_subquery_1
            ON "Animal_2".uuid = folded_subquery_1.uuid
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_and_filter_and_traverse_and_output(self) -> None:
        test_data = test_input_data.fold_and_filter_and_traverse_and_output()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___in_Animal_ParentOf.name AS `grand_parent_list`
            FROM  (
                MATCH  {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            )
            LET
                $Animal___1___in_Animal_ParentOf = Animal___1.in("Animal_ParentOf")[
                    (net_worth > {parent_min_worth})
            ].in("Animal_ParentOf").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                grand_parent_list: (
                    (m.Animal___1.in_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.in_Animal_ParentOf
                            .collect{entry -> entry.outV.next()}
                            .findAll{entry -> (entry.net_worth > $parent_min_worth)}
                            .collectMany{
                                entry -> entry.in_Animal_ParentOf.collect{edge -> edge.outV.next()}
                            }
                            .collect{entry -> entry.name}
                    )
                )
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_name AS grand_parent_list
            FROM db_1.schema_1.[Animal] AS [Animal_1]
            JOIN (
                SELECT
                    [Animal_2].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Animal_3].name, '^', '^e'),
                                    '~', '^n'),
                                '|', '^d'),
                            '~')
                        FROM db_1.schema_1.[Animal] AS [Animal_4]
                        JOIN db_1.schema_1.[Animal] AS [Animal_3]
                        ON [Animal_4].parent = [Animal_3].uuid
                        WHERE [Animal_2].parent = [Animal_4].uuid
                        AND [Animal_4].net_worth > :parent_min_worth
                        FOR XML PATH ('')
                    ), '') AS fold_output_name
                FROM db_1.schema_1.[Animal] AS [Animal_2]
            ) AS folded_subquery_1
            ON [Animal_1].uuid = folded_subquery_1.uuid
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            WHERE (Animal__in_Animal_ParentOf___1.net_worth > $parent_min_worth)
            OPTIONAL MATCH (
                Animal__in_Animal_ParentOf___1)<-
                [:Animal_ParentOf]-(Animal__in_Animal_ParentOf__in_Animal_ParentOf___1:Animal)
            WITH
                Animal___1 AS Animal___1,
                collect(Animal__in_Animal_ParentOf___1) AS collected_Animal__in_Animal_ParentOf___1,
                collect(Animal__in_Animal_ParentOf__in_Animal_ParentOf___1)
                    AS collected_Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
            RETURN
                Animal___1.name AS `animal_name`,
                [x IN collected_Animal__in_Animal_ParentOf__in_Animal_ParentOf___1 | x.name]
                    AS `grand_parent_list`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                    AS grand_parent_list
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_4"
                ON "Animal_2".parent = "Animal_4".uuid
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_4".parent = "Animal_3".uuid
                WHERE "Animal_4".net_worth > :parent_min_worth
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
        """
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_multiple_outputs_in_same_fold(self) -> None:
        test_data = test_input_data.multiple_outputs_in_same_fold()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___out_Animal_ParentOf.name AS `child_names_list`,
                $Animal___1___out_Animal_ParentOf.uuid AS `child_uuids_list`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___out_Animal_ParentOf = Animal___1.out("Animal_ParentOf").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_names_list: (
                    (m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.out_Animal_ParentOf
                            .collect{entry -> entry.inV.next().name}
                    )
                ),
                child_uuids_list: (
                    (m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.out_Animal_ParentOf
                            .collect{entry -> entry.inV.next().uuid}
                    )
                )
            ])}
        """
        expected_mssql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              collect(Animal__out_Animal_ParentOf___1) AS collected_Animal__out_Animal_ParentOf___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN collected_Animal__out_Animal_ParentOf___1 | x.name] AS `child_names_list`,
              [x IN collected_Animal__out_Animal_ParentOf___1 | x.uuid] AS `child_uuids_list`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                    AS child_names_list,
                coalesce(folded_subquery_1.fold_output_uuid, ARRAY[]::VARCHAR[]) AS child_uuids_list
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".uuid) AS fold_output_uuid,
                    array_agg("Animal_3".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_2".uuid = "Animal_3".parent
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_multiple_outputs_in_same_fold_and_traverse(self) -> None:
        test_data = test_input_data.multiple_outputs_in_same_fold_and_traverse()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___in_Animal_ParentOf.name AS `sibling_and_self_names_list`,
                $Animal___1___in_Animal_ParentOf.uuid AS `sibling_and_self_uuids_list`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___in_Animal_ParentOf =
                    Animal___1.in("Animal_ParentOf").out("Animal_ParentOf").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                sibling_and_self_names_list:
                    ((m.Animal___1.in_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.in_Animal_ParentOf
                            .collect{entry -> entry.outV.next()}
                            .collectMany{
                                entry -> entry.out_Animal_ParentOf
                                    .collect{
                                        edge -> edge.inV.next()
                                    }
                            }
                            .collect{entry -> entry.name}
                    )),
                sibling_and_self_uuids_list:
                    ((m.Animal___1.in_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.in_Animal_ParentOf
                            .collect{entry -> entry.outV.next()}
                            .collectMany{
                                entry -> entry.out_Animal_ParentOf
                                    .collect{
                                        edge -> edge.inV.next()
                                    }
                            }
                            .collect{entry -> entry.uuid}
                    ))
            ])}
        """
        expected_mssql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH
              (Animal__in_Animal_ParentOf___1)-[:Animal_ParentOf]->
              (Animal__in_Animal_ParentOf__out_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              collect(Animal__in_Animal_ParentOf___1) AS collected_Animal__in_Animal_ParentOf___1,
              collect(Animal__in_Animal_ParentOf__out_Animal_ParentOf___1) AS
                collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1 | x.name] AS
                `sibling_and_self_names_list`,
              [x IN collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1 | x.uuid] AS
                `sibling_and_self_uuids_list`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                    AS sibling_and_self_names_list,
                coalesce(folded_subquery_1.fold_output_uuid, ARRAY[]::VARCHAR[])
                    AS sibling_and_self_uuids_list
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".uuid) AS fold_output_uuid,
                    array_agg("Animal_3".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_4"
                ON "Animal_2".parent = "Animal_4".uuid
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_4".uuid = "Animal_3".parent
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_multiple_folds(self) -> None:
        test_data = test_input_data.multiple_folds()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___out_Animal_ParentOf.name AS `child_names_list`,
                $Animal___1___out_Animal_ParentOf.uuid AS `child_uuids_list`,
                $Animal___1___in_Animal_ParentOf.name AS `parent_names_list`,
                $Animal___1___in_Animal_ParentOf.uuid AS `parent_uuids_list`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___in_Animal_ParentOf = Animal___1.in("Animal_ParentOf").asList(),
                $Animal___1___out_Animal_ParentOf = Animal___1.out("Animal_ParentOf").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_names_list: (
                    (m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.out_Animal_ParentOf.collect{entry -> entry.inV.next().name}
                    )
                ),
                child_uuids_list: (
                    (m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.out_Animal_ParentOf.collect{entry -> entry.inV.next().uuid}
                    )
                ),
                parent_names_list: (
                    (m.Animal___1.in_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.in_Animal_ParentOf.collect{entry -> entry.outV.next().name}
                    )
                ),
                parent_uuids_list: (
                    (m.Animal___1.in_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.in_Animal_ParentOf.collect{entry -> entry.outV.next().uuid}
                    )
                )
            ])}
        """
        expected_mssql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              collect(Animal__in_Animal_ParentOf___1) AS collected_Animal__in_Animal_ParentOf___1
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              collected_Animal__in_Animal_ParentOf___1 AS collected_Animal__in_Animal_ParentOf___1,
              collect(Animal__out_Animal_ParentOf___1) AS collected_Animal__out_Animal_ParentOf___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN collected_Animal__out_Animal_ParentOf___1 | x.name] AS `child_names_list`,
              [x IN collected_Animal__out_Animal_ParentOf___1 | x.uuid] AS `child_uuids_list`,
              [x IN collected_Animal__in_Animal_ParentOf___1 | x.name] AS `parent_names_list`,
              [x IN collected_Animal__in_Animal_ParentOf___1 | x.uuid] AS `parent_uuids_list`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                    AS child_names_list,
                coalesce(folded_subquery_1.fold_output_uuid, ARRAY[]::VARCHAR[])
                    AS child_uuids_list,
                coalesce(folded_subquery_2.fold_output_name, ARRAY[]::VARCHAR[])
                    AS parent_names_list,
                coalesce(folded_subquery_2.fold_output_uuid, ARRAY[]::VARCHAR[])
                    AS parent_uuids_list
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".uuid) AS fold_output_uuid,
                    array_agg("Animal_3".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_2".uuid = "Animal_3".parent
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
            LEFT OUTER JOIN (
                SELECT
                    "Animal_4".uuid AS uuid,
                    array_agg("Animal_5".uuid) AS fold_output_uuid,
                    array_agg("Animal_5".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_4"
                JOIN schema_1."Animal" AS "Animal_5"
                ON "Animal_4".parent = "Animal_5".uuid
                GROUP BY "Animal_4".uuid
            ) AS folded_subquery_2
            ON "Animal_1".uuid = folded_subquery_2.uuid
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_multiple_folds_and_traverse(self) -> None:
        test_data = test_input_data.multiple_folds_and_traverse()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___in_Animal_ParentOf.name AS `sibling_and_self_names_list`,
                $Animal___1___in_Animal_ParentOf.uuid AS `sibling_and_self_uuids_list`,
                $Animal___1___out_Animal_ParentOf.name AS `spouse_and_self_names_list`,
                $Animal___1___out_Animal_ParentOf.uuid AS `spouse_and_self_uuids_list`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___in_Animal_ParentOf =
                    Animal___1.in("Animal_ParentOf").out("Animal_ParentOf").asList(),
                $Animal___1___out_Animal_ParentOf =
                    Animal___1.out("Animal_ParentOf").in("Animal_ParentOf").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                sibling_and_self_names_list: ((m.Animal___1.in_Animal_ParentOf == null) ? [] : (
                    m.Animal___1.in_Animal_ParentOf
                        .collect{entry -> entry.outV.next()}
                        .collectMany{
                            entry -> entry.out_Animal_ParentOf
                                .collect{
                                    edge -> edge.inV.next()
                                }
                        }
                        .collect{entry -> entry.name}
                )),
                sibling_and_self_uuids_list: ((m.Animal___1.in_Animal_ParentOf == null) ? [] : (
                    m.Animal___1.in_Animal_ParentOf
                        .collect{entry -> entry.outV.next()}
                        .collectMany{
                            entry -> entry.out_Animal_ParentOf
                                .collect{
                                    edge -> edge.inV.next()
                                }
                        }
                        .collect{entry -> entry.uuid}
                )),
                spouse_and_self_names_list: ((m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                    m.Animal___1.out_Animal_ParentOf
                        .collect{entry -> entry.inV.next()}
                        .collectMany{
                            entry -> entry.in_Animal_ParentOf
                                .collect{
                                    edge -> edge.outV.next()
                                }
                        }
                        .collect{entry -> entry.name}
                )),
                spouse_and_self_uuids_list: ((m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                    m.Animal___1.out_Animal_ParentOf
                        .collect{entry -> entry.inV.next()}
                        .collectMany{
                            entry -> entry.in_Animal_ParentOf
                                .collect{
                                    edge -> edge.outV.next()
                                }
                        }
                        .collect{entry -> entry.uuid}
                ))
            ])}
        """
        expected_mssql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH (Animal__in_Animal_ParentOf___1)-[:Animal_ParentOf]->
              (Animal__in_Animal_ParentOf__out_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              collect(Animal__in_Animal_ParentOf___1) AS collected_Animal__in_Animal_ParentOf___1,
              collect(Animal__in_Animal_ParentOf__out_Animal_ParentOf___1) AS
                collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH
              (Animal__out_Animal_ParentOf___1)<-[:Animal_ParentOf]-
              (Animal__out_Animal_ParentOf__in_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              collected_Animal__in_Animal_ParentOf___1 AS collected_Animal__in_Animal_ParentOf___1,
              collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1 AS
                collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1,
              collect(Animal__out_Animal_ParentOf___1) AS collected_Animal__out_Animal_ParentOf___1,
              collect(Animal__out_Animal_ParentOf__in_Animal_ParentOf___1) AS
                collected_Animal__out_Animal_ParentOf__in_Animal_ParentOf___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1 | x.name] AS
                `sibling_and_self_names_list`,
              [x IN collected_Animal__in_Animal_ParentOf__out_Animal_ParentOf___1 | x.uuid] AS
                `sibling_and_self_uuids_list`,
              [x IN collected_Animal__out_Animal_ParentOf__in_Animal_ParentOf___1 | x.name] AS
                `spouse_and_self_names_list`,
              [x IN collected_Animal__out_Animal_ParentOf__in_Animal_ParentOf___1 | x.uuid] AS
                `spouse_and_self_uuids_list`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_2.fold_output_name, ARRAY[]::VARCHAR[])
                    AS sibling_and_self_names_list,
                coalesce(folded_subquery_2.fold_output_uuid, ARRAY[]::VARCHAR[])
                    AS sibling_and_self_uuids_list,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                    AS spouse_and_self_names_list,
                coalesce(folded_subquery_1.fold_output_uuid, ARRAY[]::VARCHAR[])
                    AS spouse_and_self_uuids_list
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".uuid) AS fold_output_uuid,
                    array_agg("Animal_3".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_4"
                ON "Animal_2".uuid = "Animal_4".parent
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_4".parent = "Animal_3".uuid
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
            LEFT OUTER JOIN (
                SELECT
                    "Animal_5".uuid AS uuid,
                    array_agg("Animal_6".uuid) AS fold_output_uuid,
                    array_agg("Animal_6".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_5"
                JOIN schema_1."Animal" AS "Animal_7"
                ON "Animal_5".parent = "Animal_7".uuid
                JOIN schema_1."Animal" AS "Animal_6"
                ON "Animal_7".uuid = "Animal_6".parent
                GROUP BY "Animal_5".uuid
            ) AS folded_subquery_2
            ON "Animal_1".uuid = folded_subquery_2.uuid
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_date_and_datetime_fields(self) -> None:
        test_data = test_input_data.fold_date_and_datetime_fields()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___out_Animal_ParentOf.birthday.format("yyyy-MM-dd")
                    AS `child_birthdays_list`,
                $Animal___1___out_Animal_FedAt.event_date.format("yyyy-MM-dd'T'HH:mm:ss")
                    AS `fed_at_datetimes_list`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___out_Animal_FedAt = Animal___1.out("Animal_FedAt").asList(),
                $Animal___1___out_Animal_ParentOf = Animal___1.out("Animal_ParentOf").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_birthdays_list: (
                    (m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.out_Animal_ParentOf.collect{
                            entry -> entry.inV
                                .next().birthday
                                .format("yyyy-MM-dd")
                        }
                    )
                ),
                fed_at_datetimes_list: (
                    (m.Animal___1.out_Animal_FedAt == null) ? [] : (
                        m.Animal___1.out_Animal_FedAt.collect{
                            entry ->
                                entry.inV.next()
                                    .event_date.format("yyyy-MM-dd'T'HH:mm:ss")
                        }
                    )
                )
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_birthday AS child_birthdays_list,
                folded_subquery_2.fold_output_event_date AS fed_at_datetimes_list
            FROM db_1.schema_1.[Animal] AS [Animal_1]
            JOIN (
                SELECT
                    [Animal_2].uuid AS uuid,
                    coalesce(
                        (
                            SELECT '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE(
                                            [Animal_3].birthday, '^', '^e'
                                        ),
                                    '~', '^n'),
                                '|', '^d'),
                            '~')
                        FROM db_1.schema_1.[Animal] AS [Animal_3]
                        WHERE [Animal_2].uuid = [Animal_3].parent
                        FOR XML PATH ('') ), ''
                    ) AS fold_output_birthday
                FROM db_1.schema_1.[Animal] AS [Animal_2]
            ) AS folded_subquery_1 ON [Animal_1].uuid = folded_subquery_1.uuid
            JOIN (
                SELECT
                    [Animal_4].uuid AS uuid,
                    coalesce(
                        (
                            SELECT '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE(
                                            [FeedingEvent_1].event_date, '^', '^e'
                                        ),
                                    '~', '^n'),
                                '|', '^d'),
                            '~')
                            FROM db_2.schema_1.[FeedingEvent] AS [FeedingEvent_1]
                            WHERE [Animal_4].fed_at = [FeedingEvent_1].uuid
                            FOR XML PATH ('')
                        ),
                    '') AS fold_output_event_date
                FROM db_1.schema_1.[Animal] AS [Animal_4]
            ) AS folded_subquery_2 ON [Animal_1].uuid = folded_subquery_2.uuid
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_1.fold_output_birthday, ARRAY[]::DATE[])
                    AS child_birthdays_list,
                coalesce(folded_subquery_2.fold_output_event_date, ARRAY[]::TIMESTAMP[])
                    AS fed_at_datetimes_list
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".birthday) AS fold_output_birthday
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_2".uuid = "Animal_3".parent
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
            LEFT OUTER JOIN (
                SELECT
                    "Animal_4".uuid AS uuid,
                    array_agg("FeedingEvent_1".event_date) AS fold_output_event_date
                FROM schema_1."Animal" AS "Animal_4"
                JOIN schema_1."FeedingEvent" AS "FeedingEvent_1"
                ON "Animal_4".fed_at = "FeedingEvent_1".uuid
                GROUP BY "Animal_4".uuid
            ) AS folded_subquery_2
            ON "Animal_1".uuid = folded_subquery_2.uuid
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)-[:Animal_FedAt]->(Animal__out_Animal_FedAt___1:FeedingEvent)
            WITH
              Animal___1 AS Animal___1,
              collect(Animal__out_Animal_FedAt___1) AS collected_Animal__out_Animal_FedAt___1
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              collected_Animal__out_Animal_FedAt___1 AS collected_Animal__out_Animal_FedAt___1,
              collect(Animal__out_Animal_ParentOf___1) AS collected_Animal__out_Animal_ParentOf___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN collected_Animal__out_Animal_ParentOf___1 | x.birthday] AS
                `child_birthdays_list`,
              [x IN collected_Animal__out_Animal_FedAt___1 | x.event_date] AS
                `fed_at_datetimes_list`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_coercion_to_union_base_type_inside_fold(self) -> None:
        # Given type_equivalence_hints = { Event: Union__BirthEvent__Event__FeedingEvent },
        # the coercion should be optimized away as a no-op.
        test_data = test_input_data.coercion_to_union_base_type_inside_fold()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___out_Animal_ImportantEvent.name AS `important_events`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___out_Animal_ImportantEvent =
                    Animal___1.out("Animal_ImportantEvent").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                important_events: (
                    (m.Animal___1.out_Animal_ImportantEvent == null) ? [] : (
                        m.Animal___1.out_Animal_ImportantEvent.collect{
                            entry -> entry.inV.next().name
                        }
                    )
                )
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST  # Type coercion not implemented for Cypher

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_no_op_coercion_inside_fold(self) -> None:
        # The type where the coercion is applied is already Entity, so the coercion is a no-op.
        test_data = test_input_data.no_op_coercion_inside_fold()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___out_Entity_Related.name AS `related_entities`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___out_Entity_Related = Animal___1.out("Entity_Related").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                related_entities: (
                    (m.Animal___1.out_Entity_Related == null) ? [] : (
                        m.Animal___1.out_Entity_Related.collect{
                            entry -> entry.inV.next().name
                        }
                    )
                )
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_name AS related_entities
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            JOIN (
                SELECT
                    [Animal_2].uuid AS uuid,
                    coalesce(
                        (
                            SELECT '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE(
                                            [Entity_1].name, '^', '^e'),
                                        '~', '^n'),
                                    '|', '^d'),
                                '~')
                            FROM
                                db_1.schema_1.[Entity] AS [Entity_1]
                            WHERE [Animal_2].related_entity = [Entity_1].uuid
                        FOR XML PATH ('')
                        ),
                    '') AS fold_output_name
                FROM
                    db_1.schema_1.[Animal] AS [Animal_2]
            ) AS folded_subquery_1
            ON [Animal_1].uuid = folded_subquery_1.uuid
        """
        expected_cypher = SKIP_TEST  # Type coercion not implemented for Cypher
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[]) AS related_entities
            FROM
                schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Entity_1".name) AS fold_output_name
                FROM
                    schema_1."Animal" AS "Animal_2"
                    JOIN schema_1."Entity" AS "Entity_1"
                        ON "Animal_2".related_entity = "Entity_1".uuid
                    GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
                    ON "Animal_1".uuid = folded_subquery_1.uuid
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_no_op_coercion_with_eligible_subpath(self) -> None:
        test_data = test_input_data.no_op_coercion_with_eligible_subpath()

        expected_match = """
            SELECT Animal__out_Animal_ParentOf__out_Animal_ParentOf___1.name
                AS `animal_name` FROM (MATCH {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal___1
            }}.out('Animal_ParentOf') {{
                as: Animal__out_Animal_ParentOf___1
            }}.out('Animal_ParentOf') {{
                as: Animal__out_Animal_ParentOf__out_Animal_ParentOf___1
            }} , {{
                where: ((@this INSTANCEOF 'Animal')),
                as: Animal__out_Animal_ParentOf___1
            }}.out('Entity_Related') {{
                class: Entity,
                where: (({entity_names} CONTAINS name)),
                as: Animal__out_Animal_ParentOf__out_Entity_Related___1
            }} RETURN $matches)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .out('Animal_ParentOf')
                .as('Animal__out_Animal_ParentOf___1')
                    .out('Animal_ParentOf')
                    .as('Animal__out_Animal_ParentOf__out_Animal_ParentOf___1')
                .back('Animal__out_Animal_ParentOf___1')
                    .out('Entity_Related')
                    .filter{it, m -> $entity_names.contains(it.name)}
                    .as('Animal__out_Animal_ParentOf__out_Entity_Related___1')
                .back('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal__out_Animal_ParentOf__out_Animal_ParentOf___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_2]
                JOIN db_1.schema_1.[Animal] AS [Animal_3]
                    ON [Animal_2].uuid = [Animal_3].parent
                JOIN db_1.schema_1.[Animal] AS [Animal_1]
                    ON [Animal_3].uuid = [Animal_1].parent
                JOIN db_1.schema_1.[Entity] AS [Entity_1]
                    ON [Animal_3].related_entity = [Entity_1].uuid
            WHERE
                [Entity_1].name IN :entity_names
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name
            FROM
                schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3"
                    ON "Animal_2".uuid = "Animal_3".parent
                JOIN schema_1."Animal" AS "Animal_1"
                    ON "Animal_3".uuid = "Animal_1".parent
                JOIN schema_1."Entity" AS "Entity_1"
                    ON "Animal_3".related_entity = "Entity_1".uuid
            WHERE
                "Entity_1".name IN :entity_names
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_filter_within_fold_scope(self) -> None:
        test_data = test_input_data.filter_within_fold_scope()

        expected_match = """
            SELECT
                $Animal___1___out_Animal_ParentOf.name AS `child_list`,
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___out_Animal_ParentOf =
                    Animal___1.out("Animal_ParentOf")[
                        (name LIKE ('%' + ({desired} + '%')))
                    ].asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_list: (
                    (m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.out_Animal_ParentOf
                         .collect{entry -> entry.inV.next()}
                         .findAll{entry -> entry.name.contains($desired)}
                         .collect{entry -> entry.name}
                    )
                ),
                name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                folded_subquery_1.fold_output_name AS child_list,
                [Animal_1].name AS name
            FROM db_1.schema_1.[Animal] AS [Animal_1]
            JOIN (
                SELECT
                    [Animal_2].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Animal_3].name, '^', '^e'),
                                    '~', '^n'),
                                '|', '^d'),
                            '~')
                        FROM db_1.schema_1.[Animal] AS [Animal_3]
                        WHERE [Animal_2].uuid = [Animal_3].parent
                        AND ([Animal_3].name LIKE '%' + :desired + '%')
                        FOR XML PATH ('')
                    ), '') AS fold_output_name
                FROM db_1.schema_1.[Animal] AS [Animal_2]
            ) AS folded_subquery_1
            ON [Animal_1].uuid = folded_subquery_1.uuid
        """
        expected_postgresql = """
            SELECT
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[]) AS child_list,
                "Animal_1".name AS name
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_2".uuid = "Animal_3".parent
                WHERE ("Animal_3".name LIKE '%%' || :desired || '%%')
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
                WHERE (
                  Animal__out_Animal_ParentOf___1.name CONTAINS $desired
                )
            WITH
              Animal___1 AS Animal___1,
              collect(Animal__out_Animal_ParentOf___1) AS collected_Animal__out_Animal_ParentOf___1
            RETURN
              [x IN collected_Animal__out_Animal_ParentOf___1 | x.name] AS
                `child_list`,
              Animal___1.name AS `name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_filter_and_multiple_outputs_within_fold_scope(self) -> None:
        test_data = test_input_data.filter_and_multiple_outputs_within_fold_scope()

        expected_match = """
            SELECT
                $Animal___1___out_Animal_ParentOf.description AS `child_descriptions`,
                $Animal___1___out_Animal_ParentOf.name AS `child_list`,
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___out_Animal_ParentOf =
                    Animal___1.out("Animal_ParentOf")[(name = {desired})].asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_descriptions: (
                    (m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.out_Animal_ParentOf
                         .collect{entry -> entry.inV.next()}
                         .findAll{entry -> (entry.name == $desired)}
                         .collect{entry -> entry.description}
                    )
                ),
                child_list: (
                    (m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.out_Animal_ParentOf
                         .collect{entry -> entry.inV.next()}
                         .findAll{entry -> (entry.name == $desired)}
                         .collect{entry -> entry.name}
                    )
                ),
                name: m.Animal___1.name
            ])}
        """
        expected_mssql = NotImplementedError
        expected_postgresql = """
            SELECT
                coalesce(folded_subquery_1.fold_output_description, ARRAY[]::VARCHAR[])
                    AS child_descriptions,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[]) AS child_list,
                "Animal_1".name AS name
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".name) AS fold_output_name,
                    array_agg("Animal_3".description) AS fold_output_description
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_2".uuid = "Animal_3".parent
                WHERE "Animal_3".name = :desired
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
                WHERE (
                  Animal__out_Animal_ParentOf___1.name = $desired
                )
            WITH
              Animal___1 AS Animal___1,
              collect(Animal__out_Animal_ParentOf___1) AS collected_Animal__out_Animal_ParentOf___1
            RETURN
              [x IN collected_Animal__out_Animal_ParentOf___1 | x.description] AS
                `child_descriptions`,
              [x IN collected_Animal__out_Animal_ParentOf___1 | x.name] AS
                `child_list`,
              Animal___1.name AS `name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_filter_on_fold_scope(self) -> None:
        test_data = test_input_data.filter_on_fold_scope()

        expected_match = """
            SELECT
                $Animal___1___out_Animal_ParentOf.name AS `child_list`,
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___out_Animal_ParentOf =
                    Animal___1.out("Animal_ParentOf")[((name = {desired})
                                                      OR (alias CONTAINS {desired}))].asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_list: (
                    (m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.out_Animal_ParentOf
                         .collect{entry -> entry.inV.next()}
                         .findAll{entry -> (
                            (entry.name == $desired) || entry.alias.contains($desired))}
                         .collect{entry -> entry.name}
                    )
                ),
                name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
                WHERE (
                    (Animal__out_Animal_ParentOf___1.name = $desired) OR
                    ($desired IN Animal__out_Animal_ParentOf___1.alias)
                )
            WITH
              Animal___1 AS Animal___1,
              collect(Animal__out_Animal_ParentOf___1) AS collected_Animal__out_Animal_ParentOf___1
            RETURN
              [x IN collected_Animal__out_Animal_ParentOf___1 | x.name] AS `child_list`,
              Animal___1.name AS `name`
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_coercion_on_interface_within_fold_scope(self) -> None:
        test_data = test_input_data.coercion_on_interface_within_fold_scope()

        expected_match = """
            SELECT
                Animal___1.name AS `name`,
                $Animal___1___out_Entity_Related.name AS `related_animals`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___out_Entity_Related =
                    Animal___1.out("Entity_Related")[(@this INSTANCEOF 'Animal')].asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name,
                related_animals: (
                    (m.Animal___1.out_Entity_Related == null) ? [] : (
                        m.Animal___1.out_Entity_Related
                         .collect{entry -> entry.inV.next()}
                         .findAll{entry -> ['Animal'].contains(entry['@class'])}
                         .collect{entry -> entry.name}
                    )
                )
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST  # Type coercion not implemented for Cypher

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_coercion_on_interface_within_fold_traversal(self) -> None:
        test_data = test_input_data.coercion_on_interface_within_fold_traversal()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___in_Animal_ParentOf.name AS `related_animal_species`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___in_Animal_ParentOf =
                    Animal___1.in("Animal_ParentOf")
                              .out("Entity_Related")[(@this INSTANCEOF 'Animal')]
                              .out("Animal_OfSpecies").asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                related_animal_species: ((m.Animal___1.in_Animal_ParentOf == null) ? [] : (
                    m.Animal___1.in_Animal_ParentOf
                    .collect{entry -> entry.outV.next()}
                    .collectMany{
                        entry -> entry.out_Entity_Related
                            .collect{edge -> edge.inV.next()}
                    }
                    .findAll{entry -> ['Animal'].contains(entry['@class'])}
                    .collectMany{
                        entry -> entry.out_Animal_OfSpecies
                            .collect{edge -> edge.inV.next()}
                    }
                    .collect{entry -> entry.name}
                ))
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST  # Type coercion not implemented for Cypher

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_coercion_on_union_within_fold_scope(self) -> None:
        test_data = test_input_data.coercion_on_union_within_fold_scope()

        expected_match = """
            SELECT
                $Animal___1___out_Animal_ImportantEvent.name AS `birth_events`,
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___out_Animal_ImportantEvent =
                   Animal___1.out("Animal_ImportantEvent")[(@this INSTANCEOF 'BirthEvent')].asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                birth_events: (
                    (m.Animal___1.out_Animal_ImportantEvent == null) ? [] : (
                        m.Animal___1.out_Animal_ImportantEvent
                         .collect{entry -> entry.inV.next()}
                         .findAll{entry -> ['BirthEvent'].contains(entry['@class'])}
                         .collect{entry -> entry.name}
                    )
                ),
                name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST  # Type coercion not implemented for Cypher

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_coercion_filters_and_multiple_outputs_within_fold_scope(self) -> None:
        test_data = test_input_data.coercion_filters_and_multiple_outputs_within_fold_scope()

        expected_match = """
            SELECT
                Animal___1.name AS `name`,
                $Animal___1___out_Entity_Related.name AS `related_animals`,
                $Animal___1___out_Entity_Related.birthday.format("yyyy-MM-dd")
                    AS `related_birthdays`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            )
            LET
                $Animal___1___out_Entity_Related =
                    Animal___1.out("Entity_Related")[(
                        (@this INSTANCEOF 'Animal') AND
                        ((name LIKE ('%' + ({substring} + '%'))) AND
                        (birthday <= date({latest}, "yyyy-MM-dd"))))].asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name,
                related_animals: (
                    (m.Animal___1.out_Entity_Related == null) ? [] : (
                        m.Animal___1.out_Entity_Related
                         .collect{entry -> entry.inV.next()}
                         .findAll{entry -> (
                            (['Animal'].contains(entry['@class']) &&
                             entry.name.contains($substring)) &&
                             (entry.birthday <= Date.parse("yyyy-MM-dd", $latest)))}
                         .collect{entry -> entry.name}
                    )
                ),
                related_birthdays: (
                    (m.Animal___1.out_Entity_Related == null) ? [] : (
                        m.Animal___1.out_Entity_Related
                         .collect{entry -> entry.inV.next()}
                         .findAll{entry -> (
                            (['Animal'].contains(entry['@class']) &&
                             entry.name.contains($substring)) &&
                             (entry.birthday <= Date.parse("yyyy-MM-dd", $latest)))}
                         .collect{entry -> entry.birthday.format("yyyy-MM-dd")}
                    )
                )
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST  # Type coercion not implemented for Cypher

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_coercion_filters_and_multiple_outputs_within_fold_traversal(self) -> None:
        test_data = test_input_data.coercion_filters_and_multiple_outputs_within_fold_traversal()

        expected_match = """
            SELECT
                Animal___1.name AS `name`,
                $Animal___1___in_Animal_ParentOf.name AS `related_animals`,
                $Animal___1___in_Animal_ParentOf.birthday.format("yyyy-MM-dd")
                    AS `related_birthdays`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            ) LET
                $Animal___1___in_Animal_ParentOf =
                    Animal___1
                        .in("Animal_ParentOf")
                        .out("Entity_Related")[(
                            (@this INSTANCEOF 'Animal') AND
                            ((name LIKE ('%' + ({substring} + '%'))) AND
                            (birthday <= date({latest}, "yyyy-MM-dd"))))].asList()
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name,
                related_animals: (
                    (m.Animal___1.in_Animal_ParentOf == null) ? [] : (
                         m.Animal___1.in_Animal_ParentOf
                             .collect{entry -> entry.outV.next()}
                             .collectMany{
                                 entry -> entry.out_Entity_Related
                                     .collect{edge -> edge.inV.next()}
                             }
                             .findAll{entry -> (
                                  (['Animal'].contains(entry['@class']) &&
                                  entry.name.contains($substring)) &&
                                  (entry.birthday <= Date.parse("yyyy-MM-dd", $latest)))}
                             .collect{entry -> entry.name}
                    )
                ),
                related_birthdays: (
                    (m.Animal___1.in_Animal_ParentOf == null) ? [] : (
                         m.Animal___1.in_Animal_ParentOf
                             .collect{entry -> entry.outV.next()}
                             .collectMany{
                                 entry -> entry.out_Entity_Related
                                     .collect{edge -> edge.inV.next()}
                             }
                             .findAll{entry -> (
                                  (['Animal'].contains(entry['@class']) &&
                                  entry.name.contains($substring)) &&
                                  (entry.birthday <= Date.parse("yyyy-MM-dd", $latest)))}
                             .collect{entry -> entry.birthday.format("yyyy-MM-dd")}
                    )
                )
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST  # Type coercion not implemented for Cypher

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_output_count_in_fold_scope(self) -> None:
        test_data = test_input_data.output_count_in_fold_scope()

        expected_match = """
            SELECT
                $Animal___1___out_Animal_ParentOf.name AS `child_names`,
                Animal___1.name AS `name`,
                $Animal___1___out_Animal_ParentOf.size() AS `number_of_children`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            )
            LET
                $Animal___1___out_Animal_ParentOf = Animal___1.out("Animal_ParentOf").asList()
        """
        expected_gremlin = NotImplementedError
        expected_mssql = NotImplementedError
        expected_postgresql = """
            SELECT
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[]) AS child_names,
                "Animal_1".name AS name,
                folded_subquery_1.fold_output__x_count AS number_of_children
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".name) AS fold_output_name,
                    coalesce(count(*), 0) AS fold_output__x_count
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_2".uuid = "Animal_3".parent
                GROUP BY "Animal_2".uuid
              ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
              """

        expected_cypher = NotImplementedError

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_filter_count_with_runtime_parameter_in_fold_scope(self) -> None:
        test_data = test_input_data.filter_count_with_runtime_parameter_in_fold_scope()

        expected_match = """
            SELECT
                $Animal___1___out_Animal_ParentOf.name AS `child_names`,
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            )
            LET
                $Animal___1___out_Animal_ParentOf = Animal___1.out("Animal_ParentOf").asList()
            WHERE
                ($Animal___1___out_Animal_ParentOf.size() >= {min_children})
        """
        expected_gremlin = NotImplementedError

        expected_mssql = NotImplementedError

        expected_postgresql = """
            SELECT
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[]) AS child_names,
                "Animal_1".name AS name
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".name) AS fold_output_name,
                    coalesce(count(*), 0) AS fold_output__x_count
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_2".uuid = "Animal_3".parent
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
            WHERE folded_subquery_1.fold_output__x_count >= :min_children
        """

        expected_cypher = NotImplementedError

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_filter_field_with_tagged_optional_parameter_in_fold_scope(self) -> None:
        test_data = test_input_data.filter_field_with_tagged_optional_parameter_in_fold_scope()

        expected_match = """
            SELECT
                $Animal___1___in_Animal_ParentOf.name AS `children_with_higher_net_worth`,
                Animal___1.name AS `name`
            FROM  (
                MATCH  {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    optional: true,
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            LET
                $Animal___1___in_Animal_ParentOf =
                    Animal___1.in("Animal_ParentOf")[((
                        $matched.Animal__out_Animal_ParentOf___1 IS null) OR
                        (net_worth >= $matched.Animal__out_Animal_ParentOf___1.net_worth
                    ))].asList()
            WHERE (
                ((Animal___1.out_Animal_ParentOf IS null) OR
                (Animal___1.out_Animal_ParentOf.size() = 0)) OR
                (Animal__out_Animal_ParentOf___1 IS NOT null)
            )
        """

        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
            .ifThenElse{
                it.out_Animal_ParentOf == null
            }{
                null
            }{
                it.out('Animal_ParentOf')
            }.as('Animal__out_Animal_ParentOf___1')
            .optional('Animal___1').as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                children_with_higher_net_worth: ((
                    m.Animal___2.in_Animal_ParentOf == null) ? [] : (
                        m.Animal___2.in_Animal_ParentOf.collect{
                            entry -> entry.outV.next()
                        }.findAll{
                            entry -> ((m.Animal__out_Animal_ParentOf___1 == null) ||
                                (entry.net_worth >= m.Animal__out_Animal_ParentOf___1.net_worth))
                        }.collect{entry -> entry.name})), name: m.Animal___1.name
                ])
            }
        """

        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            WHERE (
                (Animal__out_Animal_ParentOf___1 IS null) OR
                (Animal__in_Animal_ParentOf___2.net_worth >=
                Animal__out_Animal_ParentOf___1.net_worth))
            WITH
                Animal___1 AS Animal___1,
                Animal__out_Animal_ParentOf___1 AS Animal__out_Animal_ParentOf___1,
                collect(Animal__in_Animal_ParentOf___1) AS collected_Animal__in_Animal_ParentOf___1
            RETURN
                [x IN collected_Animal__in_Animal_ParentOf___1 | x.name]
                AS `children_with_higher_net_worth`,
                Animal___1.name AS `name`
        """

        expected_sql = NotImplementedError

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_filter_count_with_tagged_optional_parameter_in_fold_scope(self) -> None:
        test_data = test_input_data.filter_count_with_tagged_optional_parameter_in_fold_scope()

        expected_match = """
            SELECT
                $Animal___1___out_Animal_ParentOf.name AS `child_names`,
                Animal___1.name AS `name`
            FROM  (
                MATCH  {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_OfSpecies') {{
                    optional: true,
                    as: Animal__out_Animal_OfSpecies___1
                }}
                RETURN $matches
            )
            LET
                $Animal___1___out_Animal_ParentOf = Animal___1.out("Animal_ParentOf").asList()
            WHERE (
                (
                    ($matched.Animal__out_Animal_OfSpecies___1 IS null) OR
                    ($Animal___1___out_Animal_ParentOf.size() >=
                    Animal__out_Animal_OfSpecies___1.limbs)
                ) AND (
                    ((Animal___1.out_Animal_OfSpecies IS null) OR
                    (Animal___1.out_Animal_OfSpecies.size() = 0)) OR
                    (Animal__out_Animal_OfSpecies___1 IS NOT null)
                )
            )
        """
        expected_gremlin = NotImplementedError
        expected_mssql = NotImplementedError
        expected_postgresql = """
            SELECT
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[]) AS child_names,
                "Animal_1".name AS name
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN schema_1."Species" AS "Species_1"
            ON "Animal_1".species = "Species_1".uuid
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".name) AS fold_output_name,
                    coalesce(count(*), 0) AS fold_output__x_count
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_2".uuid = "Animal_3".parent
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
            WHERE
                "Species_1".uuid IS NULL OR
                "Species_1".limbs <= folded_subquery_1.fold_output__x_count
        """

        expected_cypher = NotImplementedError  # _x_count not implemented for Cypher

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_filter_count_with_tagged_parameter_in_fold_scope(self) -> None:
        test_data = test_input_data.filter_count_with_tagged_parameter_in_fold_scope()

        expected_match = """
            SELECT
                $Animal___1___out_Animal_ParentOf.name AS `child_names`,
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_OfSpecies') {{
                    class: Species,
                    as: Animal__out_Animal_OfSpecies___1
                }}
                RETURN $matches
            )
            LET
                $Animal___1___out_Animal_ParentOf = Animal___1.out("Animal_ParentOf").asList()
            WHERE
                ($Animal___1___out_Animal_ParentOf.size() >= Animal__out_Animal_OfSpecies___1.limbs)
        """
        expected_gremlin = NotImplementedError
        expected_mssql = NotImplementedError
        expected_postgresql = """
            SELECT
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[]) AS child_names,
                "Animal_1".name AS name
            FROM schema_1."Animal" AS "Animal_1"
            JOIN schema_1."Species" AS "Species_1"
            ON "Animal_1".species = "Species_1".uuid
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    array_agg("Animal_3".name) AS fold_output_name,
                    coalesce(count(*), 0) AS fold_output__x_count
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_2".uuid = "Animal_3".parent
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
            WHERE "Species_1".limbs <= folded_subquery_1.fold_output__x_count
        """
        expected_cypher = NotImplementedError  # _x_count not implemented for Cypher

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_filter_count_and_other_filters_in_fold_scope(self) -> None:
        test_data = test_input_data.filter_count_and_other_filters_in_fold_scope()

        expected_match = """
            SELECT
                Animal___1.name AS `name`,
                $Animal___1___out_Animal_ParentOf.size() AS `number_of_children`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            )
            LET
                $Animal___1___out_Animal_ParentOf =
                    Animal___1.out("Animal_ParentOf")[(alias CONTAINS {expected_alias})].asList()
            WHERE
                ($Animal___1___out_Animal_ParentOf.size() >= {min_children})
        """
        expected_gremlin = NotImplementedError
        expected_sql = NotImplementedError
        expected_cypher = NotImplementedError

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_multiple_filters_on_count(self) -> None:
        test_data = test_input_data.multiple_filters_on_count()

        expected_match = """
            SELECT
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            )
            LET
                $Animal___1___out_Animal_ParentOf =
                    Animal___1.out("Animal_ParentOf").asList() ,
                $Animal___1___out_Entity_Related =
                    Animal___1.out("Entity_Related").asList()
            WHERE
                (
                    ($Animal___1___out_Animal_ParentOf.size() >= {min_children}) AND
                    ($Animal___1___out_Entity_Related.size() >= {min_related})
                )
        """
        expected_gremlin = NotImplementedError
        expected_mssql = NotImplementedError
        expected_postgresql = """
            SELECT
                "Animal_1".name AS name
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_2".uuid AS uuid,
                    coalesce(count(*), 0) AS fold_output__x_count
                FROM schema_1."Animal" AS "Animal_2"
                JOIN schema_1."Animal" AS "Animal_3"
                ON "Animal_2".uuid = "Animal_3".parent
                GROUP BY "Animal_2".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
            LEFT OUTER JOIN (
                SELECT
                    "Animal_4".uuid AS uuid,
                    coalesce(count(*), 0) AS fold_output__x_count
                FROM schema_1."Animal" AS "Animal_4"
                JOIN schema_1."Entity" AS "Entity_1"
                ON "Animal_4".related_entity = "Entity_1".uuid
                GROUP BY "Animal_4".uuid
            ) AS folded_subquery_2
            ON "Animal_1".uuid = folded_subquery_2.uuid
            WHERE
                folded_subquery_1.fold_output__x_count >= :min_children AND
                folded_subquery_2.fold_output__x_count >= :min_related
        """
        expected_cypher = NotImplementedError

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_filter_on_count_with_nested_filter(self) -> None:
        test_data = test_input_data.filter_on_count_with_nested_filter()

        expected_match = """
            SELECT
                Species___1.name AS `name`
            FROM (
                MATCH {{
                    class: Species,
                    as: Species___1
                }}
                RETURN $matches
            )
            LET
                $Species___1___in_Animal_OfSpecies = Species___1.in("Animal_OfSpecies")\
.out("Animal_LivesIn")[(name = {location})].asList()
            WHERE
                ($Species___1___in_Animal_OfSpecies.size() = {num_animals})
        """
        expected_gremlin = NotImplementedError
        expected_mssql = NotImplementedError
        expected_cypher = NotImplementedError
        expected_postgresql = """
            SELECT
                "Species_1".name AS name
            FROM schema_1."Species" AS "Species_1"
            LEFT OUTER JOIN (
                SELECT
                    "Species_2".uuid AS uuid,
                    coalesce(count(*), 0) AS fold_output__x_count
                FROM schema_1."Species" AS "Species_2"
                JOIN schema_1."Animal" AS "Animal_1"
                ON "Species_2".uuid = "Animal_1".species
                JOIN schema_1."Location" AS "Location_1"
                ON "Animal_1".lives_in = "Location_1".uuid
                WHERE "Location_1".name = :location
                GROUP BY "Species_2".uuid
            ) AS folded_subquery_1
            ON "Species_1".uuid = folded_subquery_1.uuid
            WHERE folded_subquery_1.fold_output__x_count = :num_animals
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_optional_and_traverse(self) -> None:
        test_data = test_input_data.optional_and_traverse()

        expected_match = """
            SELECT EXPAND($result)
            LET
                $optional__0 = (
                    SELECT
                        Animal___1.name AS `name`
                    FROM (
                        MATCH {{
                            class: Animal,
                            where: ((
                                (in_Animal_ParentOf IS null)
                                OR
                                (in_Animal_ParentOf.size() = 0)
                            )),
                            as: Animal___1
                        }}
                        RETURN $matches
                    )
                ),
                $optional__1 = (
                    SELECT
                        Animal__in_Animal_ParentOf___1.name AS `child_name`,
                        Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name
                            AS `grandchild_name`,
                        Animal___1.name AS `name`
                    FROM (
                        MATCH {{
                            class: Animal,
                            as: Animal___1
                        }}.in('Animal_ParentOf') {{
                            class: Animal,
                            as: Animal__in_Animal_ParentOf___1
                        }}.in('Animal_ParentOf') {{
                            class: Animal,
                            as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
                        }}
                        RETURN $matches
                    )
                ),
                $result = UNIONALL($optional__0, $optional__1)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{it.in('Animal_ParentOf')}
                    .as('Animal__in_Animal_ParentOf__in_Animal_ParentOf___1')
                .back('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_name: (
                    (m.Animal__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf___1.name : null
                ),
                grandchild_name: (
                    (m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name : null
                ),
                name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS child_name,
                [Animal_2].name AS grandchild_name,
                [Animal_3].name AS name
            FROM
                db_1.schema_1.[Animal] AS [Animal_3]
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_1]
                    ON [Animal_3].parent = [Animal_1].uuid
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].parent = [Animal_2].uuid
            WHERE
                [Animal_2].uuid IS NOT NULL OR [Animal_1].uuid IS NULL
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "Animal_1".name AS child_name,
                "Animal_2".name AS grandchild_name,
                "Animal_3".name AS name
            FROM
                schema_1."Animal" AS "Animal_3"
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_1"
                    ON "Animal_3".parent = "Animal_1".uuid
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".parent = "Animal_2".uuid
            WHERE
                "Animal_2".uuid IS NOT NULL OR "Animal_1".uuid IS NULL
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_optional_and_traverse_after_filter(self) -> None:
        test_data = test_input_data.optional_and_traverse_after_filter()

        expected_match = """
            SELECT EXPAND($result)
            LET
                $optional__0 = (
                    SELECT
                        Animal___1.name AS `name`
                    FROM (
                        MATCH {{
                            class: Animal,
                            where: ((
                                (name LIKE ('%' + ({wanted} + '%')))
                                AND
                                (
                                    (in_Animal_ParentOf IS null)
                                    OR
                                    (in_Animal_ParentOf.size() = 0)
                                )
                            )),
                            as: Animal___1
                        }}
                        RETURN $matches
                    )
                ),
                $optional__1 = (
                    SELECT
                        Animal__in_Animal_ParentOf___1.name AS `child_name`,
                        Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name
                            AS `grandchild_name`,
                        Animal___1.name AS `name`
                    FROM (
                        MATCH {{
                            class: Animal,
                            where: ((name LIKE ('%' + ({wanted} + '%')))),
                            as: Animal___1
                        }}.in('Animal_ParentOf') {{
                            as: Animal__in_Animal_ParentOf___1
                        }}.in('Animal_ParentOf') {{
                            as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
                        }}
                        RETURN $matches
                    )
                ),
                $result = UNIONALL($optional__0, $optional__1)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> it.name.contains($wanted)}
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{it.in('Animal_ParentOf')}
                    .as('Animal__in_Animal_ParentOf__in_Animal_ParentOf___1')
                .back('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_name: (
                    (m.Animal__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf___1.name : null
                ),
                grandchild_name: (
                    (m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name : null
                ),
                name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS child_name,
                [Animal_2].name AS grandchild_name,
                [Animal_3].name AS name
            FROM
                db_1.schema_1.[Animal] AS [Animal_3]
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_1]
                    ON [Animal_3].parent = [Animal_1].uuid
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].parent = [Animal_2].uuid
            WHERE (
                [Animal_3].name LIKE '%' + :wanted + '%'
            ) AND (
                [Animal_2].uuid IS NOT NULL OR
                [Animal_1].uuid IS NULL
            )
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "Animal_1".name AS child_name,
                "Animal_2".name AS grandchild_name,
                "Animal_3".name AS name
            FROM
                schema_1."Animal" AS "Animal_3"
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_1"
                    ON "Animal_3".parent = "Animal_1".uuid
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".parent = "Animal_2".uuid
            WHERE (
                "Animal_3".name LIKE '%%' || :wanted || '%%'
            ) AND (
                "Animal_2".uuid IS NOT NULL OR
                "Animal_1".uuid IS NULL
            )
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_optional_and_deep_traverse(self) -> None:
        test_data = test_input_data.optional_and_deep_traverse()

        expected_match = """
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal___1.name AS `animal_name`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((
                            (in_Animal_ParentOf IS null)
                            OR
                            (in_Animal_ParentOf.size() = 0)
                        )),
                        as: Animal___1
                    }}
                    RETURN $matches
                )
            ),
            $optional__1 = (
                SELECT
                    Animal___1.name AS `animal_name`,
                    Animal__in_Animal_ParentOf___1.name AS `child_name`,
                    Animal__in_Animal_ParentOf__out_Animal_ParentOf___1.name
                        AS `spouse_and_self_name`,
                    Animal__in_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1.name
                        AS `spouse_species`
                FROM (
                    MATCH {{
                        class: Animal,
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf___1
                    }}.out('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf__out_Animal_ParentOf___1
                    }}.out('Animal_OfSpecies') {{
                        class: Species,
                        as: Animal__in_Animal_ParentOf__out_Animal_ParentOf
                            __out_Animal_OfSpecies___1
                    }}
                    RETURN $matches
                )
            ),
            $result = UNIONALL($optional__0, $optional__1)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{it.out('Animal_ParentOf')}
                    .as('Animal__in_Animal_ParentOf__out_Animal_ParentOf___1')
                        .ifThenElse{it == null}{null}{it.out('Animal_OfSpecies')}
                        .as('Animal__in_Animal_ParentOf__out_Animal_ParentOf
                             __out_Animal_OfSpecies___1')
                    .back('Animal__in_Animal_ParentOf__out_Animal_ParentOf___1')
                .back('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_name: (
                    (m.Animal__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf___1.name : null
                ),
                spouse_and_self_name: (
                    (m.Animal__in_Animal_ParentOf__out_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf__out_Animal_ParentOf___1.name : null
                ),
                spouse_species: (
                    (m.Animal__in_Animal_ParentOf__out_Animal_ParentOf
                       __out_Animal_OfSpecies___1 != null) ?
                        m.Animal__in_Animal_ParentOf__out_Animal_ParentOf
                          __out_Animal_OfSpecies___1.name
                        : null
                )
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                [Animal_2].name AS child_name,
                [Animal_3].name AS spouse_and_self_name,
                [Species_1].name AS spouse_species
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].parent = [Animal_2].uuid
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_3]
                    ON [Animal_2].uuid = [Animal_3].parent
                LEFT OUTER JOIN db_1.schema_1.[Species] AS [Species_1]
                    ON [Animal_3].species = [Species_1].uuid
            WHERE (
                [Animal_3].parent IS NOT NULL OR
                [Animal_2].uuid IS NULL
            ) AND (
                [Species_1].uuid IS NOT NULL OR
                [Animal_3].parent IS NULL
            )
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                "Animal_2".name AS child_name,
                "Animal_3".name AS spouse_and_self_name,
                "Species_1".name AS spouse_species
            FROM
                schema_1."Animal" AS "Animal_1"
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".parent = "Animal_2".uuid
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_3"
                    ON "Animal_2".uuid = "Animal_3".parent
                LEFT OUTER JOIN schema_1."Species" AS "Species_1"
                    ON "Animal_3".species = "Species_1".uuid
            WHERE (
                "Animal_3".parent IS NOT NULL OR
                "Animal_2".uuid IS NULL
            ) AND (
                "Species_1".uuid IS NOT NULL OR
                "Animal_3".parent IS NULL
            )
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_traverse_and_optional_and_traverse(self) -> None:
        test_data = test_input_data.traverse_and_optional_and_traverse()

        expected_match = """
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal___1.name AS `animal_name`,
                    Animal__in_Animal_ParentOf___1.name AS `child_name`
                FROM (
                    MATCH {{
                        where: ((@this INSTANCEOF 'Animal')),
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        class: Animal,
                        where: ((
                            (out_Animal_ParentOf IS null)
                            OR
                            (out_Animal_ParentOf.size() = 0)
                        )),
                        as: Animal__in_Animal_ParentOf___1
                    }}
                    RETURN $matches
                )
            ),
            $optional__1 = (
                SELECT
                    Animal___1.name AS `animal_name`,
                    Animal__in_Animal_ParentOf___1.name AS `child_name`,
                    Animal__in_Animal_ParentOf__out_Animal_ParentOf___1.name
                        AS `spouse_and_self_name`,
                    Animal__in_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1.name
                        AS `spouse_and_self_species`
                FROM (
                    MATCH {{
                        class: Animal,
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf___1
                    }}.out('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf__out_Animal_ParentOf___1
                    }}.out('Animal_OfSpecies') {{
                        class: Species,
                        as: Animal__in_Animal_ParentOf__out_Animal_ParentOf
                            __out_Animal_OfSpecies___1
                    }}
                    RETURN $matches
                )
            ),
            $result = UNIONALL($optional__0, $optional__1)
        """
        expected_gremlin = """
            g.V('@class',
                'Animal')
            .as('Animal___1')
                .in('Animal_ParentOf')
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it.out_Animal_ParentOf == null}{null}{it.out('Animal_ParentOf')}
                    .as('Animal__in_Animal_ParentOf__out_Animal_ParentOf___1')
                        .ifThenElse{it == null}{null}{it.out('Animal_OfSpecies')}
                        .as('Animal__in_Animal_ParentOf__out_Animal_ParentOf
                             __out_Animal_OfSpecies___1')
                    .back('Animal__in_Animal_ParentOf__out_Animal_ParentOf___1')
                .optional('Animal__in_Animal_ParentOf___1')
                .as('Animal__in_Animal_ParentOf___2')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_name: m.Animal__in_Animal_ParentOf___1.name,
                spouse_and_self_name: (
                    (m.Animal__in_Animal_ParentOf__out_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf__out_Animal_ParentOf___1.name : null
                ),
                spouse_and_self_species: (
                    (m.Animal__in_Animal_ParentOf__out_Animal_ParentOf
                        __out_Animal_OfSpecies___1 != null) ?
                        m.Animal__in_Animal_ParentOf__out_Animal_ParentOf
                          __out_Animal_OfSpecies___1.name
                        : null
                )
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                [Animal_2].name AS child_name,
                [Animal_3].name AS spouse_and_self_name,
                [Species_1].name AS spouse_and_self_species
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].parent = [Animal_2].uuid
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_3]
                    ON [Animal_2].uuid = [Animal_3].parent
                LEFT OUTER JOIN db_1.schema_1.[Species] AS [Species_1]
                    ON [Animal_3].species = [Species_1].uuid
            WHERE
                [Species_1].uuid IS NOT NULL OR [Animal_3].parent IS NULL

        """
        expected_cypher = SKIP_TEST
        expeceted_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                "Animal_2".name AS child_name,
                "Animal_3".name AS spouse_and_self_name,
                "Species_1".name AS spouse_and_self_species
            FROM
                schema_1."Animal" AS "Animal_1"
                JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".parent = "Animal_2".uuid
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_3"
                    ON "Animal_2".uuid = "Animal_3".parent
                LEFT OUTER JOIN schema_1."Species" AS "Species_1"
                    ON "Animal_3".species = "Species_1".uuid
                WHERE
                    "Species_1".uuid IS NOT NULL OR "Animal_3".parent IS NULL
"""

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expeceted_postgresql,
        )

    def test_multiple_optional_traversals_with_starting_filter(self) -> None:
        test_data = test_input_data.multiple_optional_traversals_with_starting_filter()

        expected_match = """
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal___1.name AS `animal_name`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((
                            (
                                (name LIKE ('%' + ({wanted} + '%')))
                                AND
                                (
                                    (in_Animal_ParentOf IS null)
                                    OR
                                    (in_Animal_ParentOf.size() = 0)
                                )
                            )
                            AND
                            (
                                (out_Animal_ParentOf IS null)
                                OR
                                (out_Animal_ParentOf.size() = 0)
                            )
                        )),
                        as: Animal___1
                    }}
                    RETURN $matches
                )
            ),
            $optional__1 = (
                SELECT
                    Animal___1.name AS `animal_name`,
                    Animal__out_Animal_ParentOf___1.name AS `parent_name`,
                    Animal__out_Animal_ParentOf__out_Animal_OfSpecies___1.name AS `parent_species`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((
                            (name LIKE ('%' + ({wanted} + '%')))
                            AND
                            (
                                (in_Animal_ParentOf IS null)
                                OR
                                (in_Animal_ParentOf.size() = 0)
                            )
                        )),
                        as: Animal___1
                    }} ,
                    {{
                        class: Animal,
                        as: Animal___1
                    }}.out('Animal_ParentOf') {{
                        as: Animal__out_Animal_ParentOf___1
                    }}.out('Animal_OfSpecies') {{
                        as: Animal__out_Animal_ParentOf__out_Animal_OfSpecies___1
                    }}
                    RETURN $matches
                )
            ),
            $optional__2 = (
                SELECT
                    Animal___1.name AS `animal_name`,
                    Animal__in_Animal_ParentOf___1.name AS `child_name`,
                    Animal__in_Animal_ParentOf__out_Animal_ParentOf___1.name
                        AS `spouse_and_self_name`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((
                            (name LIKE ('%' + ({wanted} + '%')))
                            AND
                            (
                                (out_Animal_ParentOf IS null)
                                OR
                                (out_Animal_ParentOf.size() = 0)
                            )
                        )),
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        as: Animal__in_Animal_ParentOf___1
                    }}.out('Animal_ParentOf') {{
                        as: Animal__in_Animal_ParentOf__out_Animal_ParentOf___1
                    }}
                    RETURN $matches
                )
            ),
            $optional__3 = (
                SELECT
                    Animal___1.name AS `animal_name`,
                    Animal__in_Animal_ParentOf___1.name AS `child_name`,
                    Animal__out_Animal_ParentOf___1.name AS `parent_name`,
                    Animal__out_Animal_ParentOf__out_Animal_OfSpecies___1.name AS `parent_species`,
                    Animal__in_Animal_ParentOf__out_Animal_ParentOf___1.name
                        AS `spouse_and_self_name`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((name LIKE ('%' + ({wanted} + '%')))),
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        as: Animal__in_Animal_ParentOf___1
                    }}.out('Animal_ParentOf') {{
                        as: Animal__in_Animal_ParentOf__out_Animal_ParentOf___1
                    }} ,
                    {{
                        class: Animal,
                        as: Animal___1
                    }}.out('Animal_ParentOf') {{
                        as: Animal__out_Animal_ParentOf___1
                    }}.out('Animal_OfSpecies') {{
                        as: Animal__out_Animal_ParentOf__out_Animal_OfSpecies___1
                    }}
                    RETURN $matches
                )
            ),
            $result = UNIONALL($optional__0, $optional__1, $optional__2, $optional__3)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> it.name.contains($wanted)}
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{it.out('Animal_ParentOf')}
                    .as('Animal__in_Animal_ParentOf__out_Animal_ParentOf___1')
                .back('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
                .ifThenElse{it.out_Animal_ParentOf == null}{null}{it.out('Animal_ParentOf')}
                .as('Animal__out_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{it.out('Animal_OfSpecies')}
                    .as('Animal__out_Animal_ParentOf__out_Animal_OfSpecies___1')
                .back('Animal__out_Animal_ParentOf___1')
            .optional('Animal___2')
            .as('Animal___3')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_name: (
                    (m.Animal__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf___1.name : null
                ),
                parent_name: (
                    (m.Animal__out_Animal_ParentOf___1 != null) ?
                        m.Animal__out_Animal_ParentOf___1.name : null
                ),
                parent_species: (
                    (m.Animal__out_Animal_ParentOf__out_Animal_OfSpecies___1 != null) ?
                        m.Animal__out_Animal_ParentOf__out_Animal_OfSpecies___1.name : null
                ),
                spouse_and_self_name: (
                    (m.Animal__in_Animal_ParentOf__out_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf__out_Animal_ParentOf___1.name : null
                )
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                [Animal_2].name AS child_name,
                [Animal_3].name AS parent_name,
                [Species_1].name AS parent_species,
                [Animal_4].name AS spouse_and_self_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].parent = [Animal_2].uuid
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_4]
                    ON [Animal_2].uuid = [Animal_4].parent
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_3]
                    ON [Animal_1].uuid = [Animal_3].parent
                LEFT OUTER JOIN db_1.schema_1.[Species] AS [Species_1]
                    ON [Animal_3].species = [Species_1].uuid
            WHERE (
                [Animal_1].name LIKE '%' + :wanted + '%'
            ) AND (
                [Animal_4].parent IS NOT NULL OR
                [Animal_2].uuid IS NULL
            ) AND (
                [Species_1].uuid IS NOT NULL OR
                [Animal_3].parent IS NULL
            )
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                "Animal_2".name AS child_name,
                "Animal_3".name AS parent_name,
                "Species_1".name AS parent_species,
                "Animal_4".name AS spouse_and_self_name
            FROM
                schema_1."Animal" AS "Animal_1"
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".parent = "Animal_2".uuid
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_4"
                    ON "Animal_2".uuid = "Animal_4".parent
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_3"
                    ON "Animal_1".uuid = "Animal_3".parent
                LEFT OUTER JOIN schema_1."Species" AS "Species_1"
                    ON "Animal_3".species = "Species_1".uuid
            WHERE (
                "Animal_1".name LIKE '%%' || :wanted || '%%'
            ) AND (
                "Animal_4".parent IS NOT NULL OR
                "Animal_2".uuid IS NULL
            ) AND (
                "Species_1".uuid IS NOT NULL OR
                "Animal_3".parent IS NULL
            )
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_optional_traversal_and_optional_without_traversal(self) -> None:
        test_data = test_input_data.optional_traversal_and_optional_without_traversal()

        expected_match = """
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal___1.name AS `animal_name`,
                    if(
                        eval("(Animal__in_Animal_ParentOf___1 IS NOT null)"),
                        Animal__in_Animal_ParentOf___1.name,
                        null
                    ) AS `child_name`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((
                            (name LIKE ('%' + ({wanted} + '%')))
                            AND
                            (
                                (out_Animal_ParentOf IS null)
                                OR
                                (out_Animal_ParentOf.size() = 0)
                            )
                        )),
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        optional: true,
                        as: Animal__in_Animal_ParentOf___1
                    }}
                    RETURN $matches
                )
                WHERE (
                    (
                        (Animal___1.in_Animal_ParentOf IS null)
                        OR
                        (Animal___1.in_Animal_ParentOf.size() = 0)
                    )
                    OR
                    (Animal__in_Animal_ParentOf___1 IS NOT null)
                )
            ),
            $optional__1 = (
                SELECT
                    Animal___1.name AS `animal_name`,
                    if(
                        eval("(Animal__in_Animal_ParentOf___1 IS NOT null)"),
                        Animal__in_Animal_ParentOf___1.name,
                        null
                    ) AS `child_name`,
                    Animal__out_Animal_ParentOf___1.name AS `parent_name`,
                    Animal__out_Animal_ParentOf__out_Animal_OfSpecies___1.name
                        AS `parent_species`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((name LIKE ('%' + ({wanted} + '%')))),
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        optional: true,
                        as: Animal__in_Animal_ParentOf___1
                    }} ,
                    {{
                        class: Animal,
                        as: Animal___1
                    }}.out('Animal_ParentOf') {{
                        as: Animal__out_Animal_ParentOf___1
                    }}.out('Animal_OfSpecies') {{
                        as: Animal__out_Animal_ParentOf__out_Animal_OfSpecies___1
                    }}
                    RETURN $matches
                )
                WHERE (
                    (
                        (Animal___1.in_Animal_ParentOf IS null)
                        OR
                        (Animal___1.in_Animal_ParentOf.size() = 0)
                    )
                    OR
                    (Animal__in_Animal_ParentOf___1 IS NOT null)
                )
            ),
            $result = UNIONALL($optional__0, $optional__1)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m -> it.name.contains($wanted)}
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
                .ifThenElse{it.out_Animal_ParentOf == null}{null}{it.out('Animal_ParentOf')}
                .as('Animal__out_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{it.out('Animal_OfSpecies')}
                    .as('Animal__out_Animal_ParentOf__out_Animal_OfSpecies___1')
                .back('Animal__out_Animal_ParentOf___1')
            .optional('Animal___2')
            .as('Animal___3')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_name: (
                    (m.Animal__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf___1.name : null
                ),
                parent_name: (
                    (m.Animal__out_Animal_ParentOf___1 != null) ?
                        m.Animal__out_Animal_ParentOf___1.name : null
                ),
                parent_species: (
                    (m.Animal__out_Animal_ParentOf__out_Animal_OfSpecies___1 != null) ?
                        m.Animal__out_Animal_ParentOf__out_Animal_OfSpecies___1.name : null
                )
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                [Animal_2].name AS child_name,
                [Animal_3].name AS parent_name,
                [Species_1].name AS parent_species
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].parent = [Animal_2].uuid
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_3]
                    ON [Animal_1].uuid = [Animal_3].parent
                LEFT OUTER JOIN db_1.schema_1.[Species] AS [Species_1]
                    ON [Animal_3].species = [Species_1].uuid
            WHERE (
                [Animal_1].name LIKE '%' + :wanted + '%'
            ) AND (
                [Species_1].uuid IS NOT NULL OR
                [Animal_3].parent IS NULL
            )
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                "Animal_2".name AS child_name,
                "Animal_3".name AS parent_name,
                "Species_1".name AS parent_species
            FROM
                schema_1."Animal" AS "Animal_1"
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".parent = "Animal_2".uuid
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_3"
                    ON "Animal_1".uuid = "Animal_3".parent
                LEFT OUTER JOIN schema_1."Species" AS "Species_1"
                    ON "Animal_3".species = "Species_1".uuid
            WHERE (
                "Animal_1".name LIKE '%%' || :wanted || '%%'
            ) AND (
                "Species_1".uuid IS NOT NULL OR
                "Animal_3".parent IS NULL
            )
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_coercion_on_interface_within_optional_traversal(self) -> None:
        test_data = test_input_data.coercion_on_interface_within_optional_traversal()

        expected_match = """
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal___1.name AS `animal_name`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((
                            (in_Animal_ParentOf IS null)
                            OR
                            (in_Animal_ParentOf.size() = 0)
                        )),
                        as: Animal___1
                    }}
                    RETURN $matches
                )
            ),
            $optional__1 = (
                SELECT
                    Animal___1.name AS `animal_name`,
                    Animal__in_Animal_ParentOf__out_Entity_Related__out_Animal_OfSpecies___1.name
                        AS `related_animal_species`
                FROM (
                    MATCH {{
                        class: Animal,
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf___1
                    }}.out('Entity_Related') {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf__out_Entity_Related___1
                    }}.out('Animal_OfSpecies') {{
                        class: Species,
                        as: Animal__in_Animal_ParentOf__out_Entity_Related
                            __out_Animal_OfSpecies___1
                    }}
                    RETURN $matches
                )
            ),
            $result = UNIONALL($optional__0, $optional__1)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{it.out('Entity_Related')}
                    .filter{it, m -> ((it == null) || ['Animal'].contains(it['@class']))}
                    .as('Animal__in_Animal_ParentOf__out_Entity_Related___1')
                        .ifThenElse{it == null}{null}{it.out('Animal_OfSpecies')}
                        .as('Animal__in_Animal_ParentOf__out_Entity_Related
                             __out_Animal_OfSpecies___1')
                    .back('Animal__in_Animal_ParentOf__out_Entity_Related___1')
                .back('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                related_animal_species: (
                    (m.Animal__in_Animal_ParentOf__out_Entity_Related
                        __out_Animal_OfSpecies___1 != null) ?
                        m.Animal__in_Animal_ParentOf__out_Entity_Related
                            __out_Animal_OfSpecies___1.name : null
                )
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_filter_on_optional_traversal_equality(self) -> None:
        test_data = test_input_data.filter_on_optional_traversal_equality()

        expected_match = """
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal___1.name AS `animal_name`
                FROM (
                    MATCH {{
                        where: ((@this INSTANCEOF 'Animal')),
                        as: Animal___1
                    }}.out('Animal_ParentOf') {{
                        class: Animal,
                        where: ((
                            (out_Animal_ParentOf IS null)
                            OR
                            (out_Animal_ParentOf.size() = 0)
                        )),
                        as: Animal__out_Animal_ParentOf___1
                    }} ,
                    {{
                        as: Animal___1
                    }}.out('Animal_FedAt') {{
                        as: Animal__out_Animal_FedAt___1
                    }}
                    RETURN $matches
                )
            ),
            $optional__1 = (
                SELECT
                    Animal___1.name AS `animal_name`
                FROM (
                    MATCH {{
                        class: Animal,
                        as: Animal___1
                    }}.out('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__out_Animal_ParentOf___1
                    }}.out('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__out_Animal_ParentOf__out_Animal_ParentOf___1
                    }}.out('Animal_FedAt') {{
                        class: FeedingEvent,
                        as: Animal__out_Animal_ParentOf__out_Animal_ParentOf
                            __out_Animal_FedAt___1
                    }} ,
                    {{
                        class: Animal,
                        as: Animal___1
                    }}.out('Animal_FedAt') {{
                        where: ((
                            ($matched.Animal__out_Animal_ParentOf
                                __out_Animal_ParentOf__out_Animal_FedAt___1 IS null)
                            OR
                            (name = $matched.Animal__out_Animal_ParentOf
                                __out_Animal_ParentOf__out_Animal_FedAt___1.name)
                        )),
                        as: Animal__out_Animal_FedAt___1
                    }}
                    RETURN $matches
                )
            ),
            $result = UNIONALL($optional__0, $optional__1)
        """
        expected_gremlin = """
            g.V('@class',
                'Animal')
            .as('Animal___1')
                .out('Animal_ParentOf')
                .as('Animal__out_Animal_ParentOf___1')
                    .ifThenElse{it.out_Animal_ParentOf == null}{null}{it.out('Animal_ParentOf')}
                    .as('Animal__out_Animal_ParentOf__out_Animal_ParentOf___1')
                        .ifThenElse{it == null}{null}{it.out('Animal_FedAt')}
                        .as('Animal__out_Animal_ParentOf__out_Animal_ParentOf
                            __out_Animal_FedAt___1')
                    .back('Animal__out_Animal_ParentOf__out_Animal_ParentOf___1')
                .optional('Animal__out_Animal_ParentOf___1')
                .as('Animal__out_Animal_ParentOf___2')
            .back('Animal___1')
                .out('Animal_FedAt')
                .filter{it, m -> (
                        (m.Animal__out_Animal_ParentOf__out_Animal_ParentOf
                            __out_Animal_FedAt___1 == null)
                        ||
                        (it.name == m.Animal__out_Animal_ParentOf__out_Animal_ParentOf
                            __out_Animal_FedAt___1.name)
                    )
                }
                    .as('Animal__out_Animal_FedAt___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                    animal_name: m.Animal___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_filter_on_optional_traversal_name_or_alias(self) -> None:
        test_data = test_input_data.filter_on_optional_traversal_name_or_alias()

        expected_match = """
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal__out_Animal_ParentOf___1.name AS `parent_name`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((
                            (in_Animal_ParentOf IS null)
                            OR
                            (in_Animal_ParentOf.size() = 0)
                        )),
                        as: Animal___1
                    }} ,
                    {{
                        class: Animal,
                        as: Animal___1
                    }}.out('Animal_ParentOf') {{
                        as: Animal__out_Animal_ParentOf___1
                    }}
                    RETURN $matches
                )
            ),
            $optional__1 = (
                SELECT
                    Animal__out_Animal_ParentOf___1.name AS `parent_name`
                FROM (
                    MATCH {{
                        class: Animal,
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf___1
                    }}.in('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
                    }} ,
                    {{
                        class: Animal,
                        as: Animal___1
                    }}.out('Animal_ParentOf') {{
                        where: ((
                            ($matched.Animal__in_Animal_ParentOf
                                __in_Animal_ParentOf___1 IS null)
                            OR
                            (
                                (name = $matched.Animal__in_Animal_ParentOf
                                    __in_Animal_ParentOf___1.name)
                                OR
                                (alias CONTAINS $matched.Animal__in_Animal_ParentOf
                                __in_Animal_ParentOf___1.name)
                            )
                        )),
                        as: Animal__out_Animal_ParentOf___1
                    }}
                    RETURN $matches
                )
            ),
            $result = UNIONALL($optional__0, $optional__1)
        """
        expected_gremlin = """
            g.V('@class',
                'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{it.in('Animal_ParentOf')}
                    .as('Animal__in_Animal_ParentOf__in_Animal_ParentOf___1')
                .back('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
                .out('Animal_ParentOf')
                .filter{it, m -> (
                        (m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1 == null)
                        || (
                            (it.name == m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name)
                            ||
                            it.alias.contains(m.Animal__in_Animal_ParentOf
                                __in_Animal_ParentOf___1.name)
                        )
                    )}
                    .as('Animal__out_Animal_ParentOf___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                    parent_name: m.Animal__out_Animal_ParentOf___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_complex_optional_traversal_variables(self) -> None:
        test_data = test_input_data.complex_optional_traversal_variables()

        expected_match = """
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal__in_Animal_ParentOf__out_Animal_FedAt___1
                        .event_date.format("yyyy-MM-dd'T'HH:mm:ss") AS `grandchild_fed_at`,
                    if(eval("(Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)"),
                        Animal__out_Animal_ParentOf__out_Animal_FedAt___1
                            .event_date.format("yyyy-MM-dd'T'HH:mm:ss"),
                            null
                    ) AS `parent_fed_at`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((name = {animal_name})),
                        as: Animal___1
                    }}.out('Animal_ParentOf') {{
                        class: Animal,
                        where: ((
                            (in_Animal_ParentOf IS null)
                            OR
                            (in_Animal_ParentOf.size() = 0)
                        )),
                        as: Animal__out_Animal_ParentOf___1
                    }}.out('Animal_FedAt') {{
                        optional: true,
                        as: Animal__out_Animal_ParentOf__out_Animal_FedAt___1
                    }},
                    {{
                        class: Animal,
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        as: Animal__in_Animal_ParentOf___1
                    }}.out('Animal_FedAt') {{
                        where: ((
                            (
                                ($matched.Animal__out_Animal_ParentOf
                                    __out_Animal_FedAt___1 IS null)
                                OR
                                (name = $matched.Animal__out_Animal_ParentOf
                                    __out_Animal_FedAt___1.name)
                            )
                            AND
                            (
                                ($matched.Animal__out_Animal_ParentOf
                                    __out_Animal_FedAt___1 IS null)
                                OR
                                (event_date <= $matched.Animal__out_Animal_ParentOf
                                    __out_Animal_FedAt___1.event_date)
                            )
                        )),
                        as: Animal__in_Animal_ParentOf__out_Animal_FedAt___1
                    }}
                    RETURN $matches
                )
                WHERE (
                    (
                        (Animal__out_Animal_ParentOf___1.out_Animal_FedAt IS null)
                        OR
                        (Animal__out_Animal_ParentOf___1.out_Animal_FedAt.size() = 0)
                    )
                    OR
                    (Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)
                )
            ),
            $optional__1 = (
                SELECT
                    Animal__in_Animal_ParentOf__out_Animal_FedAt___1
                        .event_date.format("yyyy-MM-dd'T'HH:mm:ss") AS `grandchild_fed_at`,
                    Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        .event_date.format("yyyy-MM-dd'T'HH:mm:ss") AS `other_child_fed_at`,
                    if(eval("(Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)"),
                        Animal__out_Animal_ParentOf__out_Animal_FedAt___1
                            .event_date.format("yyyy-MM-dd'T'HH:mm:ss"),
                        null
                    ) AS `parent_fed_at`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((name = {animal_name})),
                        as: Animal___1
                    }}.out('Animal_ParentOf') {{
                        as: Animal__out_Animal_ParentOf___1
                    }}.out('Animal_FedAt') {{
                        optional: true,
                        as: Animal__out_Animal_ParentOf__out_Animal_FedAt___1
                    }} ,
                    {{
                        where: ((@this INSTANCEOF 'Animal')),
                        as: Animal__out_Animal_ParentOf___1
                    }}.in('Animal_ParentOf') {{
                        as: Animal__out_Animal_ParentOf__in_Animal_ParentOf___1
                    }}.out('Animal_FedAt') {{
                        as: Animal__out_Animal_ParentOf__in_Animal_ParentOf
                            __out_Animal_FedAt___1
                    }} ,
                    {{
                        class: Animal,
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        as: Animal__in_Animal_ParentOf___1
                    }}.out('Animal_FedAt') {{
                        where: ((
                            (
                                ($matched.Animal__out_Animal_ParentOf
                                    __out_Animal_FedAt___1 IS null)
                                OR
                                (name = $matched.Animal__out_Animal_ParentOf
                                    __out_Animal_FedAt___1.name)
                            )
                            AND
                            (
                                (
                                    ($matched.Animal__out_Animal_ParentOf
                                        __in_Animal_ParentOf__out_Animal_FedAt___1 IS null)
                                    OR
                                    (event_date >= $matched.Animal__out_Animal_ParentOf
                                        __in_Animal_ParentOf__out_Animal_FedAt___1.event_date)
                                )
                                AND
                                (
                                    ($matched.Animal__out_Animal_ParentOf
                                        __out_Animal_FedAt___1 IS null)
                                    OR
                                    (event_date <= $matched.Animal__out_Animal_ParentOf
                                        __out_Animal_FedAt___1.event_date)
                                )
                            )
                        )),
                        as: Animal__in_Animal_ParentOf__out_Animal_FedAt___1
                    }}
                    RETURN $matches
                )
                WHERE (
                    (
                        (Animal__out_Animal_ParentOf___1.out_Animal_FedAt IS null)
                        OR
                        (Animal__out_Animal_ParentOf___1.out_Animal_FedAt.size() = 0)
                    )
                    OR
                    (Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)
                )
            ),
            $result = UNIONALL($optional__0, $optional__1)
        """

        expected_gremlin = """
           g.V('@class',
               'Animal')
           .filter{it, m -> (it.name == $animal_name)}
           .as('Animal___1')
               .out('Animal_ParentOf')
               .as('Animal__out_Animal_ParentOf___1')
                   .ifThenElse{it.out_Animal_FedAt == null}{null}{it.out('Animal_FedAt')}
                   .as('Animal__out_Animal_ParentOf__out_Animal_FedAt___1')
               .optional('Animal__out_Animal_ParentOf___1')
               .as('Animal__out_Animal_ParentOf___2')
                   .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                   .as('Animal__out_Animal_ParentOf__in_Animal_ParentOf___1')
                       .ifThenElse{it == null}{null}{it.out('Animal_FedAt')}
                       .as('Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1')
                   .back('Animal__out_Animal_ParentOf__in_Animal_ParentOf___1')
               .optional('Animal__out_Animal_ParentOf___2')
               .as('Animal__out_Animal_ParentOf___3')
           .back('Animal___1')
               .in('Animal_ParentOf')
               .as('Animal__in_Animal_ParentOf___1')
                   .out('Animal_FedAt')
                   .filter{it, m -> (
                           (
                               (m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 == null)
                               ||
                               (it.name == m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1.name)
                           )
                           &&
                           (
                               (
                                   (m.Animal__out_Animal_ParentOf__in_Animal_ParentOf
                                       __out_Animal_FedAt___1 == null)
                                   ||
                                   (it.event_date >= m.Animal__out_Animal_ParentOf
                                       __in_Animal_ParentOf__out_Animal_FedAt___1.event_date)
                               )
                               &&
                               (
                                   (m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 == null)
                                   ||
                                   (it.event_date <= m.Animal__out_Animal_ParentOf__out_Animal_FedAt
                                       ___1.event_date)
                               )
                           )
                       )}
                   .as('Animal__in_Animal_ParentOf__out_Animal_FedAt___1')
               .back('Animal__in_Animal_ParentOf___1')
           .back('Animal___1')
           .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                   grandchild_fed_at:
                       m.Animal__in_Animal_ParentOf__out_Animal_FedAt___1
                           .event_date.format("yyyy-MM-dd'T'HH:mm:ss"),
                   other_child_fed_at: (
                       (m.Animal__out_Animal_ParentOf__in_Animal_ParentOf
                           __out_Animal_FedAt___1 != null) ?
                           m.Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                               .event_date.format("yyyy-MM-dd'T'HH:mm:ss")
                           : null
                   ),
                   parent_fed_at: (
                       (m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 != null) ?
                           m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1
                               .event_date.format("yyyy-MM-dd'T'HH:mm:ss")
                           : null
                   )
               ])
           }
        """
        expected_mssql = """
            SELECT
                [FeedingEvent_1].event_date AS grandchild_fed_at,
                [FeedingEvent_2].event_date AS other_child_fed_at,
                [FeedingEvent_3].event_date AS parent_fed_at
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].uuid = [Animal_2].parent
                LEFT OUTER JOIN db_2.schema_1.[FeedingEvent] AS [FeedingEvent_3]
                    ON [Animal_2].fed_at = [FeedingEvent_3].uuid
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_3]
                    ON [Animal_2].parent = [Animal_3].uuid
                LEFT OUTER JOIN db_2.schema_1.[FeedingEvent] AS [FeedingEvent_2]
                    ON [Animal_3].fed_at = [FeedingEvent_2].uuid
                JOIN db_1.schema_1.[Animal] AS [Animal_4]
                    ON [Animal_1].parent = [Animal_4].uuid
                JOIN db_2.schema_1.[FeedingEvent] AS [FeedingEvent_1]
                    ON [Animal_4].fed_at = [FeedingEvent_1].uuid
            WHERE
                [Animal_1].name = :animal_name AND (
                     [FeedingEvent_2].uuid IS NOT NULL OR
                     [Animal_3].uuid IS NULL
                ) AND (
                     [FeedingEvent_3].uuid IS NULL OR
                     [FeedingEvent_1].name = [FeedingEvent_3].name
                ) AND (
                     [FeedingEvent_2].uuid IS NULL OR
                     [FeedingEvent_1].event_date >= [FeedingEvent_2].event_date
                ) AND (
                     [FeedingEvent_3].uuid IS NULL OR
                     [FeedingEvent_1].event_date <= [FeedingEvent_3].event_date
                )
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "FeedingEvent_1".event_date AS grandchild_fed_at,
                "FeedingEvent_2".event_date AS other_child_fed_at,
                "FeedingEvent_3".event_date AS parent_fed_at
            FROM
                schema_1."Animal" AS "Animal_1"
                JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".uuid = "Animal_2".parent
                LEFT OUTER JOIN schema_1."FeedingEvent" AS "FeedingEvent_3"
                    ON "Animal_2".fed_at = "FeedingEvent_3".uuid
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_3"
                    ON "Animal_2".parent = "Animal_3".uuid
                LEFT OUTER JOIN schema_1."FeedingEvent" AS "FeedingEvent_2"
                    ON "Animal_3".fed_at = "FeedingEvent_2".uuid
                JOIN schema_1."Animal" AS "Animal_4"
                    ON "Animal_1".parent = "Animal_4".uuid
                JOIN schema_1."FeedingEvent" AS "FeedingEvent_1"
                    ON "Animal_4".fed_at = "FeedingEvent_1".uuid
            WHERE
                "Animal_1".name = :animal_name AND (
                    "FeedingEvent_2".uuid IS NOT NULL OR
                    "Animal_3".uuid IS NULL
                ) AND (
                    "FeedingEvent_3".uuid IS NULL OR
                    "FeedingEvent_1".name = "FeedingEvent_3".name
                ) AND (
                    "FeedingEvent_2".uuid IS NULL OR
                    "FeedingEvent_1".event_date >= "FeedingEvent_2".event_date
                ) AND (
                    "FeedingEvent_3".uuid IS NULL OR
                    "FeedingEvent_1".event_date <= "FeedingEvent_3".event_date
                )
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_simple_optional_recurse(self) -> None:
        test_data = test_input_data.simple_optional_recurse()

        expected_match = """
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal___1.name AS `name`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((
                            (in_Animal_ParentOf IS null)
                            OR
                            (in_Animal_ParentOf.size() = 0)
                        )),
                        as: Animal___1
                    }}
                    RETURN $matches
                )
            ),
            $optional__1 = (
                SELECT
                    Animal__in_Animal_ParentOf___1.name AS `child_name`,
                    Animal___1.name AS `name`,
                    if(eval("(Animal__in_Animal_ParentOf__out_Animal_ParentOf___1 IS NOT null)"),
                        Animal__in_Animal_ParentOf__out_Animal_ParentOf___1.name,
                        null
                    ) AS `self_and_ancestor_name`
                FROM (
                    MATCH {{
                        class: Animal,
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf___1
                    }}.out('Animal_ParentOf') {{
                        while: ($depth < 3),
                        as: Animal__in_Animal_ParentOf__out_Animal_ParentOf___1
                    }}
                    RETURN $matches
                )
            ),
            $result = UNIONALL($optional__0, $optional__1)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{
                        it.copySplit(
                            _(),
                            _().out('Animal_ParentOf'),
                            _().out('Animal_ParentOf').out('Animal_ParentOf'),
                            _().out('Animal_ParentOf').out('Animal_ParentOf').out('Animal_ParentOf')
                        ).exhaustMerge
                    }
                    .as('Animal__in_Animal_ParentOf__out_Animal_ParentOf___1')
                .back('Animal__in_Animal_ParentOf___1')
                    .optional('Animal___1')
                    .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                    child_name: (
                        (m.Animal__in_Animal_ParentOf___1 != null) ?
                            m.Animal__in_Animal_ParentOf___1.name : null
                    ),
                    name: m.Animal___1.name,
                    self_and_ancestor_name: (
                        (m.Animal__in_Animal_ParentOf__out_Animal_ParentOf___1 != null) ?
                            m.Animal__in_Animal_ParentOf__out_Animal_ParentOf___1.name : null
                    )
            ])}
        """
        expected_mssql = """
            WITH anon_1 AS (
                SELECT
                    [Animal_1].name AS [Animal__name],
                    [Animal_1].parent AS [Animal__parent],
                    [Animal_2].name AS [Animal_in_Animal_ParentOf__name],
                    [Animal_2].uuid AS [Animal_in_Animal_ParentOf__uuid]
                FROM
                    db_1.schema_1.[Animal] AS [Animal_1]
                    LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_2]
                        ON [Animal_1].parent = [Animal_2].uuid
            ),
            anon_2(name, parent, uuid, __cte_key, __cte_depth) AS (
                SELECT
                    [Animal_3].name AS name,
                    [Animal_3].parent AS parent,
                    [Animal_3].uuid AS uuid,
                    [Animal_3].uuid AS __cte_key,
                    0 AS __cte_depth
                FROM
                    db_1.schema_1.[Animal] AS [Animal_3]
                WHERE
                    [Animal_3].uuid IN (SELECT anon_1.[Animal_in_Animal_ParentOf__uuid] FROM anon_1)
                UNION ALL
                SELECT
                    [Animal_4].name AS name,
                    [Animal_4].parent AS parent,
                    [Animal_4].uuid AS uuid,
                    anon_2.__cte_key AS __cte_key,
                    anon_2.__cte_depth + 1 AS __cte_depth
                FROM
                    anon_2
                    JOIN db_1.schema_1.[Animal] AS [Animal_4]
                        ON anon_2.uuid = [Animal_4].parent
                WHERE
                    anon_2.__cte_depth < 3
            )
            SELECT
                anon_1.[Animal_in_Animal_ParentOf__name] AS child_name,
                anon_1.[Animal__name] AS name,
                anon_2.name AS self_and_ancestor_name
            FROM
                anon_1
                LEFT OUTER JOIN anon_2
                    ON anon_1.[Animal_in_Animal_ParentOf__uuid] = anon_2.__cte_key
            WHERE anon_2.__cte_key IS NOT NULL OR anon_1.[Animal_in_Animal_ParentOf__uuid] IS NULL
        """
        # TODO(bojanserafimov) Test with a traversal inside the recurse. See that the recursive
        #                      cte uses LEFT OUTER JOIN.
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            WITH RECURSIVE anon_1 AS (
                SELECT
                    "Animal_1".name AS "Animal__name",
                    "Animal_1".parent AS "Animal__parent",
                    "Animal_2".name AS "Animal_in_Animal_ParentOf__name",
                    "Animal_2".uuid AS "Animal_in_Animal_ParentOf__uuid"
                FROM
                    schema_1."Animal" AS "Animal_1"
                    LEFT OUTER JOIN schema_1."Animal" AS "Animal_2"
                        ON "Animal_1".parent = "Animal_2".uuid
            ),
            anon_2(name, parent, uuid, __cte_key, __cte_depth) AS (
                SELECT
                    "Animal_3".name AS name,
                    "Animal_3".parent AS parent,
                    "Animal_3".uuid AS uuid,
                    "Animal_3".uuid AS __cte_key,
                    0 AS __cte_depth
                FROM
                    schema_1."Animal" AS "Animal_3"
                WHERE "Animal_3".uuid IN (
                    SELECT anon_1."Animal_in_Animal_ParentOf__uuid" FROM anon_1)
                UNION ALL
                SELECT
                    "Animal_4".name AS name,
                    "Animal_4".parent AS parent,
                    "Animal_4".uuid AS uuid,
                    anon_2.__cte_key AS __cte_key,
                    anon_2.__cte_depth + 1 AS __cte_depth
                FROM
                    anon_2
                    JOIN schema_1."Animal" AS "Animal_4"
                        ON anon_2.uuid = "Animal_4".parent
                WHERE anon_2.__cte_depth < 3
            )
            SELECT
                anon_1."Animal_in_Animal_ParentOf__name" AS child_name,
                anon_1."Animal__name" AS name,
                anon_2.name AS self_and_ancestor_name
            FROM
                anon_1
                LEFT OUTER JOIN anon_2
                    ON anon_1."Animal_in_Animal_ParentOf__uuid" = anon_2.__cte_key
                WHERE anon_2.__cte_key IS NOT NULL OR anon_1."Animal_in_Animal_ParentOf__uuid"
                    IS NULL
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_multiple_traverse_within_optional(self) -> None:
        test_data = test_input_data.multiple_traverse_within_optional()

        expected_match = """
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal___1.name AS `name`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((
                            (in_Animal_ParentOf IS null)
                            OR
                            (in_Animal_ParentOf.size() = 0)
                        )),
                        as: Animal___1
                    }}
                    RETURN $matches
                )
            ),
            $optional__1 = (
                SELECT
                    Animal__in_Animal_ParentOf__out_Animal_FedAt___1.name AS `child_feeding_time`,
                    Animal__in_Animal_ParentOf___1.name AS `child_name`,
                    Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name AS `grandchild_name`,
                    Animal___1.name AS `name`
                FROM (
                    MATCH {{
                        class: Animal,
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf___1
                    }}.in('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
                    }} ,
                    {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf___1
                    }}.out('Animal_FedAt') {{
                        class: FeedingEvent,
                        as: Animal__in_Animal_ParentOf__out_Animal_FedAt___1
                    }}
                    RETURN $matches
                )
            ),
            $result = UNIONALL($optional__0, $optional__1)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{it.in('Animal_ParentOf')}
                    .as('Animal__in_Animal_ParentOf__in_Animal_ParentOf___1')
                .back('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{it.out('Animal_FedAt')}
                    .as('Animal__in_Animal_ParentOf__out_Animal_FedAt___1')
                .back('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_feeding_time: (
                    (m.Animal__in_Animal_ParentOf__out_Animal_FedAt___1 != null) ?
                        m.Animal__in_Animal_ParentOf__out_Animal_FedAt___1.name : null
                ),
                child_name: (
                    (m.Animal__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf___1.name : null
                ),
                grandchild_name: (
                    (m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name : null
                ),
                name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [FeedingEvent_1].name AS child_feeding_time,
                [Animal_1].name AS child_name,
                [Animal_2].name AS grandchild_name,
                [Animal_3].name AS name
            FROM
                db_1.schema_1.[Animal] AS [Animal_3]
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_1]
                    ON [Animal_3].parent = [Animal_1].uuid
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].parent = [Animal_2].uuid
                LEFT OUTER JOIN db_2.schema_1.[FeedingEvent] AS [FeedingEvent_1]
                    ON [Animal_1].fed_at = [FeedingEvent_1].uuid
            WHERE (
                [Animal_2].uuid IS NOT NULL OR
                [Animal_1].uuid IS NULL
            ) AND (
                [FeedingEvent_1].uuid IS NOT NULL OR
                [Animal_1].uuid IS NULL
            )
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "FeedingEvent_1".name AS child_feeding_time,
                "Animal_1".name AS child_name,
                "Animal_2".name AS grandchild_name,
                "Animal_3".name AS name
            FROM
                schema_1."Animal" AS "Animal_3"
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_1"
                    ON "Animal_3".parent = "Animal_1".uuid
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".parent = "Animal_2".uuid
                LEFT OUTER JOIN schema_1."FeedingEvent" AS "FeedingEvent_1"
                    ON "Animal_1".fed_at = "FeedingEvent_1".uuid
            WHERE (
                "Animal_2".uuid IS NOT NULL OR
                "Animal_1".uuid IS NULL
            ) AND (
                "FeedingEvent_1".uuid IS NOT NULL OR
                "Animal_1".uuid IS NULL
            )
        """
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_optional_and_fold(self) -> None:
        test_data = test_input_data.optional_and_fold()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___out_Animal_ParentOf.name AS `child_names_list`,
                if(eval("(Animal__in_Animal_ParentOf___1 IS NOT null)"),
                    Animal__in_Animal_ParentOf___1.name,
                    null
                ) AS `parent_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    optional: true,
                    as: Animal__in_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            LET
                $Animal___1___out_Animal_ParentOf = Animal___1.out("Animal_ParentOf").asList()
            WHERE (
                (
                    (Animal___1.in_Animal_ParentOf IS null)
                    OR
                    (Animal___1.in_Animal_ParentOf.size() = 0)
                )
                OR
                (Animal__in_Animal_ParentOf___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_names_list: (
                    (m.Animal___2.out_Animal_ParentOf == null) ?
                        [] :
                        (m.Animal___2.out_Animal_ParentOf.collect{entry -> entry.inV.next().name})
                ),
                parent_name: (
                    (m.Animal__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf___1.name : null
                )
            ])}
        """
        expected_postgresql = """
            SELECT
              "Animal_1".name AS animal_name,
              coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[]) AS child_names_list,
              "Animal_2".name AS parent_name
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN
                schema_1."Animal" AS "Animal_2"
            ON "Animal_1".parent = "Animal_2".uuid
            LEFT OUTER JOIN (
                SELECT
                  "Animal_3".uuid AS uuid,
                  array_agg("Animal_4".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_3"
                JOIN schema_1."Animal" AS "Animal_4"
                ON "Animal_3".uuid = "Animal_4".parent
                GROUP BY "Animal_3".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              Animal__in_Animal_ParentOf___1 AS Animal__in_Animal_ParentOf___1,
              collect(Animal__out_Animal_ParentOf___1) AS collected_Animal__out_Animal_ParentOf___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN collected_Animal__out_Animal_ParentOf___1 | x.name] AS `child_names_list`,
              (CASE
                WHEN (Animal__in_Animal_ParentOf___1 IS NOT null)
                  THEN Animal__in_Animal_ParentOf___1.name
                  ELSE null
                END) AS `parent_name`
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_name AS child_names_list,
                [Animal_2].name AS parent_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            LEFT OUTER JOIN
                db_1.schema_1.[Animal] AS [Animal_2]
            ON [Animal_1].parent = [Animal_2].uuid
            JOIN(
                SELECT
                    [Animal_3].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Animal_4].name, '^', '^e'),
                                    '~',
                                    '^n'),
                                '|',
                                '^d'),
                            '~')
                        FROM
                            db_1.schema_1.[Animal] AS [Animal_4]
                        WHERE
                            [Animal_3].uuid = [Animal_4].parent FOR XML PATH('')),
                    '') AS fold_output_name
                FROM
                    db_1.schema_1.[Animal] AS [Animal_3]
            ) AS folded_subquery_1 ON [Animal_1].uuid = folded_subquery_1.uuid
            """
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_and_optional(self) -> None:
        test_data = test_input_data.fold_and_optional()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___out_Animal_ParentOf.name AS `child_names_list`,
                if(eval("(Animal__in_Animal_ParentOf___1 IS NOT null)"),
                    Animal__in_Animal_ParentOf___1.name,
                    null
                ) AS `parent_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    optional: true,
                    as: Animal__in_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            LET
                $Animal___1___out_Animal_ParentOf = Animal___1.out("Animal_ParentOf").asList()
            WHERE (
                (
                    (Animal___1.in_Animal_ParentOf IS null)
                    OR
                    (Animal___1.in_Animal_ParentOf.size() = 0)
                )
                OR
                (Animal__in_Animal_ParentOf___1 IS NOT null)
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_names_list: (
                    (m.Animal___1.out_Animal_ParentOf == null) ?
                        [] :
                        (m.Animal___1.out_Animal_ParentOf.collect{entry -> entry.inV.next().name})
                ),
                parent_name: (
                    (m.Animal__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf___1.name : null
                )
            ])}
        """
        expected_postgresql = """
            SELECT
              "Animal_1".name AS animal_name,
              coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[]) AS child_names_list,
              "Animal_2".name AS parent_name
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                  "Animal_3".uuid AS uuid,
                  array_agg("Animal_4".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_3"
                JOIN schema_1."Animal" AS "Animal_4"
                ON "Animal_3".uuid = "Animal_4".parent
                GROUP BY "Animal_3".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
            LEFT OUTER JOIN
                schema_1."Animal" AS "Animal_2"
            ON "Animal_1".parent = "Animal_2".uuid
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              Animal__in_Animal_ParentOf___1 AS Animal__in_Animal_ParentOf___1,
              collect(Animal__out_Animal_ParentOf___1) AS collected_Animal__out_Animal_ParentOf___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN collected_Animal__out_Animal_ParentOf___1 | x.name] AS `child_names_list`,
              (CASE
                WHEN (Animal__in_Animal_ParentOf___1 IS NOT null)
                  THEN Animal__in_Animal_ParentOf___1.name
                  ELSE null
                END) AS `parent_name`
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_name AS child_names_list,
                [Animal_2].nameASparent_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            JOIN (
                SELECT
                    [Animal_3].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Animal_4].name, '^', '^e'),
                                    '~',
                                    '^n'),
                                '|',
                                '^d'),
                            '~')
                        FROM
                            db_1.schema_1.[Animal] AS [Animal_4]
                        WHERE
                            [Animal_3].uuid = [Animal_4].parent FOR XML PATH('')),
                    '') AS fold_output_name
                FROM
                    db_1.schema_1.[Animal] AS [Animal_3]
            ) AS folded_subquery_1 ON [Animal_1].uuid = folded_subquery_1.uuid
            LEFT OUTER JOIN
                db_1.schema_1.[Animal] AS [Animal_2]
            ON [Animal_1].parent = [Animal_2].uuid
        """
        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_optional_traversal_and_fold_traversal(self) -> None:
        test_data = test_input_data.optional_traversal_and_fold_traversal()

        expected_match = """
            SELECT EXPAND($result)
            LET
                $optional__0 = (
                    SELECT
                        Animal___1.name AS `animal_name`,
                        $Animal___1___out_Animal_ParentOf.name AS `grandchild_names_list`
                    FROM (
                        MATCH {{
                            class: Animal,
                            where: ((
                                    (in_Animal_ParentOf IS null)
                                    OR
                                    (in_Animal_ParentOf.size() = 0))),
                            as: Animal___1
                        }}
                        RETURN $matches
                    )
                    LET
                        $Animal___1___out_Animal_ParentOf =
                            Animal___1.out("Animal_ParentOf").out("Animal_ParentOf").asList()
                ),
                $optional__1 = (
                    SELECT
                        Animal___1.name AS `animal_name`,
                        $Animal___1___out_Animal_ParentOf.name AS `grandchild_names_list`,
                        Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name
                            AS `grandparent_name`
                    FROM (
                        MATCH {{
                            class: Animal,
                            as: Animal___1
                        }}.in('Animal_ParentOf') {{
                            class: Animal,
                            as: Animal__in_Animal_ParentOf___1
                        }}.in('Animal_ParentOf') {{
                            class: Animal,
                            as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
                        }}
                        RETURN $matches
                    )
                LET
                    $Animal___1___out_Animal_ParentOf
                        = Animal___1.out("Animal_ParentOf").out("Animal_ParentOf").asList()
                ),
                $result = UNIONALL($optional__0, $optional__1)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{it.in('Animal_ParentOf')}
                    .as('Animal__in_Animal_ParentOf__in_Animal_ParentOf___1')
                .back('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                grandchild_names_list: (
                    (m.Animal___2.out_Animal_ParentOf == null) ?
                        [] :
                        (m.Animal___2.out_Animal_ParentOf
                            .collect{entry -> entry.inV.next()}
                            .collectMany{entry ->
                                entry.out_Animal_ParentOf.collect{edge -> edge.inV.next()}
                            }
                            .collect{entry -> entry.name})),
                grandparent_name: (
                    (m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name : null
                )
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_name AS grandchild_names_list,
                [Animal_2].name AS grandparent_name
            FROM db_1.schema_1.[Animal] AS [Animal_1]
            LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_3]
            ON [Animal_1].parent = [Animal_3].uuid
            LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_2]
            ON [Animal_3].parent = [Animal_2].uuid
            JOIN (
                SELECT
                    [Animal_4].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Animal_5].name, '^', '^e'),
                                    '~', '^n'),
                                '|', '^d'),
                            '~')
                        FROM db_1.schema_1.[Animal] AS [Animal_6]
                        JOIN db_1.schema_1.[Animal] AS [Animal_5]
                        ON [Animal_6].uuid = [Animal_5].parent
                        WHERE [Animal_4].uuid = [Animal_6].parent
                        FOR XML PATH ('')
                    ), '') AS fold_output_name
                FROM db_1.schema_1.[Animal] AS [Animal_4]
            ) AS folded_subquery_1
            ON [Animal_1].uuid = folded_subquery_1.uuid
            WHERE [Animal_2].uuid IS NOT NULL OR [Animal_3].uuid IS NULL
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH
              (Animal__in_Animal_ParentOf___1)<-[:Animal_ParentOf]-
              (Animal__in_Animal_ParentOf__in_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH
              (Animal__out_Animal_ParentOf___1)-[:Animal_ParentOf]->
              (Animal__out_Animal_ParentOf__out_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              Animal__in_Animal_ParentOf___1 AS Animal__in_Animal_ParentOf___1,
              Animal__in_Animal_ParentOf__in_Animal_ParentOf___1 AS
                Animal__in_Animal_ParentOf__in_Animal_ParentOf___1,
              collect(Animal__out_Animal_ParentOf___1) AS collected_Animal__out_Animal_ParentOf___1,
              collect(Animal__out_Animal_ParentOf__out_Animal_ParentOf___1) AS
                collected_Animal__out_Animal_ParentOf__out_Animal_ParentOf___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN collected_Animal__out_Animal_ParentOf__out_Animal_ParentOf___1 | x.name] AS
                `grandchild_names_list`,
              (CASE
                WHEN (Animal__in_Animal_ParentOf__in_Animal_ParentOf___1 IS NOT null)
                  THEN Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name
                  ELSE null
                END) AS `grandparent_name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                    AS grandchild_names_list,
                "Animal_2".name AS grandparent_name
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN schema_1."Animal" AS "Animal_3"
            ON "Animal_1".parent = "Animal_3".uuid
            LEFT OUTER JOIN schema_1."Animal" AS "Animal_2"
            ON "Animal_3".parent = "Animal_2".uuid
            LEFT OUTER JOIN (
                SELECT
                    "Animal_4".uuid AS uuid,
                    array_agg("Animal_5".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_4"
                JOIN schema_1."Animal" AS "Animal_6"
                ON "Animal_4".uuid = "Animal_6".parent
                JOIN schema_1."Animal" AS "Animal_5"
                ON "Animal_6".uuid = "Animal_5".parent
                GROUP BY "Animal_4".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
            WHERE "Animal_2".uuid IS NOT NULL OR "Animal_3".uuid IS NULL
"""

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_fold_traversal_and_optional_traversal(self) -> None:
        test_data = test_input_data.fold_traversal_and_optional_traversal()

        expected_match = """
            SELECT EXPAND($result)
            LET
                $optional__0 = (
                    SELECT
                        Animal___1.name AS `animal_name`,
                        $Animal___1___out_Animal_ParentOf.name AS `grandchild_names_list`
                    FROM (
                        MATCH {{
                            class: Animal,
                            where: ((
                                    (in_Animal_ParentOf IS null)
                                    OR
                                    (in_Animal_ParentOf.size() = 0))),
                            as: Animal___1
                        }}
                        RETURN $matches
                    )
                    LET
                        $Animal___1___out_Animal_ParentOf =
                            Animal___1.out("Animal_ParentOf").out("Animal_ParentOf").asList()
                ),
                $optional__1 = (
                    SELECT
                        Animal___1.name AS `animal_name`,
                        $Animal___1___out_Animal_ParentOf.name AS `grandchild_names_list`,
                        Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name
                            AS `grandparent_name`
                    FROM (
                        MATCH {{
                            class: Animal,
                            as: Animal___1
                        }}.in('Animal_ParentOf') {{
                            class: Animal,
                            as: Animal__in_Animal_ParentOf___1
                        }}.in('Animal_ParentOf') {{
                            class: Animal,
                            as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
                        }}
                        RETURN $matches
                    )
                LET
                    $Animal___1___out_Animal_ParentOf
                        = Animal___1.out("Animal_ParentOf").out("Animal_ParentOf").asList()
                ),
                $result = UNIONALL($optional__0, $optional__1)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it == null}{null}{it.in('Animal_ParentOf')}
                    .as('Animal__in_Animal_ParentOf__in_Animal_ParentOf___1')
                .back('Animal__in_Animal_ParentOf___1')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name, grandchild_names_list: (
                    (m.Animal___1.out_Animal_ParentOf == null) ?
                        [] : (m.Animal___1.out_Animal_ParentOf.collect{entry -> entry.inV.next()}
            .collectMany{entry -> entry.out_Animal_ParentOf.collect{edge -> edge.inV.next()}}
            .collect{entry -> entry.name})), grandparent_name: (
                    (m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name : null
                )
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                folded_subquery_1.fold_output_name AS grandchild_names_list,
                [Animal_2].name AS grandparent_name
            FROM db_1.schema_1.[Animal] AS [Animal_1]
            JOIN (
                SELECT
                    [Animal_3].uuid AS uuid,
                    coalesce((
                        SELECT
                            '|' + coalesce(
                                REPLACE(
                                    REPLACE(
                                        REPLACE([Animal_4].name, '^', '^e'),
                                    '~', '^n'),
                                '|', '^d'),
                            '~')
                        FROM db_1.schema_1.[Animal] AS [Animal_5]
                        JOIN db_1.schema_1.[Animal] AS [Animal_4]
                        ON [Animal_5].uuid = [Animal_4].parent
                        WHERE [Animal_3].uuid = [Animal_5].parent
                        FOR XML PATH ('')
                    ), '') AS fold_output_name
                FROM db_1.schema_1.[Animal] AS [Animal_3]
            ) AS folded_subquery_1
            ON [Animal_1].uuid = folded_subquery_1.uuid
            LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_6]
            ON [Animal_1].parent = [Animal_6].uuid
            LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_2]
            ON [Animal_6].parent = [Animal_2].uuid
            WHERE [Animal_2].uuid IS NOT NULL OR [Animal_6].uuid IS NULL
"""
        expected_cypher = """
            MATCH (Animal___1:Animal)
            OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH
              (Animal__in_Animal_ParentOf___1)<-[:Animal_ParentOf]-
              (Animal__in_Animal_ParentOf__in_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
            OPTIONAL MATCH
              (Animal__out_Animal_ParentOf___1)-[:Animal_ParentOf]->
              (Animal__out_Animal_ParentOf__out_Animal_ParentOf___1:Animal)
            WITH
              Animal___1 AS Animal___1,
              Animal__in_Animal_ParentOf___1 AS Animal__in_Animal_ParentOf___1,
              Animal__in_Animal_ParentOf__in_Animal_ParentOf___1 AS
                Animal__in_Animal_ParentOf__in_Animal_ParentOf___1,
              collect(Animal__out_Animal_ParentOf___1) AS
                collected_Animal__out_Animal_ParentOf___1,
              collect(Animal__out_Animal_ParentOf__out_Animal_ParentOf___1) AS
                collected_Animal__out_Animal_ParentOf__out_Animal_ParentOf___1
            RETURN
              Animal___1.name AS `animal_name`,
              [x IN collected_Animal__out_Animal_ParentOf__out_Animal_ParentOf___1 | x.name] AS
                `grandchild_names_list`,
              (CASE
                WHEN (Animal__in_Animal_ParentOf__in_Animal_ParentOf___1 IS NOT null)
                  THEN Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name
                  ELSE null
                END) AS `grandparent_name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                coalesce(folded_subquery_1.fold_output_name, ARRAY[]::VARCHAR[])
                    AS grandchild_names_list,
                "Animal_2".name AS grandparent_name
            FROM schema_1."Animal" AS "Animal_1"
            LEFT OUTER JOIN (
                SELECT
                    "Animal_3".uuid AS uuid,
                    array_agg("Animal_4".name) AS fold_output_name
                FROM schema_1."Animal" AS "Animal_3"
                JOIN schema_1."Animal" AS "Animal_5"
                ON "Animal_3".uuid = "Animal_5".parent
                JOIN schema_1."Animal" AS "Animal_4"
                ON "Animal_5".uuid = "Animal_4".parent
                GROUP BY "Animal_3".uuid
            ) AS folded_subquery_1
            ON "Animal_1".uuid = folded_subquery_1.uuid
            LEFT OUTER JOIN schema_1."Animal" AS "Animal_6"
            ON "Animal_1".parent = "Animal_6".uuid
            LEFT OUTER JOIN schema_1."Animal" AS "Animal_2"
            ON "Animal_6".parent = "Animal_2".uuid
            WHERE "Animal_2".uuid IS NOT NULL OR "Animal_6".uuid IS NULL
            """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_between_lowering(self) -> None:
        test_data = test_input_data.between_lowering()

        expected_match = """
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((
                        (uuid BETWEEN {uuid_lower} AND {uuid_upper})
                        AND
                        (birthday >= date({earliest_modified_date}, "yyyy-MM-dd"))
                    )),
                    as: Animal___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .filter{it, m ->
                (
                    ((it.uuid >= $uuid_lower) && (it.uuid <= $uuid_upper))
                    &&
                    (it.birthday >= Date.parse("yyyy-MM-dd", $earliest_modified_date))
                )}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
            WHERE
                [Animal_1].uuid >= :uuid_lower
                AND [Animal_1].uuid <= :uuid_upper
                AND [Animal_1].birthday >= :earliest_modified_date
        """
        expected_cypher = """
            MATCH (Animal___1:Animal)
                WHERE (((Animal___1.uuid >= $uuid_lower) AND (Animal___1.uuid <= $uuid_upper))
                        AND (Animal___1.birthday >= $earliest_modified_date))
            RETURN
                Animal___1.name AS `animal_name`
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name
            FROM
                schema_1."Animal" AS "Animal_1"
            WHERE
                "Animal_1".uuid >= :uuid_lower
                AND "Animal_1".uuid <= :uuid_upper
                AND "Animal_1".birthday >= :earliest_modified_date
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_coercion_and_filter_with_tag(self) -> None:
        test_data = test_input_data.coercion_and_filter_with_tag()

        expected_match = """
            SELECT
                Animal___1.name AS `origin`,
                Animal__out_Entity_Related___1.name AS `related_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Entity_Related') {{
                    class: Animal,
                    where: ((name LIKE ('%' + ($matched.Animal___1.name + '%')))),
                    as: Animal__out_Entity_Related___1
                }}
                RETURN $matches
            )
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .out('Entity_Related')
                .filter{it, m ->
                    (
                        ['Animal'].contains(it['@class'])
                        &&
                        it.name.contains(m.Animal___1.name)
                    )
                }
                .as('Animal__out_Entity_Related___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                origin: m.Animal___1.name,
                related_name: m.Animal__out_Entity_Related___1.name
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_nested_optional_and_traverse(self) -> None:
        test_data = test_input_data.nested_optional_and_traverse()

        expected_match = """
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal___1.name AS `animal_name`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((
                            (in_Animal_ParentOf IS null)
                            OR
                            (in_Animal_ParentOf.size() = 0)
                        )),
                        as: Animal___1
                    }}
                    RETURN $matches
                )
            ),
            $optional__1 = (
                SELECT
                    Animal___1.name AS `animal_name`,
                    Animal__in_Animal_ParentOf___1.name AS `child_name`
                FROM (
                    MATCH {{
                        where: ((@this INSTANCEOF 'Animal')),
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        class: Animal,
                        where: ((
                            (out_Animal_ParentOf IS null)
                            OR
                            (out_Animal_ParentOf.size() = 0)
                        )),
                        as: Animal__in_Animal_ParentOf___1
                    }}
                    RETURN $matches
                )
            ),
            $optional__2 = (
                SELECT
                    Animal___1.name AS `animal_name`,
                    Animal__in_Animal_ParentOf___1.name AS `child_name`,
                    Animal__in_Animal_ParentOf__out_Animal_ParentOf___1.name
                        AS `spouse_and_self_name`,
                    Animal__in_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1.name
                        AS `spouse_species`
                FROM (
                    MATCH {{
                        class: Animal,
                        as: Animal___1
                    }}.in('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf___1
                    }}.out('Animal_ParentOf') {{
                        class: Animal,
                        as: Animal__in_Animal_ParentOf__out_Animal_ParentOf___1
                    }}.out('Animal_OfSpecies') {{
                        class: Species,
                        as: Animal__in_Animal_ParentOf__out_Animal_ParentOf
                            __out_Animal_OfSpecies___1
                    }}
                    RETURN $matches
                )
            ),
            $result = UNIONALL($optional__0, $optional__1, $optional__2)
        """
        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it.out_Animal_ParentOf == null}{null}{it.out('Animal_ParentOf')}
                    .as('Animal__in_Animal_ParentOf__out_Animal_ParentOf___1')
                        .ifThenElse{it == null}{null}{it.out('Animal_OfSpecies')}
                        .as('Animal__in_Animal_ParentOf__out_Animal_ParentOf
                             __out_Animal_OfSpecies___1')
                    .back('Animal__in_Animal_ParentOf__out_Animal_ParentOf___1')
                .optional('Animal__in_Animal_ParentOf___1')
                .as('Animal__in_Animal_ParentOf___2')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_name: (
                    (m.Animal__in_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf___1.name : null
                ),
                spouse_and_self_name: (
                    (m.Animal__in_Animal_ParentOf__out_Animal_ParentOf___1 != null) ?
                        m.Animal__in_Animal_ParentOf__out_Animal_ParentOf___1.name : null
                ),
                spouse_species: (
                    (m.Animal__in_Animal_ParentOf__out_Animal_ParentOf
                       __out_Animal_OfSpecies___1 != null) ?
                        m.Animal__in_Animal_ParentOf__out_Animal_ParentOf
                          __out_Animal_OfSpecies___1.name
                        : null
                )
            ])}
        """
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                [Animal_2].name AS child_name,
                [Animal_3].name AS spouse_and_self_name,
                [Species_1].name AS spouse_species
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_2]
                    ON [Animal_1].parent = [Animal_2].uuid
                LEFT OUTER JOIN db_1.schema_1.[Animal] AS [Animal_3]
                    ON [Animal_2].uuid = [Animal_3].parent
                LEFT OUTER JOIN db_1.schema_1.[Species] AS [Species_1]
                    ON [Animal_3].species = [Species_1].uuid
            WHERE [Species_1].uuid IS NOT NULL OR [Animal_3].parent IS NULL
        """
        expected_cypher = SKIP_TEST
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                "Animal_2".name AS child_name,
                "Animal_3".name AS spouse_and_self_name,
                "Species_1".name AS spouse_species
            FROM
                schema_1."Animal" AS "Animal_1"
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_2"
                    ON "Animal_1".parent = "Animal_2".uuid
                LEFT OUTER JOIN schema_1."Animal" AS "Animal_3"
                    ON "Animal_2".uuid = "Animal_3".parent
                LEFT OUTER JOIN schema_1."Species" AS "Species_1"
                    ON "Animal_3".species = "Species_1".uuid
            WHERE "Species_1".uuid IS NOT NULL OR "Animal_3".parent IS NULL
        """

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )

    def test_complex_nested_optionals(self) -> None:
        test_data = test_input_data.complex_nested_optionals()

        # The correct MATCH output is outrageously long, and is stored in a separate file.
        match_output_file = "./complex_nested_optionals_output.sql"
        with open(os.path.join(os.path.dirname(__file__), match_output_file)) as f:
            expected_match = f.read()

        expected_gremlin = """
            g.V('@class', 'Animal')
            .as('Animal___1')
                .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                .as('Animal__in_Animal_ParentOf___1')
                    .ifThenElse{it.in_Animal_ParentOf == null}{null}{it.in('Animal_ParentOf')}
                    .as('Animal__in_Animal_ParentOf__in_Animal_ParentOf___1')
                        .ifThenElse{it == null}{null}{it.out('Animal_OfSpecies')}
                        .as('Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1')
                    .back('Animal__in_Animal_ParentOf__in_Animal_ParentOf___1')
                .optional('Animal__in_Animal_ParentOf___1')
                .as('Animal__in_Animal_ParentOf___2')
                    .ifThenElse{it.in_Entity_Related == null}{null}{it.in('Entity_Related')}
                    .filter{it, m -> ((it == null) || ['Animal'].contains(it['@class']))}
                    .as('Animal__in_Animal_ParentOf__in_Entity_Related___1')
                        .ifThenElse{it == null}{null}{it.out('Animal_OfSpecies')}
                        .as('Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1')
                    .back('Animal__in_Animal_ParentOf__in_Entity_Related___1')
                .optional('Animal__in_Animal_ParentOf___2')
                .as('Animal__in_Animal_ParentOf___3')
            .optional('Animal___1')
            .as('Animal___2')
                .ifThenElse{it.out_Animal_ParentOf == null}{null}{it.out('Animal_ParentOf')}
                .as('Animal__out_Animal_ParentOf___1')
                    .ifThenElse{it.out_Animal_ParentOf == null}{null}{it.out('Animal_ParentOf')}
                    .as('Animal__out_Animal_ParentOf__out_Animal_ParentOf___1')
                        .ifThenElse{it == null}{null}{it.out('Animal_OfSpecies')}
                        .as('Animal__out_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1')
                    .back('Animal__out_Animal_ParentOf__out_Animal_ParentOf___1')
                .optional('Animal__out_Animal_ParentOf___1')
                .as('Animal__out_Animal_ParentOf___2')
            .optional('Animal___2')
            .as('Animal___3')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_name: (
                    (m.Animal__in_Animal_ParentOf___1 != null) ?
                    m.Animal__in_Animal_ParentOf___1.name : null
                ),
                grandchild_name: (
                    (m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
                        != null) ?
                    m.Animal__in_Animal_ParentOf__in_Animal_ParentOf___1.name : null
                ),
                grandchild_relation_name: (
                    (m.Animal__in_Animal_ParentOf__in_Entity_Related___1
                        != null) ?
                    m.Animal__in_Animal_ParentOf__in_Entity_Related___1.name : null
                ),
                grandchild_relation_species: (
                    (m.Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1
                        != null) ?
                    m.Animal__in_Animal_ParentOf__in_Entity_Related__out_Animal_OfSpecies___1.name
                    : null
                ),
                grandchild_species: (
                    (m.Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1
                        != null) ?
                    m.Animal__in_Animal_ParentOf__in_Animal_ParentOf__out_Animal_OfSpecies___1.name
                    : null
                ),
                grandparent_name: (
                    (m.Animal__out_Animal_ParentOf__out_Animal_ParentOf___1 != null) ?
                    m.Animal__out_Animal_ParentOf__out_Animal_ParentOf___1.name : null
                ),
                grandparent_species: (
                    (m.Animal__out_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1
                        != null) ?
                    m.Animal__out_Animal_ParentOf__out_Animal_ParentOf__out_Animal_OfSpecies___1.name
                    : null
                ),
                parent_name: (
                    (m.Animal__out_Animal_ParentOf___1 != null) ?
                    m.Animal__out_Animal_ParentOf___1.name : null)
            ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_recursive_field_type_is_subtype_of_parent_field(self) -> None:
        """Ensure recursion can occur on an edge assigned to a supertype of the current scope."""
        test_data = test_input_data.recursive_field_type_is_subtype_of_parent_field()

        expected_match = """
            SELECT BirthEvent__out_Event_RelatedEvent___1.name AS `related_event_name`
            FROM (
                MATCH {{
                    class: BirthEvent,
                    as: BirthEvent___1
                }}.out('Event_RelatedEvent') {{
                    while: ($depth < 2),
                    as: BirthEvent__out_Event_RelatedEvent___1
                }}
                RETURN $matches
            )
        """

        expected_gremlin = """
            g.V('@class', 'BirthEvent')
            .as('BirthEvent___1')
            .copySplit(_(),_()
            .out('Event_RelatedEvent'),_()
            .out('Event_RelatedEvent')
            .out('Event_RelatedEvent'))
            .exhaustMerge.as('BirthEvent__out_Event_RelatedEvent___1')
            .back('BirthEvent___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                related_event_name: m.BirthEvent__out_Event_RelatedEvent___1.name ])}
        """
        expected_sql = NotImplementedError
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_sql,
            expected_cypher,
            expected_sql,
        )

    def test_animal_born_at_traversal(self) -> None:
        """Ensure that sql composite key traversals work."""
        test_data = test_input_data.animal_born_at_traversal()

        expected_match = SKIP_TEST
        expected_gremlin = SKIP_TEST
        expected_mssql = """
            SELECT
                [Animal_1].name AS animal_name,
                [BirthEvent_1].name AS birth_event_name
            FROM
                db_1.schema_1.[Animal] AS [Animal_1]
                JOIN db_1.schema_1.[BirthEvent] AS [BirthEvent_1]
                    ON [Animal_1].birth_date = [BirthEvent_1].event_date
                    AND [Animal_1].birth_uuid = [BirthEvent_1].uuid
        """
        expected_postgresql = """
            SELECT
                "Animal_1".name AS animal_name,
                "BirthEvent_1".name AS birth_event_name
            FROM
                schema_1."Animal" AS "Animal_1"
                JOIN schema_1."BirthEvent" AS "BirthEvent_1"
                    ON "Animal_1".birth_date = "BirthEvent_1".event_date
                    AND "Animal_1".birth_uuid = "BirthEvent_1".uuid
        """
        expected_cypher = SKIP_TEST

        check_test_data(
            self,
            test_data,
            expected_match,
            expected_gremlin,
            expected_mssql,
            expected_cypher,
            expected_postgresql,
        )
