# Copyright 2017-present Kensho Technologies, LLC.
"""End-to-end tests of the GraphQL compiler."""
import unittest

from graphql import GraphQLID, GraphQLString
import six

from . import test_input_data
from ..compiler import OutputMetadata, compile_graphql_to_gremlin, compile_graphql_to_match
from .test_helpers import compare_gremlin, compare_input_metadata, compare_match, get_schema


def check_test_data(test_case, test_data, expected_match, expected_gremlin):
    """Assert that the GraphQL input generates all expected MATCH and Gremlin data."""
    if test_data.type_equivalence_hints:
        # For test convenience, we accept the type equivalence hints in string form.
        # Here, we convert them to the required GraphQL types.
        schema_based_type_equivalence_hints = {
            test_case.schema.get_type(key): test_case.schema.get_type(value)
            for key, value in six.iteritems(test_data.type_equivalence_hints)
        }
    else:
        schema_based_type_equivalence_hints = None

    result = compile_graphql_to_match(test_case.schema, test_data.graphql_input,
                                      type_equivalence_hints=schema_based_type_equivalence_hints)
    compare_match(test_case, expected_match, result.query)
    test_case.assertEqual(test_data.expected_output_metadata, result.output_metadata)
    compare_input_metadata(test_case, test_data.expected_input_metadata, result.input_metadata)

    result = compile_graphql_to_gremlin(test_case.schema, test_data.graphql_input,
                                        type_equivalence_hints=schema_based_type_equivalence_hints)
    compare_gremlin(test_case, expected_gremlin, result.query)
    test_case.assertEqual(test_data.expected_output_metadata, result.output_metadata)
    compare_input_metadata(test_case, test_data.expected_input_metadata, result.input_metadata)


class CompilerTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.schema = get_schema()

    def test_immediate_output(self):
        test_data = test_input_data.immediate_output()

        expected_match = '''
            SELECT
                Animal___1.name AS `animal_name`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}
                RETURN $matches
            )
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_immediate_output_custom_scalars(self):
        test_data = test_input_data.immediate_output_custom_scalars()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                birthday: m.Animal___1.birthday.format("yyyy-MM-dd"),
                net_worth: m.Animal___1.net_worth
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_immediate_output_with_custom_scalar_filter(self):
        test_data = test_input_data.immediate_output_with_custom_scalar_filter()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> (it.net_worth >= $min_worth)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_immediate_filter_and_output(self):
        # Ensure that all basic comparison operators output correct code in this simple case.
        comparison_operators = {u'=', u'!=', u'>', u'<', u'>=', u'<='}

        for operator in comparison_operators:
            graphql_input = '''{
                Animal {
                    name @filter(op_name: "%s", value: ["$wanted"]) @output(out_name: "animal_name")
                }
            }''' % (operator,)

            # In MATCH, inequality comparisons use the SQL standard "<>" rather than "!=".
            match_operator = u'<>' if operator == u'!=' else operator
            expected_match = '''
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
            ''' % {'operator': match_operator}

            # In Gremlin, equality comparisons use two equal signs instead of one, unlike in MATCH.
            gremlin_operator = u'==' if operator == u'=' else operator
            expected_gremlin = '''
                g.V('@class', 'Animal')
                .filter{it, m -> (it.name %(operator)s $wanted)}
                .as('Animal___1')
                .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                    animal_name: m.Animal___1.name
                ])}
            ''' % {'operator': gremlin_operator}
            expected_output_metadata = {
                'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            }
            expected_input_metadata = {
                'wanted': GraphQLString,
            }

            test_data = test_input_data.CommonTestData(
                graphql_input=graphql_input,
                expected_output_metadata=expected_output_metadata,
                expected_input_metadata=expected_input_metadata,
                type_equivalence_hints=None)

            check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_multiple_filters(self):
        test_data = test_input_data.multiple_filters()

        expected_match = '''
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
        '''

        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> ((it.name >= $lower_bound) && (it.name < $upper_bound))}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_traverse_and_output(self):
        test_data = test_input_data.traverse_and_output()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_ParentOf')
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                parent_name: m.Animal__out_Animal_ParentOf___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_optional_traverse_after_mandatory_traverse(self):
        test_data = test_input_data.optional_traverse_after_mandatory_traverse()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_traverse_filter_and_output(self):
        test_data = test_input_data.traverse_filter_and_output()

        expected_match = '''
            SELECT
                Animal__out_Animal_ParentOf___1.name AS `parent_name`
            FROM (
                MATCH {{
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    class: Animal,
                    where: (((name = {wanted}) OR (alias CONTAINS {wanted}))),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_ParentOf')
            .filter{it, m -> ((it.name == $wanted) || it.alias.contains($wanted))}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                parent_name: m.Animal__out_Animal_ParentOf___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_name_or_alias_filter_on_interface_type(self):
        test_data = test_input_data.name_or_alias_filter_on_interface_type()

        expected_match = '''
            SELECT
                Animal__out_Entity_Related___1.name AS `related_entity`
            FROM (
                MATCH {{
                    as: Animal___1
                }}.out('Entity_Related') {{
                    class: Entity,
                    where: (((name = {wanted}) OR (alias CONTAINS {wanted}))),
                    as: Animal__out_Entity_Related___1
                }}
                RETURN $matches
            )
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Entity_Related')
            .filter{it, m -> ((it.name == $wanted) || it.alias.contains($wanted))}
            .as('Animal__out_Entity_Related___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                related_entity: m.Animal__out_Entity_Related___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_output_source_and_complex_output(self):
        test_data = test_input_data.output_source_and_complex_output()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> (it.name == $wanted)}
            .as('Animal___1')
            .out('Animal_ParentOf')
            .as('Animal__out_Animal_ParentOf___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                parent_name: m.Animal__out_Animal_ParentOf___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_filter_on_optional_variable_equality(self):
        # The operand in the @filter directive originates from an optional block.
        test_data = test_input_data.filter_on_optional_variable_equality()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_filter_on_optional_variable_name_or_alias(self):
        # The operand in the @filter directive originates from an optional block.
        test_data = test_input_data.filter_on_optional_variable_name_or_alias()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_filter_in_optional_block(self):
        test_data = test_input_data.filter_in_optional_block()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_between_filter_on_simple_scalar(self):
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a simple scalar (a String).
        test_data = test_input_data.between_filter_on_simple_scalar()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> ((it.name >= $lower) && (it.name <= $upper))}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_between_filter_on_date(self):
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a custom scalar (Date).
        test_data = test_input_data.between_filter_on_date()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> (
                (it.birthday >= Date.parse("yyyy-MM-dd", $lower)) &&
                (it.birthday <= Date.parse("yyyy-MM-dd", $upper))
            )}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                birthday: m.Animal___1.birthday.format("yyyy-MM-dd")
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_between_filter_on_datetime(self):
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a custom scalar (DateTime).
        test_data = test_input_data.between_filter_on_datetime()

        expected_match = '''
            SELECT
                Event___1.event_date.format("yyyy-MM-dd'T'HH:mm:ssX") AS `event_date`
            FROM (
                MATCH {{
                    class: Event,
                    where: ((
                        event_date BETWEEN
                            date({lower}, "yyyy-MM-dd'T'HH:mm:ssX")
                            AND date({upper}, "yyyy-MM-dd'T'HH:mm:ssX")
                    )),
                    as: Event___1
                }}
                RETURN $matches
            )
        '''
        expected_gremlin = '''
            g.V('@class', 'Event')
            .filter{it, m -> (
                (it.event_date >= Date.parse("yyyy-MM-dd'T'HH:mm:ssX", $lower)) &&
                (it.event_date <= Date.parse("yyyy-MM-dd'T'HH:mm:ssX", $upper))
            )}
            .as('Event___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                event_date: m.Event___1.event_date.format("yyyy-MM-dd'T'HH:mm:ssX")
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_between_lowering_on_simple_scalar(self):
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a simple scalar (a String).
        test_data = test_input_data.between_lowering_on_simple_scalar()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> ((it.name <= $upper) && (it.name >= $lower))}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                name: m.Animal___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_between_lowering_with_extra_filters(self):
        test_data = test_input_data.between_lowering_with_extra_filters()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_no_between_lowering_on_simple_scalar(self):
        test_data = test_input_data.no_between_lowering_on_simple_scalar()

        expected_match = '''
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
        '''
        expected_gremlin = '''
           g.V('@class', 'Animal')
           .filter{it, m -> (((it.name <= $upper) && (it.name >= $lower0)) && (it.name >= $lower1))}
           .as('Animal___1')
           .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
               name: m.Animal___1.name
           ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_complex_optional_variables(self):
        # The operands in the @filter directives originate from an optional block,
        # in addition to having very complex filtering logic.
        test_data = test_input_data.complex_optional_variables()

        expected_match = '''
            SELECT
                if(
                    eval("(Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)"),
                    Animal__out_Animal_ParentOf__out_Animal_FedAt___1.event_date
                        .format("yyyy-MM-dd'T'HH:mm:ssX"),
                    null
                ) AS `child_fed_at`,
                Animal__in_Animal_ParentOf__out_Animal_FedAt___1
                    .event_date.format("yyyy-MM-dd'T'HH:mm:ssX") AS `grandparent_fed_at`,
                if(
                    eval("(Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        IS NOT null)"),
                    Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        .event_date.format("yyyy-MM-dd'T'HH:mm:ssX"),
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
                        (Animal__out_Animal_ParentOf___1.out_Animal_FedAt IS null)
                        OR
                        (Animal__out_Animal_ParentOf___1.out_Animal_FedAt.size() = 0)
                    )
                    OR
                    (Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)
                )
                AND
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
            )
        '''
        expected_gremlin = '''
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
                        .format("yyyy-MM-dd'T'HH:mm:ssX") :
                    null
                ),
                grandparent_fed_at: m.Animal__in_Animal_ParentOf__out_Animal_FedAt___1.event_date
                    .format("yyyy-MM-dd'T'HH:mm:ssX"),
                other_parent_fed_at: (
                    (m.Animal__out_Animal_ParentOf__in_Animal_ParentOf
                        __out_Animal_FedAt___1 != null) ?
                    m.Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        .event_date.format("yyyy-MM-dd'T'HH:mm:ssX") :
                    null
                )
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_simple_fragment(self):
        test_data = test_input_data.simple_fragment()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_typename_output(self):
        test_data = test_input_data.typename_output()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_OfSpecies')
            .as('Animal__out_Animal_OfSpecies___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                base_cls: m.Animal___1['@class'],
                child_cls: m.Animal__out_Animal_OfSpecies___1['@class']
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_typename_filter(self):
        test_data = test_input_data.typename_filter()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Entity')
            .filter{it, m -> (it['@class'] == $base_cls)}
            .as('Entity___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                entity_name: m.Entity___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_simple_recurse(self):
        test_data = test_input_data.simple_recurse()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_recurse_within_fragment(self):
        test_data = test_input_data.recurse_within_fragment()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_filter_within_recurse(self):
        test_data = test_input_data.filter_within_recurse()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_recurse_with_immediate_type_coercion(self):
        test_data = test_input_data.recurse_with_immediate_type_coercion()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_recurse_with_immediate_type_coercion_and_filter(self):
        test_data = test_input_data.recurse_with_immediate_type_coercion_and_filter()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_in_collection_op_filter_with_variable(self):
        test_data = test_input_data.in_collection_op_filter_with_variable()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> $wanted.contains(it.name)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_in_collection_op_filter_with_tag(self):
        test_data = test_input_data.in_collection_op_filter_with_tag()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_ParentOf')
            .filter{it, m -> m.Animal___1.alias.contains(it.name)}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_in_collection_op_filter_with_optional_tag(self):
        test_data = test_input_data.in_collection_op_filter_with_optional_tag()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_intersects_op_filter_with_variable(self):
        test_data = test_input_data.intersects_op_filter_with_variable()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> (!it.alias.intersect($wanted).empty)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_intersects_op_filter_with_tag(self):
        test_data = test_input_data.intersects_op_filter_with_tag()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_ParentOf')
            .filter{it, m -> (!it.alias.intersect(m.Animal___1.alias).empty)}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_intersects_op_filter_with_optional_tag(self):
        test_data = test_input_data.intersects_op_filter_with_optional_tag()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_contains_op_filter_with_variable(self):
        test_data = test_input_data.contains_op_filter_with_variable()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> it.alias.contains($wanted)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_contains_op_filter_with_tag(self):
        test_data = test_input_data.contains_op_filter_with_tag()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
                .in('Animal_ParentOf')
                .filter{it, m -> it.alias.contains(m.Animal___1.name)}
                .as('Animal__in_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_contains_op_filter_with_optional_tag(self):
        test_data = test_input_data.contains_op_filter_with_optional_tag()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_has_substring_op_filter(self):
        test_data = test_input_data.has_substring_op_filter()

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> it.name.contains($wanted)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_has_substring_op_filter_with_variable(self):
        graphql_input = '''{
            Animal {
                name @filter(op_name: "has_substring", value: ["$wanted"])
                     @output(out_name: "animal_name")
            }
        }'''

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> it.name.contains($wanted)}
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'wanted': GraphQLString,
        }

        test_data = test_input_data.CommonTestData(
            graphql_input=graphql_input,
            expected_output_metadata=expected_output_metadata,
            expected_input_metadata=expected_input_metadata,
            type_equivalence_hints=None)

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_has_substring_op_filter_with_tag(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name") @tag(tag_name: "root_name")
                out_Animal_ParentOf {
                    name @filter(op_name: "has_substring", value: ["%root_name"])
                }
            }
        }'''

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Animal_ParentOf')
            .filter{it, m -> it.name.contains(m.Animal___1.name)}
            .as('Animal__out_Animal_ParentOf___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name
            ])}
        '''
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        test_data = test_input_data.CommonTestData(
            graphql_input=graphql_input,
            expected_output_metadata=expected_output_metadata,
            expected_input_metadata=expected_input_metadata,
            type_equivalence_hints=None)

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_has_substring_op_filter_with_optional_tag(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                in_Animal_ParentOf @optional {
                    name @tag(tag_name: "parent_name")
                }
                out_Animal_ParentOf {
                    name @filter(op_name: "has_substring", value: ["%parent_name"])
                }
            }
        }'''

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        test_data = test_input_data.CommonTestData(
            graphql_input=graphql_input,
            expected_output_metadata=expected_output_metadata,
            expected_input_metadata=expected_input_metadata,
            type_equivalence_hints=None)

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_has_edge_degree_op_filter(self):
        test_data = test_input_data.has_edge_degree_op_filter()

        expected_match = '''
            SELECT
                Animal___1.name AS `animal_name`,
                Animal__out_Animal_ParentOf___1.name AS `child_name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((
                        (({child_count} = 0) AND (out_Animal_ParentOf IS null)) OR
                        ((out_Animal_ParentOf IS NOT null) AND
                            (out_Animal_ParentOf.size() = {child_count}))
                    )),
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .filter{it, m -> (
                (($child_count == 0) && (it.out_Animal_ParentOf == null)) ||
                ((it.out_Animal_ParentOf != null) &&
                    (it.out_Animal_ParentOf.count() == $child_count))
            )}
            .as('Animal___1')
            .out('Animal_ParentOf')
            .as('Animal__out_Animal_ParentOf___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_name: m.Animal__out_Animal_ParentOf___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_has_edge_degree_op_filter_with_optional(self):
        test_data = test_input_data.has_edge_degree_op_filter_with_optional()

        expected_match = '''
            SELECT
                if(eval("(Species__in_Animal_OfSpecies__out_Animal_ParentOf___1 IS NOT null)"),
                   Species__in_Animal_OfSpecies__out_Animal_ParentOf___1.name,
                   null
                ) AS `child_name`,
                Species__in_Animal_OfSpecies___1.name AS `parent_name`,
                Species___1.name AS `species_name`
            FROM (
                MATCH {{
                    as: Species___1
                }}.in('Animal_OfSpecies') {{
                    class: Animal,
                    where: ((
                        (({child_count} = 0) AND (out_Animal_ParentOf IS null)) OR
                        ((out_Animal_ParentOf IS NOT null) AND
                            (out_Animal_ParentOf.size() = {child_count}))
                    )),
                    as: Species__in_Animal_OfSpecies___1
                }}.out('Animal_ParentOf') {{
                    optional: true,
                    as: Species__in_Animal_OfSpecies__out_Animal_ParentOf___1
                }}
                RETURN $matches
            )
            WHERE (
                (
                    (Species__in_Animal_OfSpecies___1.out_Animal_ParentOf IS null)
                    OR
                    (Species__in_Animal_OfSpecies___1.out_Animal_ParentOf.size() = 0)
                )
                OR
                (Species__in_Animal_OfSpecies__out_Animal_ParentOf___1 IS NOT null)
            )
        '''
        expected_gremlin = '''
            g.V('@class', 'Species')
            .as('Species___1')
            .in('Animal_OfSpecies')
            .filter{it, m -> (
                (($child_count == 0) && (it.out_Animal_ParentOf == null)) ||
                ((it.out_Animal_ParentOf != null) &&
                    (it.out_Animal_ParentOf.count() == $child_count))
            )}
            .as('Species__in_Animal_OfSpecies___1')
            .ifThenElse{it.out_Animal_ParentOf == null}{null}{it.out('Animal_ParentOf')}
            .as('Species__in_Animal_OfSpecies__out_Animal_ParentOf___1')
            .optional('Species__in_Animal_OfSpecies___1')
            .as('Species__in_Animal_OfSpecies___2')
            .back('Species___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_name: (
                    (m.Species__in_Animal_OfSpecies__out_Animal_ParentOf___1 != null) ?
                    m.Species__in_Animal_OfSpecies__out_Animal_ParentOf___1.name : null),
                parent_name: m.Species__in_Animal_OfSpecies___1.name,
                species_name: m.Species___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_has_edge_degree_op_filter_with_fold(self):
        test_data = test_input_data.has_edge_degree_op_filter_with_fold()

        expected_match = '''
            SELECT
                $Species__in_Animal_OfSpecies___1___out_Animal_ParentOf.name AS `child_names`,
                Species__in_Animal_OfSpecies___1.name AS `parent_name`,
                Species___1.name AS `species_name`
            FROM (
                MATCH {{
                    as: Species___1
                }}.in('Animal_OfSpecies') {{
                    class: Animal,
                    where: ((
                        (({child_count} = 0) AND (out_Animal_ParentOf IS null)) OR
                        ((out_Animal_ParentOf IS NOT null) AND
                            (out_Animal_ParentOf.size() = {child_count}))
                    )),
                    as: Species__in_Animal_OfSpecies___1
                }}
                RETURN $matches
            ) LET
                $Species__in_Animal_OfSpecies___1___out_Animal_ParentOf =
                    Species__in_Animal_OfSpecies___1.out("Animal_ParentOf").asList()
        '''
        expected_gremlin = '''
            g.V('@class', 'Species')
            .as('Species___1')
            .in('Animal_OfSpecies')
            .filter{it, m -> (
                (($child_count == 0) && (it.out_Animal_ParentOf == null)) ||
                ((it.out_Animal_ParentOf != null) &&
                    (it.out_Animal_ParentOf.count() == $child_count))
            )}
            .as('Species__in_Animal_OfSpecies___1')
            .back('Species___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                child_names: (
    (m.Species__in_Animal_OfSpecies___1.out_Animal_ParentOf == null) ?
    [] :
    (m.Species__in_Animal_OfSpecies___1.out_Animal_ParentOf.collect{entry -> entry.inV.next().name})
                ),
                parent_name: m.Species__in_Animal_OfSpecies___1.name,
                species_name: m.Species___1.name
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_simple_union(self):
        test_data = test_input_data.simple_union()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_filter_then_apply_fragment(self):
        test_data = test_input_data.filter_then_apply_fragment()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_filter_then_apply_fragment_with_multiple_traverses(self):
        test_data = test_input_data.filter_then_apply_fragment_with_multiple_traverses()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_filter_on_fragment_in_union(self):
        test_data = test_input_data.filter_on_fragment_in_union()

        expected_match = '''
            SELECT
                Species__out_Species_Eats___1.name AS `food_name`,
                Species___1.name AS `species_name`
            FROM (
                MATCH {{
                    as: Species___1
                }}.out('Species_Eats') {{
                    class: Food,
                    where: (((name = {wanted}) OR (alias CONTAINS {wanted}))),
                    as: Species__out_Species_Eats___1
                }}
                RETURN $matches
            )
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_optional_on_union(self):
        test_data = test_input_data.optional_on_union()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_gremlin_type_hints(self):
        graphql_input = '''{
            Animal {
                out_Entity_Related {
                    ... on Event {
                        name @output(out_name: "related_event")
                    }
                }
            }
        }'''
        type_equivalence_hints = {
            'Event': 'EventOrBirthEvent'
        }

        expected_match = '''
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .out('Entity_Related')
            .filter{it, m -> ['BirthEvent', 'Event'].contains(it['@class'])}
            .as('Animal__out_Entity_Related___1')
            .back('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                related_event: m.Animal__out_Entity_Related___1.name
            ])}
        '''
        expected_output_metadata = {
            'related_event': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        test_data = test_input_data.CommonTestData(
            graphql_input=graphql_input,
            expected_output_metadata=expected_output_metadata,
            expected_input_metadata=expected_input_metadata,
            type_equivalence_hints=type_equivalence_hints)

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_unnecessary_traversal_elimination(self):
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
        graphql_input = '''{
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
        }'''

        expected_match = '''
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
                        (
                            (Animal___1.out_Animal_ParentOf IS null)
                            OR
                            (Animal___1.out_Animal_ParentOf.size() = 0)
                        )
                        OR
                        (Animal__out_Animal_ParentOf___1 IS NOT null)
                    )
                    AND
                    (
                        (
                            (Animal___1.out_Animal_OfSpecies IS null)
                            OR
                            (Animal___1.out_Animal_OfSpecies.size() = 0)
                        )
                        OR
                        (Animal__out_Animal_OfSpecies___1 IS NOT null)
                    )
                )
                AND
                (
                    (
                        (Animal___1.out_Animal_FedAt IS null)
                        OR
                        (Animal___1.out_Animal_FedAt.size() = 0)
                    )
                    OR
                    (Animal__out_Animal_FedAt___1 IS NOT null)
                )
            )
        '''
        expected_gremlin = '''
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
        '''
        expected_output_metadata = {
            'child_uuid': OutputMetadata(type=GraphQLID, optional=True),
            'event_uuid': OutputMetadata(type=GraphQLID, optional=True),
            'species_uuid': OutputMetadata(type=GraphQLID, optional=True),
        }
        expected_input_metadata = {
            'uuid': GraphQLID,
        }

        test_data = test_input_data.CommonTestData(
            graphql_input=graphql_input,
            expected_output_metadata=expected_output_metadata,
            expected_input_metadata=expected_input_metadata,
            type_equivalence_hints=None)

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_fold_on_output_variable(self):
        test_data = test_input_data.fold_on_output_variable()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_fold_after_traverse(self):
        test_data = test_input_data.fold_after_traverse()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_fold_and_traverse(self):
        test_data = test_input_data.fold_and_traverse()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_fold_and_deep_traverse(self):
        test_data = test_input_data.fold_and_deep_traverse()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_traverse_and_fold_and_traverse(self):
        test_data = test_input_data.traverse_and_fold_and_traverse()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_multiple_outputs_in_same_fold(self):
        test_data = test_input_data.multiple_outputs_in_same_fold()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_multiple_outputs_in_same_fold_and_traverse(self):
        test_data = test_input_data.multiple_outputs_in_same_fold_and_traverse()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_multiple_folds(self):
        test_data = test_input_data.multiple_folds()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_multiple_folds_and_traverse(self):
        test_data = test_input_data.multiple_folds_and_traverse()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_fold_date_and_datetime_fields(self):
        test_data = test_input_data.fold_date_and_datetime_fields()

        expected_match = '''
            SELECT
                Animal___1.name AS `animal_name`,
                $Animal___1___out_Animal_ParentOf.birthday.format("yyyy-MM-dd")
                    AS `child_birthdays_list`,
                $Animal___1___out_Animal_FedAt.event_date.format("yyyy-MM-dd'T'HH:mm:ssX")
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
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                animal_name: m.Animal___1.name,
                child_birthdays_list: (
                    (m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.out_Animal_ParentOf.collect{
                            entry -> entry.inV.next().birthday.format("yyyy-MM-dd")
                        }
                    )
                ),
                fed_at_datetimes_list: (
                    (m.Animal___1.out_Animal_FedAt == null) ? [] : (
                        m.Animal___1.out_Animal_FedAt.collect{
                            entry -> entry.inV.next().event_date.format("yyyy-MM-dd'T'HH:mm:ssX")
                        }
                    )
                )
            ])}
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_coercion_to_union_base_type_inside_fold(self):
        # Given type_equivalence_hints = { Event: EventOrBirthEvent },
        # the coercion should be optimized away as a no-op.
        test_data = test_input_data.coercion_to_union_base_type_inside_fold()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_no_op_coercion_inside_fold(self):
        # The type where the coercion is applied is already Entity, so the coercion is a no-op.
        test_data = test_input_data.no_op_coercion_inside_fold()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_filter_within_fold_scope(self):
        test_data = test_input_data.filter_within_fold_scope()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_filter_on_fold_scope(self):
        test_data = test_input_data.filter_on_fold_scope()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_coercion_on_interface_within_fold_scope(self):
        test_data = test_input_data.coercion_on_interface_within_fold_scope()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_coercion_on_interface_within_fold_traversal(self):
        test_data = test_input_data.coercion_on_interface_within_fold_traversal()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_coercion_on_union_within_fold_scope(self):
        test_data = test_input_data.coercion_on_union_within_fold_scope()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_coercion_filters_and_multiple_outputs_within_fold_scope(self):
        test_data = test_input_data.coercion_filters_and_multiple_outputs_within_fold_scope()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_coercion_filters_and_multiple_outputs_within_fold_traversal(self):
        test_data = test_input_data.coercion_filters_and_multiple_outputs_within_fold_traversal()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_optional_and_traverse(self):
        test_data = test_input_data.optional_and_traverse()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_optional_and_traverse_after_filter(self):
        test_data = test_input_data.optional_and_traverse_after_filter()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_optional_and_deep_traverse(self):
        test_data = test_input_data.optional_and_deep_traverse()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_traverse_and_optional_and_traverse(self):
        test_data = test_input_data.traverse_and_optional_and_traverse()

        expected_match = '''
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal___1.name AS `animal_name`,
                    Animal__in_Animal_ParentOf___1.name AS `child_name`
                FROM (
                    MATCH {{
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_multiple_optional_traversals_with_starting_filter(self):
        test_data = test_input_data.multiple_optional_traversals_with_starting_filter()

        expected_match = '''
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
                                (out_Animal_ParentOf IS null)
                                OR
                                (out_Animal_ParentOf.size() = 0)
                            )
                            AND
                            (
                                (name LIKE ('%' + ({wanted} + '%')))
                                AND
                                (
                                    (in_Animal_ParentOf IS null)
                                    OR
                                    (in_Animal_ParentOf.size() = 0)
                                )
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
                    Animal__in_Animal_ParentOf___1.name AS `child_name`,
                    Animal__in_Animal_ParentOf__out_Animal_ParentOf___1.name
                        AS `spouse_and_self_name`
                FROM (
                    MATCH {{
                        class: Animal,
                        where: ((
                            (
                                (out_Animal_ParentOf IS null)
                                OR
                                (out_Animal_ParentOf.size() = 0)
                            )
                            AND
                            (name LIKE ('%' + ({wanted} + '%')))
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
            $optional__2 = (
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
        '''

        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_optional_traversal_and_optional_without_traversal(self):
        test_data = test_input_data.optional_traversal_and_optional_without_traversal()

        expected_match = '''
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
                            (
                                (out_Animal_ParentOf IS null)
                                OR
                                (out_Animal_ParentOf.size() = 0)
                            )
                            AND
                            (name LIKE ('%' + ({wanted} + '%')))
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
        '''

        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_coercion_on_interface_within_optional_traversal(self):
        test_data = test_input_data.coercion_on_interface_within_optional_traversal()

        expected_match = '''
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
        '''

        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_filter_on_optional_traversal_equality(self):
        test_data = test_input_data.filter_on_optional_traversal_equality()

        expected_match = '''
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal___1.name AS `animal_name`
                FROM (
                    MATCH {{
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
                        class: Event,
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
        '''

        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_filter_on_optional_traversal_name_or_alias(self):
        test_data = test_input_data.filter_on_optional_traversal_name_or_alias()

        expected_match = '''
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
        '''

        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_complex_optional_traversal_variables(self):
        test_data = test_input_data.complex_optional_traversal_variables()

        expected_match = '''
            SELECT EXPAND($result)
            LET
            $optional__0 = (
                SELECT
                    Animal__in_Animal_ParentOf__out_Animal_FedAt___1
                        .event_date.format("yyyy-MM-dd'T'HH:mm:ssX") AS `grandchild_fed_at`,
                    if(eval("(Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)"),
                        Animal__out_Animal_ParentOf__out_Animal_FedAt___1
                            .event_date.format("yyyy-MM-dd'T'HH:mm:ssX"),
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
                        .event_date.format("yyyy-MM-dd'T'HH:mm:ssX") AS `grandchild_fed_at`,
                    Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                        .event_date.format("yyyy-MM-dd'T'HH:mm:ssX") AS `other_child_fed_at`,
                    if(eval("(Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)"),
                        Animal__out_Animal_ParentOf__out_Animal_FedAt___1
                            .event_date.format("yyyy-MM-dd'T'HH:mm:ssX"),
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
        '''

        expected_gremlin = '''
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
                           .event_date.format("yyyy-MM-dd'T'HH:mm:ssX"),
                   other_child_fed_at: (
                       (m.Animal__out_Animal_ParentOf__in_Animal_ParentOf
                           __out_Animal_FedAt___1 != null) ?
                           m.Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                               .event_date.format("yyyy-MM-dd'T'HH:mm:ssX")
                           : null
                   ),
                   parent_fed_at: (
                       (m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 != null) ?
                           m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1
                               .event_date.format("yyyy-MM-dd'T'HH:mm:ssX")
                           : null
                   )
               ])
           }
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_simple_optional_recurse(self):
        test_data = test_input_data.simple_optional_recurse()

        expected_match = '''
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
        '''

        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_multiple_traverse_within_optional(self):
        test_data = test_input_data.multiple_traverse_within_optional()

        expected_match = '''
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
                        class: Event,
                        as: Animal__in_Animal_ParentOf__out_Animal_FedAt___1
                    }}
                    RETURN $matches
                )
            ),
            $result = UNIONALL($optional__0, $optional__1)
        '''

        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_optional_and_fold(self):
        test_data = test_input_data.optional_and_fold()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_fold_and_optional(self):
        test_data = test_input_data.fold_and_optional()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_optional_traversal_and_fold_traversal(self):
        test_data = test_input_data.optional_traversal_and_fold_traversal()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_fold_traversal_and_optional_traversal(self):
        test_data = test_input_data.fold_traversal_and_optional_traversal()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_between_lowering(self):
        test_data = test_input_data.between_lowering()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)

    def test_coercion_and_filter_with_tag(self):
        test_data = test_input_data.coercion_and_filter_with_tag()

        expected_match = '''
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
        '''
        expected_gremlin = '''
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
        '''

        check_test_data(self, test_data, expected_match, expected_gremlin)
