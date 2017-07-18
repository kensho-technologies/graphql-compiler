# Copyright 2017 Kensho Technologies, Inc.
"""End-to-end tests of the GraphQL compiler."""
import unittest

from graphql import GraphQLID, GraphQLList, GraphQLString, GraphQLUnionType

from ..compiler import OutputMetadata, compile_graphql_to_gremlin, compile_graphql_to_match
from ..exceptions import GraphQLCompilationError
from ..schema import GraphQLDate, GraphQLDateTime
from .test_helpers import compare_gremlin, compare_input_metadata, compare_match, get_schema


def check_test_data(test_case, graphql_input, expected_match, expected_gremlin,
                    expected_output_metadata, expected_input_metadata, type_equivalence_hints=None):
    """Assert that the GraphQL input generates all expected MATCH and Gremlin data."""
    result = compile_graphql_to_match(test_case.schema, graphql_input)
    compare_match(test_case, expected_match, result.query)
    test_case.assertEquals(expected_output_metadata, result.output_metadata)
    compare_input_metadata(test_case, expected_input_metadata, result.input_metadata)

    if type_equivalence_hints:
        # For test convenience, we accept the type equivalence hints in string form.
        # Here, we convert them to the required GraphQL types, generating meaningless
        # temporary names for the new interfaces.
        schema_based_type_equivalence_hints = {}
        name_format = 'temp_union_{}'
        name_counter = 0
        for key, value in type_equivalence_hints.iteritems():
            new_key = test_case.schema.get_type(key)

            new_value_name = name_format.format(name_counter)
            name_counter += 1

            # The 'resolve_type' argument below is only to side-step an unnecessary sanity-check
            # in the underlying GraphQL library. The library assumes we are going to use
            # its execution system, so it complains that we don't provide a means to resolve which
            # of the allowed types in the union is actually present. We don't care, because we
            # simply compile the GraphQL query directly to a database query.
            new_value = GraphQLUnionType(new_value_name,
                                         types=[test_case.schema.get_type(x) for x in value],
                                         resolve_type=lambda: None)
            schema_based_type_equivalence_hints[new_key] = new_value
    else:
        schema_based_type_equivalence_hints = None

    result = compile_graphql_to_gremlin(test_case.schema, graphql_input,
                                        type_equivalence_hints=schema_based_type_equivalence_hints)
    compare_gremlin(test_case, expected_gremlin, result.query)
    test_case.assertEquals(expected_output_metadata, result.output_metadata)
    compare_input_metadata(test_case, expected_input_metadata, result.input_metadata)


