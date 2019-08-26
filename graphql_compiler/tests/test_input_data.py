# Copyright 2017-present Kensho Technologies, LLC.
"""Common GraphQL test inputs and expected outputs."""

from collections import namedtuple

from graphql import GraphQLID, GraphQLInt, GraphQLList, GraphQLString

from ..compiler.compiler_frontend import OutputMetadata
from ..schema import GraphQLDate, GraphQLDateTime, GraphQLDecimal


CommonTestData = namedtuple(
    'CommonTestData',
    (
        'graphql_input',
        'expected_output_metadata',
        'expected_input_metadata',
        'type_equivalence_hints',
    ))


def immediate_output():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def immediate_output_custom_scalars():  # noqa: D103
    graphql_input = '''{
        Animal {
            birthday @output(out_name: "birthday")
            net_worth @output(out_name: "net_worth")
        }
    }'''
    expected_output_metadata = {
        'birthday': OutputMetadata(type=GraphQLDate, optional=False),
        'net_worth': OutputMetadata(type=GraphQLDecimal, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def immediate_output_with_custom_scalar_filter():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            net_worth @filter(op_name: ">=", value: ["$min_worth"])
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'min_worth': GraphQLDecimal,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def colocated_filter_and_tag():  # noqa: D103
    graphql_input = '''{
        Animal {
            out_Entity_Related {
                name @output(out_name: "related_name")
                     @tag(tag_name: "name")
                alias @filter(op_name: "contains", value: ["%name"])
            }
        }
    }'''
    expected_output_metadata = {
        'related_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def colocated_out_of_order_filter_and_tag():  # noqa: D103
    graphql_input = '''{
        Animal {
            out_Entity_Related {
                alias @filter(op_name: "contains", value: ["%name"])
                name @output(out_name: "related_name")
                     @tag(tag_name: "name")
            }
        }
    }'''
    expected_output_metadata = {
        'related_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def multiple_filters():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @filter(op_name: ">=", value: ["$lower_bound"])
                 @filter(op_name: "<", value: ["$upper_bound"])
                 @output(out_name: "animal_name")
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'lower_bound': GraphQLString,
        'upper_bound': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def traverse_and_output():  # noqa: D103
    graphql_input = '''{
        Animal {
            out_Animal_ParentOf {
                name @output(out_name: "parent_name")
            }
        }
    }'''
    expected_output_metadata = {
        'parent_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def optional_traverse_after_mandatory_traverse():  # noqa: D103
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
    expected_output_metadata = {
        'species_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_name': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def traverse_filter_and_output():  # noqa: D103
    graphql_input = '''{
        Animal {
            out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["$wanted"]) {
                name @output(out_name: "parent_name")
            }
        }
    }'''
    expected_output_metadata = {
        'parent_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'wanted': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def name_or_alias_filter_on_interface_type():  # noqa: D103
    graphql_input = '''{
        Animal {
            out_Entity_Related @filter(op_name: "name_or_alias", value: ["$wanted"]) {
                name @output(out_name: "related_entity")
            }
        }
    }'''
    expected_output_metadata = {
        'related_entity': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'wanted': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def output_source_and_complex_output():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @filter(op_name: "=", value: ["$wanted"]) @output(out_name: "animal_name")
            out_Animal_ParentOf @output_source {
                name @output(out_name: "parent_name")
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'parent_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'wanted': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_on_optional_variable_equality():  # noqa: D103
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
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_on_optional_variable_name_or_alias():  # noqa: D103
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
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_in_optional_block():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_ParentOf @optional {
                name @filter(op_name: "=", value: ["$name"])
                     @output(out_name: "parent_name")
                uuid @output(out_name: "uuid")
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'parent_name': OutputMetadata(type=GraphQLString, optional=True),
        'uuid': OutputMetadata(type=GraphQLID, optional=True),
    }
    expected_input_metadata = {
        'name': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_in_optional_and_count():  # noqa: D103
    graphql_input = '''{
        Species {
            name @output(out_name: "species_name")

            in_Animal_OfSpecies @optional {
                name @filter(op_name: "=", value: ["$animal_name"])
            }

            in_Species_Eats @fold {
                _x_count @filter(op_name: ">=", value: ["$predators"])
            }
        }
    }'''
    expected_output_metadata = {
        'species_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'animal_name': GraphQLString,
        'predators': GraphQLInt,
    }
    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def between_filter_on_simple_scalar():  # noqa: D103
    # The "between" filter emits different output depending on what the compared types are.
    # This test checks for correct code generation when the type is a simple scalar (a String).
    graphql_input = '''{
        Animal {
            name @filter(op_name: "between", value: ["$lower", "$upper"])
                 @output(out_name: "name")
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'lower': GraphQLString,
        'upper': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def between_filter_on_date():  # noqa: D103
    # The "between" filter emits different output depending on what the compared types are.
    # This test checks for correct code generation when the type is a custom scalar (Date).
    graphql_input = '''{
        Animal {
            birthday @filter(op_name: "between", value: ["$lower", "$upper"])
                     @output(out_name: "birthday")
        }
    }'''
    expected_output_metadata = {
        'birthday': OutputMetadata(type=GraphQLDate, optional=False),
    }
    expected_input_metadata = {
        'lower': GraphQLDate,
        'upper': GraphQLDate,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def between_filter_on_datetime():  # noqa: D103
    # The "between" filter emits different output depending on what the compared types are.
    # This test checks for correct code generation when the type is a custom scalar (DateTime).
    graphql_input = '''{
        Event {
            event_date @filter(op_name: "between", value: ["$lower", "$upper"])
                       @output(out_name: "event_date")
        }
    }'''
    expected_output_metadata = {
        'event_date': OutputMetadata(type=GraphQLDateTime, optional=False),
    }
    expected_input_metadata = {
        'lower': GraphQLDateTime,
        'upper': GraphQLDateTime,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def between_lowering_on_simple_scalar():  # noqa: D103
    # The "between" filter emits different output depending on what the compared types are.
    # This test checks for correct code generation when the type is a simple scalar (a String).
    graphql_input = '''{
        Animal {
            name @filter(op_name: "<=", value: ["$upper"])
                 @filter(op_name: ">=", value: ["$lower"])
                 @output(out_name: "name")
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'lower': GraphQLString,
        'upper': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def between_lowering_with_extra_filters():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @filter(op_name: "<=", value: ["$upper"])
                 @filter(op_name: "has_substring", value: ["$substring"])
                 @filter(op_name: "in_collection", value: ["$fauna"])
                 @filter(op_name: ">=", value: ["$lower"])
                 @output(out_name: "name")
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'lower': GraphQLString,
        'upper': GraphQLString,
        'substring': GraphQLString,
        'fauna': GraphQLList(GraphQLString)
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def no_between_lowering_on_simple_scalar():  # noqa: D103
    # The following filters do not get lowered to a BETWEEN clause.
    # This is because the compiler has no way to decide which lower bound to use.
    # The parameters are not provided to the compiler.
    graphql_input = '''{
        Animal {
            name @filter(op_name: "<=", value: ["$upper"])
                 @filter(op_name: ">=", value: ["$lower0"])
                 @filter(op_name: ">=", value: ["$lower1"])
                 @output(out_name: "name")
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'lower0': GraphQLString,
        'lower1': GraphQLString,
        'upper': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def complex_optional_variables():  # noqa: D103
    # The operands in the @filter directives originate from an optional block.
    graphql_input = '''{
        Animal {
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
    expected_output_metadata = {
        'child_fed_at': OutputMetadata(type=GraphQLDateTime, optional=True),
        'other_parent_fed_at': OutputMetadata(type=GraphQLDateTime, optional=True),
        'grandparent_fed_at': OutputMetadata(type=GraphQLDateTime, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def complex_optional_variables_with_starting_filter():  # noqa: D103
    # The operands in the @filter directives originate from an optional block.
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
    expected_output_metadata = {
        'child_fed_at': OutputMetadata(type=GraphQLDateTime, optional=True),
        'other_parent_fed_at': OutputMetadata(type=GraphQLDateTime, optional=True),
        'grandparent_fed_at': OutputMetadata(type=GraphQLDateTime, optional=False),
    }
    expected_input_metadata = {
        'animal_name': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def simple_fragment():  # noqa: D103
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
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'related_animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'related_animal_species': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def simple_union():  # noqa: D103
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
    expected_output_metadata = {
        'species_name': OutputMetadata(type=GraphQLString, optional=False),
        'food_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_then_apply_fragment():  # noqa: D103
    graphql_input = '''{
        Species {
            name @filter(op_name: "in_collection", value: ["$species"])
                 @output(out_name: "species_name")
            out_Species_Eats {
                ... on Food {
                    name @output(out_name: "food_name")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'species_name': OutputMetadata(type=GraphQLString, optional=False),
        'food_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'species': GraphQLList(GraphQLString),
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_then_apply_fragment_with_multiple_traverses():  # noqa: D103
    graphql_input = '''{
        Species {
            name @filter(op_name: "in_collection", value: ["$species"])
                 @output(out_name: "species_name")
            out_Species_Eats {
                ... on Food {
                    name @output(out_name: "food_name")
                    out_Entity_Related {
                        name @output(out_name: "entity_related_to_food")
                    }
                    in_Entity_Related {
                        name @output(out_name: "food_related_to_entity")
                    }
                }
            }
        }
    }'''
    expected_output_metadata = {
        'species_name': OutputMetadata(type=GraphQLString, optional=False),
        'food_name': OutputMetadata(type=GraphQLString, optional=False),
        'entity_related_to_food': OutputMetadata(type=GraphQLString, optional=False),
        'food_related_to_entity': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'species': GraphQLList(GraphQLString),
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_on_fragment_in_union():  # noqa: D103
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
    expected_output_metadata = {
        'species_name': OutputMetadata(type=GraphQLString, optional=False),
        'food_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'wanted': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def optional_on_union():  # noqa: D103
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
    expected_output_metadata = {
        'species_name': OutputMetadata(type=GraphQLString, optional=False),
        'food_name': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def typename_output():  # noqa: D103
    graphql_input = '''{
        Animal {
            __typename @output(out_name: "base_cls")
            out_Animal_OfSpecies {
                __typename @output(out_name: "child_cls")
            }
        }
    }'''
    expected_output_metadata = {
        'base_cls': OutputMetadata(type=GraphQLString, optional=False),
        'child_cls': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def typename_filter():  # noqa: D103
    graphql_input = '''{
        Entity {
            __typename @filter(op_name: "=", value: ["$base_cls"])
            name @output(out_name: "entity_name")
        }
    }'''
    expected_output_metadata = {
        'entity_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'base_cls': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def simple_recurse():  # noqa: D103
    graphql_input = '''{
        Animal {
            out_Animal_ParentOf @recurse(depth: 1) {
                name @output(out_name: "relation_name")
            }
        }
    }'''
    expected_output_metadata = {
        'relation_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def traverse_then_recurse():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_ImportantEvent {
                ... on Event {
                    name @output(out_name: "important_event")
                }
            }
            out_Animal_ParentOf @recurse(depth: 2) {
                name @output(out_name: "ancestor_name")
            }
        }
    }'''

    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'important_event': OutputMetadata(type=GraphQLString, optional=False),
        'ancestor_name': OutputMetadata(type=GraphQLString, optional=False),
    }

    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_then_traverse_and_recurse():  # noqa: D103
    graphql_input = '''{
        Animal @filter(op_name: "name_or_alias", value: ["$animal_name_or_alias"]) {
            name @output(out_name: "animal_name")
            out_Animal_ImportantEvent {
                ... on Event {
                    name @output(out_name: "important_event")
                }
            }
            out_Animal_ParentOf @recurse(depth: 2) {
                name @output(out_name: "ancestor_name")
            }
        }
    }'''

    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'important_event': OutputMetadata(type=GraphQLString, optional=False),
        'ancestor_name': OutputMetadata(type=GraphQLString, optional=False),
    }

    expected_input_metadata = {
        'animal_name_or_alias': GraphQLString
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def two_consecutive_recurses():  # noqa: D103
    graphql_input = '''{
        Animal @filter(op_name: "name_or_alias", value: ["$animal_name_or_alias"]) {
            name @output(out_name: "animal_name")
            out_Animal_ImportantEvent {
                ... on Event {
                    name @output(out_name: "important_event")
                }
            }
            out_Animal_ParentOf @recurse(depth: 2) {
                name @output(out_name: "ancestor_name")
            }
            in_Animal_ParentOf @recurse(depth: 2) {
                name @output(out_name: "descendent_name")
            }
        }
    }'''

    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'important_event': OutputMetadata(type=GraphQLString, optional=False),
        'ancestor_name': OutputMetadata(type=GraphQLString, optional=False),
        'descendent_name': OutputMetadata(type=GraphQLString, optional=False)
    }

    expected_input_metadata = {
        'animal_name_or_alias': GraphQLString
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def recurse_within_fragment():  # noqa: D103
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
    expected_output_metadata = {
        'food_name': OutputMetadata(type=GraphQLString, optional=False),
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'relation_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_within_recurse():  # noqa: D103
    graphql_input = '''{
        Animal {
            out_Animal_ParentOf @recurse(depth: 3) {
                name @output(out_name: "relation_name")
                color @filter(op_name: "=", value: ["$wanted"])
            }
        }
    }'''
    expected_output_metadata = {
        'relation_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'wanted': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def recurse_with_immediate_type_coercion():  # noqa: D103
    graphql_input = '''{
        Animal {
            in_Entity_Related @recurse(depth: 4) {
                ... on Animal {
                    name @output(out_name: "name")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def recurse_with_immediate_type_coercion_and_filter():  # noqa: D103
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
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'color': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def in_collection_op_filter_with_variable():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @filter(op_name: "in_collection", value: ["$wanted"])
                 @output(out_name: "animal_name")
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'wanted': GraphQLList(GraphQLString)
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def in_collection_op_filter_with_tag():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            alias @tag(tag_name: "aliases")
            out_Animal_ParentOf {
                name @filter(op_name: "in_collection", value: ["%aliases"])
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def in_collection_op_filter_with_optional_tag():  # noqa: D103
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
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def not_in_collection_op_filter_with_variable():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @filter(op_name: "not_in_collection", value: ["$wanted"])
                 @output(out_name: "animal_name")
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'wanted': GraphQLList(GraphQLString)
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def not_in_collection_op_filter_with_tag():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            alias @tag(tag_name: "aliases")
            out_Animal_ParentOf {
                name @filter(op_name: "not_in_collection", value: ["%aliases"])
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def not_in_collection_op_filter_with_optional_tag():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @optional {
                alias @tag(tag_name: "parent_aliases")
            }
            out_Animal_ParentOf {
                name @filter(op_name: "not_in_collection", value: ["%parent_aliases"])
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def intersects_op_filter_with_variable():  # noqa: D103
    graphql_input = '''{
        Animal {
            alias @filter(op_name: "intersects", value: ["$wanted"])
            name @output(out_name: "animal_name")
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'wanted': GraphQLList(GraphQLString)
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def intersects_op_filter_with_tag():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            alias @tag(tag_name: "aliases")
            out_Animal_ParentOf {
                alias @filter(op_name: "intersects", value: ["%aliases"])
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def intersects_op_filter_with_optional_tag():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @optional {
                alias @tag(tag_name: "parent_aliases")
            }
            out_Animal_ParentOf {
                alias @filter(op_name: "intersects", value: ["%parent_aliases"])
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def contains_op_filter_with_variable():  # noqa: D103
    graphql_input = '''{
        Animal {
            alias @filter(op_name: "contains", value: ["$wanted"])
            name @output(out_name: "animal_name")
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'wanted': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def contains_op_filter_with_tag():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name") @tag(tag_name: "name")
            in_Animal_ParentOf {
                alias @filter(op_name: "contains", value: ["%name"])
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def contains_op_filter_with_optional_tag():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @optional {
                name @tag(tag_name: "parent_name")
            }
            out_Animal_ParentOf {
                alias @filter(op_name: "contains", value: ["%parent_name"])
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def not_contains_op_filter_with_variable():  # noqa: D103
    graphql_input = '''{
        Animal {
            alias @filter(op_name: "not_contains", value: ["$wanted"])
            name @output(out_name: "animal_name")
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'wanted': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def not_contains_op_filter_with_tag():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name") @tag(tag_name: "name")
            in_Animal_ParentOf {
                alias @filter(op_name: "not_contains", value: ["%name"])
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def not_contains_op_filter_with_optional_tag():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @optional {
                name @tag(tag_name: "parent_name")
            }
            out_Animal_ParentOf {
                alias @filter(op_name: "not_contains", value: ["%parent_name"])
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def ends_with_op_filter():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @filter(op_name: "ends_with", value: ["$wanted"])
                 @output(out_name: "animal_name")
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'wanted': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def starts_with_op_filter():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @filter(op_name: "starts_with", value: ["$wanted"])
                 @output(out_name: "animal_name")
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'wanted': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def has_substring_op_filter():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @filter(op_name: "has_substring", value: ["$wanted"])
                 @output(out_name: "animal_name")
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'wanted': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def has_substring_op_filter_with_optional_tag():  # noqa: D103
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
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def has_edge_degree_op_filter():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @filter(op_name: "has_edge_degree", value: ["$child_count"])
                               @output_source {
                name @output(out_name: "child_name")
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'child_count': GraphQLInt,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def has_edge_degree_op_filter_with_optional():  # noqa: D103
    graphql_input = '''{
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
    }'''
    expected_output_metadata = {
        'species_name': OutputMetadata(type=GraphQLString, optional=False),
        'parent_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_name': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {
        'child_count': GraphQLInt,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def has_edge_degree_op_filter_with_optional_and_between():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            uuid @filter(op_name: "between", value: ["$uuid_lower_bound","$uuid_upper_bound"])

            in_Animal_ParentOf @optional
                               @filter(op_name: "has_edge_degree", value: ["$number_of_edges"]) {
                out_Entity_Related {
                    ... on Event {
                        name @output(out_name: "related_event")
                    }
                }
            }
        }
    }
    '''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'related_event': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {
        'uuid_lower_bound': GraphQLID,
        'uuid_upper_bound': GraphQLID,
        'number_of_edges': GraphQLInt,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def has_edge_degree_op_filter_with_fold():  # noqa: D103
    graphql_input = '''{
        Species {
            name @output(out_name: "species_name")

            in_Animal_OfSpecies {
                name @output(out_name: "parent_name")

                in_Animal_ParentOf @filter(op_name: "has_edge_degree", value: ["$child_count"])
                                   @fold {
                    name @output(out_name: "child_names")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'species_name': OutputMetadata(type=GraphQLString, optional=False),
        'parent_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_names': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {
        'child_count': GraphQLInt,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def is_null_op_filter():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            net_worth @filter(op_name: "is_null", value: [])
        }
    }'''

    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False)
    }

    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def is_not_null_op_filter():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            net_worth @filter(op_name: "is_not_null", value: [])
        }
    }'''

    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False)
    }

    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def fold_on_output_variable():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_ParentOf @fold {
                name @output(out_name: "child_names_list")
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_names_list': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def fold_after_traverse():  # noqa: D103
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
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'sibling_and_self_names_list': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def fold_and_traverse():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @fold {
                out_Animal_ParentOf {
                    name @output(out_name: "sibling_and_self_names_list")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'sibling_and_self_names_list': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def fold_and_deep_traverse():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @fold {
                out_Animal_ParentOf {
                    out_Animal_OfSpecies {
                        name @output(out_name: "sibling_and_self_species_list")
                    }
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'sibling_and_self_species_list': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def traverse_and_fold_and_traverse():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf {
                out_Animal_ParentOf @fold {
                    out_Animal_OfSpecies {
                        name @output(out_name: "sibling_and_self_species_list")
                    }
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'sibling_and_self_species_list': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def multiple_outputs_in_same_fold():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_ParentOf @fold {
                name @output(out_name: "child_names_list")
                uuid @output(out_name: "child_uuids_list")
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_names_list': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
        'child_uuids_list': OutputMetadata(type=GraphQLList(GraphQLID), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def multiple_outputs_in_same_fold_and_traverse():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @fold {
                out_Animal_ParentOf {
                    name @output(out_name: "sibling_and_self_names_list")
                    uuid @output(out_name: "sibling_and_self_uuids_list")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'sibling_and_self_names_list': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
        'sibling_and_self_uuids_list': OutputMetadata(
            type=GraphQLList(GraphQLID), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def multiple_folds():  # noqa: D103
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
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_names_list': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
        'child_uuids_list': OutputMetadata(type=GraphQLList(GraphQLID), optional=False),
        'parent_names_list': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
        'parent_uuids_list': OutputMetadata(type=GraphQLList(GraphQLID), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def multiple_folds_and_traverse():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_ParentOf @fold {
                in_Animal_ParentOf {
                    name @output(out_name: "spouse_and_self_names_list")
                    uuid @output(out_name: "spouse_and_self_uuids_list")
                }
            }
            in_Animal_ParentOf @fold {
                out_Animal_ParentOf {
                    name @output(out_name: "sibling_and_self_names_list")
                    uuid @output(out_name: "sibling_and_self_uuids_list")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'spouse_and_self_names_list': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
        'spouse_and_self_uuids_list': OutputMetadata(
            type=GraphQLList(GraphQLID), optional=False),
        'sibling_and_self_names_list': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
        'sibling_and_self_uuids_list': OutputMetadata(
            type=GraphQLList(GraphQLID), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def fold_date_and_datetime_fields():  # noqa: D103
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
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_birthdays_list': OutputMetadata(type=GraphQLList(GraphQLDate), optional=False),
        'fed_at_datetimes_list': OutputMetadata(
            type=GraphQLList(GraphQLDateTime), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def coercion_to_union_base_type_inside_fold():  # noqa: D103
    # Given type_equivalence_hints = { Event: Union__BirthEvent__Event__FeedingEvent },
    # the coercion should be optimized away as a no-op.
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_ImportantEvent @fold {
                ... on Event {
                    name @output(out_name: "important_events")
                }
            }
        }
    }'''
    type_equivalence_hints = {
        'Event': 'Union__BirthEvent__Event__FeedingEvent'
    }
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'important_events': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=type_equivalence_hints)


def no_op_coercion_inside_fold():  # noqa: D103
    # The type where the coercion is applied is already Entity, so the coercion is a no-op.
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            out_Entity_Related @fold {
                ... on Entity {
                    name @output(out_name: "related_entities")
                }
            }
        }
    }'''
    type_equivalence_hints = {
        'Event': 'Union__BirthEvent__Event__FeedingEvent'
    }
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'related_entities': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=type_equivalence_hints)


def no_op_coercion_with_eligible_subpath():  # noqa: D103
    # This test case has a no-op coercion and a preferred location inside an
    # eligible location. The no-op must be optimized away, or it will cause
    # problems when hiding the eligible non-preferred location.
    graphql_input = '''{
        Animal {
            out_Animal_ParentOf {
                ... on Animal {
                    out_Animal_ParentOf {
                        name @output(out_name: "animal_name")
                    }
                    out_Entity_Related {
                        ... on Entity {
                            name @filter(op_name: "in_collection", value: ["$entity_names"])
                        }
                    }
                }
            }
        }
    }'''
    type_equivalence_hints = {}
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'entity_names': GraphQLList(GraphQLString)
    }
    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=type_equivalence_hints)


def filter_within_fold_scope():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            out_Animal_ParentOf @fold {
                name @filter(op_name: "=", value: ["$desired"]) @output(out_name: "child_list")
                description @output(out_name: "child_descriptions")
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'child_list': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
        'child_descriptions': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {
        'desired': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_on_fold_scope():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            out_Animal_ParentOf @fold
                                @filter(op_name: "name_or_alias", value: ["$desired"]) {
                name @output(out_name: "child_list")
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'child_list': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {
        'desired': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def coercion_on_interface_within_fold_scope():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            out_Entity_Related @fold {
                ... on Animal {
                    name @output(out_name: "related_animals")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'related_animals': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def coercion_on_interface_within_fold_traversal():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @fold {
                out_Entity_Related {
                    ... on Animal {
                        out_Animal_OfSpecies {
                            name @output(out_name: "related_animal_species")
                        }
                    }
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'related_animal_species': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def coercion_on_union_within_fold_scope():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            out_Animal_ImportantEvent @fold {
                ... on BirthEvent {
                    name @output(out_name: "birth_events")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'birth_events': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def coercion_filters_and_multiple_outputs_within_fold_scope():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            out_Entity_Related @fold {
                ... on Animal {
                    name @filter(op_name: "has_substring", value: ["$substring"])
                         @output(out_name: "related_animals")
                    birthday @filter(op_name: "<=", value: ["$latest"])
                             @output(out_name: "related_birthdays")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'related_animals': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
        'related_birthdays': OutputMetadata(
            type=GraphQLList(GraphQLDate), optional=False),
    }
    expected_input_metadata = {
        'substring': GraphQLString,
        'latest': GraphQLDate,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def coercion_filters_and_multiple_outputs_within_fold_traversal():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            in_Animal_ParentOf @fold {
                out_Entity_Related {
                    ... on Animal {
                        name @filter(op_name: "has_substring", value: ["$substring"])
                             @output(out_name: "related_animals")
                        birthday @filter(op_name: "<=", value: ["$latest"])
                                 @output(out_name: "related_birthdays")
                    }
                }
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'related_animals': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
        'related_birthdays': OutputMetadata(
            type=GraphQLList(GraphQLDate), optional=False),
    }
    expected_input_metadata = {
        'substring': GraphQLString,
        'latest': GraphQLDate,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def output_count_in_fold_scope():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            out_Animal_ParentOf @fold {
                _x_count @output(out_name: "number_of_children")
                name @output(out_name: "child_names")
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'number_of_children': OutputMetadata(type=GraphQLInt, optional=False),
        'child_names': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_count_with_runtime_parameter_in_fold_scope():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            out_Animal_ParentOf @fold {
                _x_count @filter(op_name: ">=", value: ["$min_children"])
                name @output(out_name: "child_names")
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'child_names': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {
        'min_children': GraphQLInt,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_count_with_tagged_parameter_in_fold_scope():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            out_Animal_OfSpecies {
                limbs @tag(tag_name: "limbs")
            }
            out_Animal_ParentOf @fold {
                _x_count @filter(op_name: ">=", value: ["%limbs"])
                name @output(out_name: "child_names")
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'child_names': OutputMetadata(type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_count_and_other_filters_in_fold_scope():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            out_Animal_ParentOf @fold {
                _x_count @filter(op_name: ">=", value: ["$min_children"])
                        @output(out_name: "number_of_children")
                alias @filter(op_name: "contains", value: ["$expected_alias"])
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'number_of_children': OutputMetadata(type=GraphQLInt, optional=False),
    }
    expected_input_metadata = {
        'min_children': GraphQLInt,
        'expected_alias': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def multiple_filters_on_count():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            out_Animal_ParentOf @fold {
                _x_count @filter(op_name: ">=", value: ["$min_children"])
            }
            out_Entity_Related @fold {
                _x_count @filter(op_name: ">=", value: ["$min_related"])
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'min_children': GraphQLInt,
        'min_related': GraphQLInt,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_on_count_with_nested_filter():  # noqa: D103
    graphql_input = '''{
        Species {
            name @output(out_name: "name")
            in_Animal_OfSpecies @fold {
                out_Animal_LivesIn {
                    _x_count @filter(op_name: "=", value: ["$num_animals"])
                    name @filter(op_name: "=", value: ["$location"])
                }
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'num_animals': GraphQLInt,
        'location': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def optional_and_traverse():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            in_Animal_ParentOf @optional {
                name @output(out_name: "child_name")
                in_Animal_ParentOf {
                    name @output(out_name: "grandchild_name")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'child_name': OutputMetadata(type=GraphQLString, optional=True),
        'grandchild_name': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def optional_and_traverse_after_filter():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
                 @filter(op_name: "has_substring", value: ["$wanted"])
            in_Animal_ParentOf @optional {
                name @output(out_name: "child_name")
                in_Animal_ParentOf {
                    name @output(out_name: "grandchild_name")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'child_name': OutputMetadata(type=GraphQLString, optional=True),
        'grandchild_name': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {
        'wanted': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def optional_and_deep_traverse():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @optional {
                name @output(out_name: "child_name")
                out_Animal_ParentOf {
                    name @output(out_name: "spouse_and_self_name")
                    out_Animal_OfSpecies {
                        name @output(out_name: "spouse_species")
                    }
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_name': OutputMetadata(type=GraphQLString, optional=True),
        'spouse_and_self_name': OutputMetadata(type=GraphQLString, optional=True),
        'spouse_species': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def traverse_and_optional_and_traverse():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf {
                name @output(out_name: "child_name")
                out_Animal_ParentOf @optional {
                    name @output(out_name: "spouse_and_self_name")
                    out_Animal_OfSpecies {
                        name @output(out_name: "spouse_and_self_species")
                    }
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_name': OutputMetadata(type=GraphQLString, optional=False),
        'spouse_and_self_name': OutputMetadata(type=GraphQLString, optional=True),
        'spouse_and_self_species': OutputMetadata(type=GraphQLString, optional=True)
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def multiple_optional_traversals_with_starting_filter():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
                 @filter(op_name: "has_substring", value: ["$wanted"])
            in_Animal_ParentOf @optional {
                name @output(out_name: "child_name")
                out_Animal_ParentOf {
                    name @output(out_name: "spouse_and_self_name")
                }
            }
            out_Animal_ParentOf @optional {
                name @output(out_name: "parent_name")
                out_Animal_OfSpecies {
                    name @output(out_name: "parent_species")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_name': OutputMetadata(type=GraphQLString, optional=True),
        'spouse_and_self_name': OutputMetadata(type=GraphQLString, optional=True),
        'parent_name': OutputMetadata(type=GraphQLString, optional=True),
        'parent_species': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {
        'wanted': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def optional_traversal_and_optional_without_traversal():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
                 @filter(op_name: "has_substring", value: ["$wanted"])
            in_Animal_ParentOf @optional {
                name @output(out_name: "child_name")
            }
            out_Animal_ParentOf @optional {
                name @output(out_name: "parent_name")
                out_Animal_OfSpecies {
                    name @output(out_name: "parent_species")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_name': OutputMetadata(type=GraphQLString, optional=True),
        'parent_name': OutputMetadata(type=GraphQLString, optional=True),
        'parent_species': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {
        'wanted': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def coercion_on_interface_within_optional_traversal():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @optional {
                out_Entity_Related {
                    ... on Animal {
                        out_Animal_OfSpecies {
                            name @output(out_name: "related_animal_species")
                        }
                    }
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'related_animal_species': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_on_optional_traversal_equality():  # noqa: D103
    # The operand in the @filter directive originates from an optional block.
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_ParentOf {
                out_Animal_ParentOf @optional {
                    out_Animal_FedAt {
                        name @tag(tag_name: "grandparent_fed_at_event")
                    }
                }
            }
            out_Animal_FedAt @output_source {
                name @filter(op_name: "=", value: ["%grandparent_fed_at_event"])
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def filter_on_optional_traversal_name_or_alias():  # noqa: D103
    # The operand in the @filter directive originates from an optional block.
    graphql_input = '''{
        Animal {
            in_Animal_ParentOf @optional {
                in_Animal_ParentOf {
                    name @tag(tag_name: "grandchild_name")
                }
            }
            out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["%grandchild_name"])
                                @output_source {
                name @output(out_name: "parent_name")
            }
        }
    }'''
    expected_output_metadata = {
        'parent_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def complex_optional_traversal_variables():  # noqa: D103
    # The operands in the @filter directives originate from an optional block.
    graphql_input = '''{
        Animal {
            name @filter(op_name: "=", value: ["$animal_name"])
            out_Animal_ParentOf {
                out_Animal_FedAt @optional {
                    name @tag(tag_name: "parent_fed_at_event")
                    event_date @tag(tag_name: "parent_fed_at")
                               @output(out_name: "parent_fed_at")
                }
                in_Animal_ParentOf @optional {
                    out_Animal_FedAt {
                        event_date @tag(tag_name: "other_child_fed_at")
                                   @output(out_name: "other_child_fed_at")
                    }
                }
            }
            in_Animal_ParentOf {
                out_Animal_FedAt {
                    name @filter(op_name: "=", value: ["%parent_fed_at_event"])
                    event_date @output(out_name: "grandchild_fed_at")
                               @filter(op_name: "between",
                                       value: ["%other_child_fed_at", "%parent_fed_at"])
                }
            }
        }
    }'''
    expected_output_metadata = {
        'parent_fed_at': OutputMetadata(type=GraphQLDateTime, optional=True),
        'other_child_fed_at': OutputMetadata(type=GraphQLDateTime, optional=True),
        'grandchild_fed_at': OutputMetadata(type=GraphQLDateTime, optional=False),
    }
    expected_input_metadata = {
        'animal_name': GraphQLString,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def simple_optional_recurse():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            in_Animal_ParentOf @optional {
                name @output(out_name: "child_name")
                out_Animal_ParentOf @recurse(depth: 3) {
                    name @output(out_name: "self_and_ancestor_name")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'child_name': OutputMetadata(type=GraphQLString, optional=True),
        'self_and_ancestor_name': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def multiple_traverse_within_optional():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "name")
            in_Animal_ParentOf @optional {
                name @output(out_name: "child_name")
                in_Animal_ParentOf {
                    name @output(out_name: "grandchild_name")
                }
                out_Animal_FedAt {
                    name @output(out_name: "child_feeding_time")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'name': OutputMetadata(type=GraphQLString, optional=False),
        'child_name': OutputMetadata(type=GraphQLString, optional=True),
        'grandchild_name': OutputMetadata(type=GraphQLString, optional=True),
        'child_feeding_time': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def optional_and_fold():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @optional {
                name @output(out_name: "parent_name")
            }
            out_Animal_ParentOf @fold {
                name @output(out_name: "child_names_list")
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'parent_name': OutputMetadata(type=GraphQLString, optional=True),
        'child_names_list': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def fold_and_optional():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_ParentOf @fold {
                name @output(out_name: "child_names_list")
            }
            in_Animal_ParentOf @optional {
                name @output(out_name: "parent_name")
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'parent_name': OutputMetadata(type=GraphQLString, optional=True),
        'child_names_list': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def optional_traversal_and_fold_traversal():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @optional {
                in_Animal_ParentOf {
                    name @output(out_name: "grandparent_name")
                }
            }
            out_Animal_ParentOf @fold {
                out_Animal_ParentOf {
                    name @output(out_name: "grandchild_names_list")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'grandparent_name': OutputMetadata(type=GraphQLString, optional=True),
        'grandchild_names_list': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def fold_traversal_and_optional_traversal():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_ParentOf @fold {
                out_Animal_ParentOf {
                    name @output(out_name: "grandchild_names_list")
                }
            }
            in_Animal_ParentOf @optional {
                in_Animal_ParentOf {
                    name @output(out_name: "grandparent_name")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'grandparent_name': OutputMetadata(type=GraphQLString, optional=True),
        'grandchild_names_list': OutputMetadata(
            type=GraphQLList(GraphQLString), optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def between_lowering():  # noqa: D103
    graphql_input = '''{
        Animal {
            uuid @filter(op_name: "between", value: ["$uuid_lower", "$uuid_upper"])
            name @output(out_name: "animal_name")
            birthday @filter(op_name: ">=", value: ["$earliest_modified_date"])
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {
        'uuid_lower': GraphQLID,
        'uuid_upper': GraphQLID,
        'earliest_modified_date': GraphQLDate,
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def coercion_and_filter_with_tag():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "origin") @tag(tag_name: "related")
            out_Entity_Related {
                ... on Animal {
                    name @filter(op_name: "has_substring", value: ["%related"])
                         @output(out_name: "related_name")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'origin': OutputMetadata(type=GraphQLString, optional=False),
        'related_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def nested_optional_and_traverse():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @optional {
                name @output(out_name: "child_name")
                out_Animal_ParentOf @optional {
                    name @output(out_name: "spouse_and_self_name")
                    out_Animal_OfSpecies {
                        name @output(out_name: "spouse_species")
                    }
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_name': OutputMetadata(type=GraphQLString, optional=True),
        'spouse_and_self_name': OutputMetadata(type=GraphQLString, optional=True),
        'spouse_species': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def complex_nested_optionals():  # noqa: D103
    graphql_input = '''{
        Animal {
            name @output(out_name: "animal_name")
            in_Animal_ParentOf @optional {
                name @output(out_name: "child_name")
                in_Animal_ParentOf @optional {
                    name @output(out_name: "grandchild_name")
                    out_Animal_OfSpecies {
                        name @output(out_name: "grandchild_species")
                    }
                }
                in_Entity_Related @optional {
                    ... on Animal {
                        name @output(out_name: "grandchild_relation_name")
                        out_Animal_OfSpecies {
                            name @output(out_name: "grandchild_relation_species")
                        }
                    }
                }
            }
            out_Animal_ParentOf @optional {
                name @output(out_name: "parent_name")
                out_Animal_ParentOf @optional {
                    name @output(out_name: "grandparent_name")
                    out_Animal_OfSpecies {
                        name @output(out_name: "grandparent_species")
                    }
                }
            }
        }
    }'''
    expected_output_metadata = {
        'animal_name': OutputMetadata(type=GraphQLString, optional=False),
        'child_name': OutputMetadata(type=GraphQLString, optional=True),
        'grandchild_name': OutputMetadata(type=GraphQLString, optional=True),
        'grandchild_species': OutputMetadata(type=GraphQLString, optional=True),
        'grandchild_relation_name': OutputMetadata(type=GraphQLString, optional=True),
        'grandchild_relation_species': OutputMetadata(type=GraphQLString, optional=True),
        'parent_name': OutputMetadata(type=GraphQLString, optional=True),
        'grandparent_name': OutputMetadata(type=GraphQLString, optional=True),
        'grandparent_species': OutputMetadata(type=GraphQLString, optional=True),
    }
    expected_input_metadata = {}

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=None)


def recursive_field_type_is_subtype_of_parent_field():  # noqa: D103
    """Ensure that recursion is allowed along an edge linked to a supertype of the parent field."""
    graphql_input = '''{
        BirthEvent {
            out_Event_RelatedEvent @recurse(depth:2) {
                ... on Event {
                    name @output(out_name: "related_event_name")
                }
            }
        }
    }'''
    expected_output_metadata = {
        'related_event_name': OutputMetadata(type=GraphQLString, optional=False),
    }
    expected_input_metadata = {}

    type_equivalence_hints = {
        'Event': 'Union__BirthEvent__Event__FeedingEvent',
    }

    return CommonTestData(
        graphql_input=graphql_input,
        expected_output_metadata=expected_output_metadata,
        expected_input_metadata=expected_input_metadata,
        type_equivalence_hints=type_equivalence_hints)