class CompilerTests(unittest.TestCase):
    def setUp(self):
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.schema = get_schema()

    def test_immediate_output(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
            }
        }'''

        expected_match = '''
            SELECT Animal___1.name AS `animal_name` FROM (
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
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

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
                SELECT Animal___1.name AS `animal_name` FROM (
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

            check_test_data(self, graphql_input, expected_match, expected_gremlin,
                            expected_output_metadata, expected_input_metadata)

    def test_traverse_and_output(self):
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf {
                    name @output(out_name: "parent_name")
                }
            }
        }'''

        expected_match = '''
            SELECT Animal__out_Animal_ParentOf___1.name AS `parent_name` FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
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
        expected_output_metadata = {
            'parent_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_optional_traverse_after_mandatory_traverse(self):
        graphql_input = '''{
            Animal {
                out_Animal_OfSpecies {
                    name @output(out_name: "species_name")
                }
                out_Animal_ParentOf @optional {
                    name @output(out_name: "child_name")
                }
            }
        }'''

        expected_match = '''
            SELECT if(eval("(Animal__out_Animal_ParentOf___1 IS NOT null)"),
                      Animal__out_Animal_ParentOf___1.name, null) AS `child_name`,
                   Animal__out_Animal_OfSpecies___1.name AS `species_name` FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_OfSpecies') {{
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
        expected_output_metadata = {
            'child_name': OutputMetadata(type=GraphQLString, optional=True),
            'species_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_traverse_filter_and_output(self):
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["$wanted"]) {
                    name @output(out_name: "parent_name")
                }
            }
        }'''

        expected_match = '''
            SELECT Animal__out_Animal_ParentOf___1.name AS `parent_name` FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_ParentOf') {{
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
        expected_output_metadata = {
            'parent_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'wanted': GraphQLString,
        }

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_output_source_and_complex_output(self):
        graphql_input = '''{
            Animal {
                name @filter(op_name: "=", value: ["$wanted"]) @output(out_name: "animal_name")
                out_Animal_ParentOf @output_source {
                    name @output(out_name: "parent_name")
                }
            }
        }'''

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
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'parent_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'wanted': GraphQLString,
        }

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_filter_on_optional_variable_equality(self):
        # The operand in the @filter directive originates from an optional block.
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Animal_ParentOf {
                    out_Animal_FedAt @optional {
                        name @tag(tag_name: "child_fed_at_event")
                    }
                }
                out_Animal_FedAt @output_source {
                    name @filter(op_name: "=", value: ["%child_fed_at_event"])
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
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_filter_on_optional_variable_name_or_alias(self):
        # The operand in the @filter directive originates from an optional block.
        graphql_input = '''{
            Animal {
                in_Animal_ParentOf @optional {
                    name @tag(tag_name: "parent_name")
                }
                out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["%parent_name"])
                                    @output_source {
                    name @output(out_name: "animal_name")
                }
            }
        }'''

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
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_filter_in_optional_block(self):
        graphql_input = '''{
            Animal {
                out_Animal_FedAt @optional {
                    name @filter(op_name: "=", value: ["$name"])
                    uuid @output(out_name: "uuid")
                }
            }
        }'''

        expected_match = '''
            SELECT
                if(eval("(Animal__out_Animal_FedAt___1 IS NOT null)"),
                   Animal__out_Animal_FedAt___1.uuid, null) AS `uuid`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_FedAt') {{
                    where: ((name = {name})),
                    optional: true,
                    as: Animal__out_Animal_FedAt___1
                }}
                RETURN $matches
            )
        '''
        expected_gremlin = '''
            g.V('@class', 'Animal')
            .as('Animal___1')
            .ifThenElse{it.out_Animal_FedAt == null}{null}{it.out('Animal_FedAt')}
            .filter{it, m -> ((it == null) || (it.name == $name))}
            .as('Animal__out_Animal_FedAt___1')
            .optional('Animal___1')
            .as('Animal___2')
            .transform{it, m -> new com.orientechnologies.orient.core.record.impl.ODocument([
                uuid: ((m.Animal__out_Animal_FedAt___1 != null) ?
                       m.Animal__out_Animal_FedAt___1.uuid : null)
            ])}
        '''
        expected_output_metadata = {
            'uuid': OutputMetadata(type=GraphQLID, optional=True),
        }
        expected_input_metadata = {
            'name': GraphQLString
        }

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_optional_traversal_edge_case(self):
        # Both Animal and out_Animal_ParentOf have an out_Animal_FedAt field,
        # ensure the correct such field is picked out.
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf @optional {
                    out_Animal_FedAt {
                        name @output(out_name: "name")
                    }
                }
            }
        }'''

        # Disabled until OrientDB fixes the limitation against traversing from an optional vertex.
        # Rather than compiling correctly, this raises an exception until the OrientDB limitation
        # is lifted.
        # For details, see https://github.com/orientechnologies/orientdb/issues/6788
        with self.assertRaises(GraphQLCompilationError):
            compile_graphql_to_match(self.schema, graphql_input)

        with self.assertRaises(GraphQLCompilationError):
            compile_graphql_to_gremlin(self.schema, graphql_input)

    def test_between_filter_on_simple_scalar(self):
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a simple scalar (a String).
        graphql_input = '''{
            Animal {
                name @filter(op_name: "between", value: ["$lower", "$upper"])
                     @output(out_name: "name")
            }
        }'''

        expected_match = '''
            SELECT
                Animal___1.name AS `name`
            FROM (
                MATCH {{
                    class: Animal,
                    where: (((name >= {lower}) AND (name <= {upper}))),
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
        expected_output_metadata = {
            'name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'lower': GraphQLString,
            'upper': GraphQLString,
        }

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_between_filter_on_date(self):
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a custom scalar (Date).
        graphql_input = '''{
            Animal {
                birthday @filter(op_name: "between", value: ["$lower", "$upper"])
                         @output(out_name: "birthday")
            }
        }'''

        expected_match = '''
            SELECT
                Animal___1.birthday.format("yyyy-MM-dd") AS `birthday`
            FROM (
                MATCH {{
                    class: Animal,
                    where: ((
                        (birthday >= date({lower}, "yyyy-MM-dd")) AND
                        (birthday <= date({upper}, "yyyy-MM-dd"))
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
        expected_output_metadata = {
            'birthday': OutputMetadata(type=GraphQLDate, optional=False),
        }
        expected_input_metadata = {
            'lower': GraphQLDate,
            'upper': GraphQLDate,
        }

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_between_filter_on_datetime(self):
        # The "between" filter emits different output depending on what the compared types are.
        # This test checks for correct code generation when the type is a custom scalar (DateTime).
        graphql_input = '''{
            Event {
                event_date @filter(op_name: "between", value: ["$lower", "$upper"])
                           @output(out_name: "event_date")
            }
        }'''

        expected_match = '''
            SELECT
                Event___1.event_date.format("yyyy-MM-dd'T'HH:mm:ssX") AS `event_date`
            FROM (
                MATCH {{
                    class: Event,
                    where: ((
                        (event_date >= date({lower}, "yyyy-MM-dd'T'HH:mm:ssX")) AND
                        (event_date <= date({upper}, "yyyy-MM-dd'T'HH:mm:ssX"))
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
        expected_output_metadata = {
            'event_date': OutputMetadata(type=GraphQLDateTime, optional=False),
        }
        expected_input_metadata = {
            'lower': GraphQLDateTime,
            'upper': GraphQLDateTime,
        }

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_complex_optional_variables(self):
        # The operands in the @filter directives originate from an optional block,
        # in addition to having very complex filtering logic.
        graphql_input = '''{
            Animal {
                name @filter(op_name: "=", value: ["$animal_name"])
                out_Animal_ParentOf {
                    out_Animal_FedAt @optional {
                        name @tag(tag_name: "child_fed_at_event")
                        event_date @tag(tag_name: "child_fed_at")
                                   @output(out_name: "child_fed_at")
                    }
                    in_Animal_ParentOf {
                        out_Animal_FedAt @optional {
                            event_date @tag(tag_name: "other_parent_fed_at")
                                       @output(out_name: "other_parent_fed_at")
                        }
                    }
                }
                in_Animal_ParentOf {
                    out_Animal_FedAt {
                        name @filter(op_name: "=", value: ["%child_fed_at_event"])
                        event_date @output(out_name: "grandparent_fed_at")
                                   @filter(op_name: "between",
                                           value: ["%other_parent_fed_at", "%child_fed_at"])
                    }
                }
            }
        }'''

        expected_match = '''
SELECT
    if(
        eval("(Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)"),
        Animal__out_Animal_ParentOf__out_Animal_FedAt___1.event_date
            .format("yyyy-MM-dd'T'HH:mm:ssX"),
        null
    ) AS `child_fed_at`,
    Animal__in_Animal_ParentOf__out_Animal_FedAt___1.event_date.format("yyyy-MM-dd'T'HH:mm:ssX")
        AS `grandparent_fed_at`,
    if(
        eval("(Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1 IS NOT null)"),
        Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1.event_date
            .format("yyyy-MM-dd'T'HH:mm:ssX"),
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
        class: Animal,
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
                ($matched.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS null) OR
                (name = $matched.Animal__out_Animal_ParentOf__out_Animal_FedAt___1.name)
            ) AND ((
            ($matched.Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1
                IS null) OR
            (event_date >= $matched.
                Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1.event_date)
            ) AND (
                ($matched.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 IS null) OR
                (event_date <=
                    $matched.Animal__out_Animal_ParentOf__out_Animal_FedAt___1.event_date)
            ))
        )),
        as: Animal__in_Animal_ParentOf__out_Animal_FedAt___1
    }}
    RETURN $matches
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
            ) && ((
                (m.Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1 == null) ||
                (it.event_date >=
                 m.Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1.event_date)
            ) && (
                (m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1 == null) ||
                (it.event_date <= m.Animal__out_Animal_ParentOf__out_Animal_FedAt___1.event_date)
            ))
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
        (m.Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1 != null) ?
        m.Animal__out_Animal_ParentOf__in_Animal_ParentOf__out_Animal_FedAt___1.event_date
            .format("yyyy-MM-dd'T'HH:mm:ssX") :
        null
    )
])}
        '''
        expected_output_metadata = {
            'child_fed_at': OutputMetadata(type=GraphQLDateTime, optional=True),
            'other_parent_fed_at': OutputMetadata(type=GraphQLDateTime, optional=True),
            'grandparent_fed_at': OutputMetadata(type=GraphQLDateTime, optional=False),
        }
        expected_input_metadata = {
            'animal_name': GraphQLString,
        }

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_simple_fragment(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Entity_Related {
                    ... on Animal {
                        name @output(out_name: "related_animal_name")
                        out_Animal_OfSpecies {
                            name @output(out_name: "related_animal_species")
                        }
                    }
                }
            }
        }'''

        expected_match = '''
SELECT
    Animal___1.name AS `animal_name`,
    Animal__out_Entity_Related___1.name AS `related_animal_name`,
    Animal__out_Entity_Related__out_Animal_OfSpecies___1.name AS `related_animal_species`
FROM (
    MATCH {{
        class: Animal,
        as: Animal___1
    }}.out('Entity_Related') {{
        class: Animal,
        as: Animal__out_Entity_Related___1
    }}.out('Animal_OfSpecies') {{
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
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'related_animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'related_animal_species': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_typename_output(self):
        graphql_input = '''{
            Animal {
                __typename @output(out_name: "base_cls")
                out_Animal_OfSpecies {
                    __typename @output(out_name: "child_cls")
                }
            }
        }'''

        expected_match = '''
            SELECT
                Animal___1.@class AS `base_cls`,
                Animal__out_Animal_OfSpecies___1.@class AS `child_cls`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.out('Animal_OfSpecies') {{
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
        expected_output_metadata = {
            'base_cls': OutputMetadata(type=GraphQLString, optional=False),
            'child_cls': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_typename_filter(self):
        graphql_input = '''{
            Entity {
                __typename @filter(op_name: "=", value: ["$base_cls"])
                name @output(out_name: "entity_name")
            }
        }'''

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
        expected_output_metadata = {
            'entity_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'base_cls': GraphQLString,
        }

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_simple_recurse(self):
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf @recurse(depth: 1) {
                    name @output(out_name: "relation_name")
                }
            }
        }'''

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
        expected_output_metadata = {
            'relation_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_recurse_within_fragment(self):
        graphql_input = '''{
            Food {
                name @output(out_name: "food_name")
                in_Entity_Related {
                    ... on Animal {
                        name @output(out_name: "animal_name")
                        out_Animal_ParentOf @recurse(depth: 3) {
                            name @output(out_name: "relation_name")
                        }
                    }
                }
            }
        }'''

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
        expected_output_metadata = {
            'food_name': OutputMetadata(type=GraphQLString, optional=False),
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'relation_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_filter_within_recurse(self):
        graphql_input = '''{
            Animal {
                out_Animal_ParentOf @recurse(depth: 3) {
                    name @output(out_name: "relation_name")
                    color @filter(op_name: "=", value: ["$wanted"])
                }
            }
        }'''

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
        expected_output_metadata = {
            'relation_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'wanted': GraphQLString,
        }

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_recurse_with_immediate_type_coercion(self):
        graphql_input = '''{
            Animal {
                in_Entity_Related @recurse(depth: 4) {
                    ... on Animal {
                        name @output(out_name: "name")
                    }
                }
            }
        }'''

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
        expected_output_metadata = {
            'name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_recurse_with_immediate_type_coercion_and_filter(self):
        graphql_input = '''{
            Animal {
                in_Entity_Related @recurse(depth: 4) {
                    ... on Animal {
                        name @output(out_name: "name")
                        color @filter(op_name: "=", value: ["$color"])
                    }
                }
            }
        }'''

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
        expected_output_metadata = {
            'name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'color': GraphQLString,
        }

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_in_collection_op_filter_with_variable(self):
        graphql_input = '''{
            Animal {
                name @filter(op_name: "in_collection", value: ["$wanted"])
                     @output(out_name: "animal_name")
            }
        }'''

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
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'wanted': GraphQLList(GraphQLString),
        }

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_in_collection_op_filter_with_tag(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                alias @tag(tag_name: "aliases")
                out_Animal_ParentOf {
                    name @filter(op_name: "in_collection", value: ["%aliases"])
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
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_in_collection_op_filter_with_optional_tag(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                in_Animal_ParentOf @optional {
                    alias @tag(tag_name: "parent_aliases")
                }
                out_Animal_ParentOf {
                    name @filter(op_name: "in_collection", value: ["%parent_aliases"])
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
                    where: (
                        (($matched.Animal__in_Animal_ParentOf___1 IS null)
                         OR ($matched.Animal__in_Animal_ParentOf___1.alias CONTAINS name))
                    ),
                    as: Animal__out_Animal_ParentOf___1
                }}
                RETURN $matches
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
        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

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

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

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

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

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

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_simple_union(self):
        graphql_input = '''{
            Species {
                name @output(out_name: "species_name")
                out_Species_Eats {
                    ... on Food {
                        name @output(out_name: "food_name")
                    }
                }
            }
        }'''

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
        expected_output_metadata = {
            'food_name': OutputMetadata(type=GraphQLString, optional=False),
            'species_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_filter_on_fragment_in_union(self):
        graphql_input = '''{
            Species {
                name @output(out_name: "species_name")
                out_Species_Eats {
                    ... on Food @filter(op_name: "name_or_alias", value: ["$wanted"]) {
                        name @output(out_name: "food_name")
                    }
                }
            }
        }'''

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
        expected_output_metadata = {
            'food_name': OutputMetadata(type=GraphQLString, optional=False),
            'species_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {
            'wanted': GraphQLString,
        }

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_optional_on_union(self):
        graphql_input = '''{
            Species {
                name @output(out_name: "species_name")
                out_Species_Eats @optional {
                    ... on Food {
                        name @output(out_name: "food_name")
                    }
                }
            }
        }'''

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
                    where: ((@this INSTANCEOF 'Food')),
                    optional: true,
                    as: Species__out_Species_Eats___1
                }}
                RETURN $matches
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
        expected_output_metadata = {
            'food_name': OutputMetadata(type=GraphQLString, optional=True),
            'species_name': OutputMetadata(type=GraphQLString, optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

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
            'Event': {'Event', 'BirthEvent'}
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

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata,
                        type_equivalence_hints=type_equivalence_hints)

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

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_fold_on_output_variable(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Animal_ParentOf @fold {
                    name @output(out_name: "child_names_list")
                }
            }
        }'''

        expected_match = '''
            SELECT
                Animal___1.name AS `animal_name`,
                Animal___1.out("Animal_ParentOf").name AS `child_names_list`
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
                animal_name: m.Animal___1.name,
                child_names_list: (
                    (m.Animal___1.out_Animal_ParentOf == null) ? [] : (
                        m.Animal___1.out_Animal_ParentOf.collect{entry -> entry.inV.next().name}
                    )
                )
            ])}
        '''

        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'child_names_list': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_fold_after_traverse(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                in_Animal_ParentOf {
                    out_Animal_ParentOf @fold {
                        name @output(out_name: "sibling_and_self_names_list")
                    }
                }
            }
        }'''

        expected_match = '''
            SELECT
                Animal___1.name AS `animal_name`,
                Animal__in_Animal_ParentOf___1.out("Animal_ParentOf").name
                    AS `sibling_and_self_names_list`
            FROM (
                MATCH {{
                    class: Animal,
                    as: Animal___1
                }}.in('Animal_ParentOf') {{
                    as: Animal__in_Animal_ParentOf___1
                }}
                RETURN $matches
            )
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

        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'sibling_and_self_names_list': OutputMetadata(
                type=GraphQLList(GraphQLString), optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_multiple_outputs_in_same_fold(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Animal_ParentOf @fold {
                    name @output(out_name: "child_names_list")
                    uuid @output(out_name: "child_uuids_list")
                }
            }
        }'''

        expected_match = '''
            SELECT
                Animal___1.name AS `animal_name`,
                Animal___1.out("Animal_ParentOf").name AS `child_names_list`,
                Animal___1.out("Animal_ParentOf").uuid AS `child_uuids_list`
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
                )
            ])}
        '''

        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'child_names_list': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
            'child_uuids_list': OutputMetadata(type=GraphQLList(GraphQLID), optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_multiple_folds(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Animal_ParentOf @fold {
                    name @output(out_name: "child_names_list")
                    uuid @output(out_name: "child_uuids_list")
                }
                in_Animal_ParentOf @fold {
                    name @output(out_name: "parent_names_list")
                    uuid @output(out_name: "parent_uuids_list")
                }
            }
        }'''

        expected_match = '''
            SELECT
                Animal___1.name AS `animal_name`,
                Animal___1.out("Animal_ParentOf").name AS `child_names_list`,
                Animal___1.out("Animal_ParentOf").uuid AS `child_uuids_list`,
                Animal___1.in("Animal_ParentOf").name AS `parent_names_list`,
                Animal___1.in("Animal_ParentOf").uuid AS `parent_uuids_list`
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

        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'child_names_list': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
            'child_uuids_list': OutputMetadata(type=GraphQLList(GraphQLID), optional=False),
            'parent_names_list': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
            'parent_uuids_list': OutputMetadata(type=GraphQLList(GraphQLID), optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)

    def test_fold_date_and_datetime_fields(self):
        graphql_input = '''{
            Animal {
                name @output(out_name: "animal_name")
                out_Animal_ParentOf @fold {
                    birthday @output(out_name: "child_birthdays_list")
                }
                out_Animal_FedAt @fold {
                    event_date @output(out_name: "fed_at_datetimes_list")
                }
            }
        }'''

        expected_match = '''
            SELECT
                Animal___1.name AS `animal_name`,
                Animal___1.out("Animal_ParentOf").birthday.format("yyyy-MM-dd")
                    AS `child_birthdays_list`,
                Animal___1.out("Animal_FedAt").event_date.format("yyyy-MM-dd'T'HH:mm:ssX")
                    AS `fed_at_datetimes_list`
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

        expected_output_metadata = {
            'animal_name': OutputMetadata(type=GraphQLString, optional=False),
            'child_birthdays_list': OutputMetadata(type=GraphQLList(GraphQLDate), optional=False),
            'fed_at_datetimes_list': OutputMetadata(
                type=GraphQLList(GraphQLDateTime), optional=False),
        }
        expected_input_metadata = {}

        check_test_data(self, graphql_input, expected_match, expected_gremlin,
                        expected_output_metadata, expected_input_metadata)
