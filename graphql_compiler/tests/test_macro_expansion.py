# Copyright 2019-present Kensho Technologies, LLC.
from typing import Any, Dict
import unittest

import pytest

from ..exceptions import GraphQLCompilationError
from ..macros import get_schema_with_macros, perform_macro_expansion
from .test_helpers import compare_graphql, get_test_macro_registry


class MacroExpansionTests(unittest.TestCase):
    def setUp(self) -> None:
        """Disable max diff limits for all tests."""
        self.maxDiff = None
        self.macro_registry = get_test_macro_registry()
        self.schema_with_macros = get_schema_with_macros(self.macro_registry)

    def test_macro_edge_basic(self) -> None:
        query = """{
            Animal {
                out_Animal_GrandparentOf {
                    name @output(out_name: "grandkid")
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                out_Animal_ParentOf {
                    out_Animal_ParentOf {
                        name @output(out_name: "grandkid")
                    }
                }
            }
        }"""
        expected_args: Dict[str, Any] = {}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_pro_forma_fields(self) -> None:
        # The macro or the user code could have an unused (pro-forma) field for the sake of not
        # having an empty selection in a vertex field. We remove pro-forma fields if they are
        # no longer necessary. This test checks that this is done correctly.
        query = """{
            Animal {
                name @output(out_name: "name")
                out_Animal_GrandparentOf {
                    uuid
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                name @output(out_name: "name")
                out_Animal_ParentOf {
                    out_Animal_ParentOf {
                        uuid
                    }
                }
            }
        }"""
        expected_args: Dict[str, Any] = {}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_two_different_pro_forma_fields(self) -> None:
        # The macro or the user code could have an unused (pro-forma) field for the sake of not
        # having an empty selection in a vertex field. We remove pro-forma fields if they are
        # no longer necessary. This test checks that this is done correctly.
        query = """{
            Animal {
                name @output(out_name: "name")
                out_Animal_GrandparentOf {
                    name
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                name @output(out_name: "name")
                out_Animal_ParentOf {
                    out_Animal_ParentOf {
                        name
                    }
                }
            }
        }"""
        expected_args: Dict[str, Any] = {}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_on_interface(self) -> None:
        query = """{
            Animal {
                out_Entity_AlmostRelated {
                    name @output(out_name: "distant_relative")
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                out_Entity_Related {
                    out_Entity_Related {
                        name @output(out_name: "distant_relative")
                    }
                }
            }
        }"""
        expected_args: Dict[str, Any] = {}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_non_leaf_target_and_field_merging(self) -> None:
        query = """{
            Animal {
                out_Animal_RichYoungerSiblings {
                    net_worth @filter(op_name: "<", value: ["$net_worth_upper_bound"])
                              @output(out_name: "sibling_net_worth")
                }
            }
        }"""
        args = {
            "net_worth_upper_bound": 5,
        }

        expected_query = """{
            Animal {
                net_worth @tag(tag_name: "net_worth")
                out_Animal_BornAt {
                    event_date @tag(tag_name: "birthday")
                }
                in_Animal_ParentOf {
                    out_Animal_ParentOf {
                        net_worth @filter(op_name: ">", value: ["%net_worth"])
                                  @filter(op_name: "<", value: ["$net_worth_upper_bound"])
                                  @output(out_name: "sibling_net_worth")
                        out_Animal_BornAt {
                            event_date @filter(op_name: "<", value: ["%birthday"])
                        }
                    }
                }
            }
        }"""
        expected_args = {
            "net_worth_upper_bound": 5,
        }

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_source_merging(self) -> None:
        query = """{
            Animal {
                net_worth @filter(op_name: "<", value: ["$net_worth_upper_bound"])
                          @output(out_name: "net_worth")
                out_Animal_RichYoungerSiblings {
                    uuid
                }
            }
        }"""
        args = {
            "net_worth_upper_bound": 5,
        }

        expected_query = """{
            Animal {
                net_worth @filter(op_name: "<", value: ["$net_worth_upper_bound"])
                          @output(out_name: "net_worth")
                          @tag(tag_name: "net_worth")
                out_Animal_BornAt {
                    event_date @tag(tag_name: "birthday")
                }
                in_Animal_ParentOf {
                    out_Animal_ParentOf {
                        net_worth @filter(op_name: ">", value: ["%net_worth"])
                        out_Animal_BornAt {
                            event_date @filter(op_name: "<", value: ["%birthday"])
                        }
                    }
                }
            }
        }"""
        expected_args = {
            "net_worth_upper_bound": 5,
        }

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_tag_filter_order(self) -> None:
        # Tags should appear before filters. Test that this is not violated during expansion.
        query = """{
            Animal {
                out_Animal_RichYoungerSiblings_2 {
                    uuid
                }
            }
        }"""
        args = {
            "net_worth_upper_bound": 5,
        }

        expected_query = """{
            Animal {
                net_worth @tag(tag_name: "net_worth")
                in_Animal_ParentOf {
                    out_Animal_ParentOf {
                        net_worth @filter(op_name: ">", value: ["%net_worth"])
                        out_Animal_BornAt {
                            event_date @tag(tag_name: "birthday")
                        }
                    }
                }
                out_Animal_BornAt {
                    event_date @filter(op_name: ">", value: ["%birthday"])
                }
            }
        }"""
        expected_args = {
            "net_worth_upper_bound": 5,
        }

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_target_coercion_0(self) -> None:
        query = """{
            Animal {
                out_Animal_GrandparentOf {
                    ... on Animal {
                        name @output(out_name: "grandkid")
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                out_Animal_ParentOf {
                    out_Animal_ParentOf {
                        ... on Animal {
                            name @output(out_name: "grandkid")
                        }
                    }
                }
            }
        }"""
        expected_args: Dict[str, Any] = {}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_target_coercion_1(self) -> None:
        query = """{
            Animal {
                out_Animal_RelatedFood {
                   ... on Food {
                       name @output(out_name: "food")
                   }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                in_Entity_Related {
                    ... on Food {
                        name @output(out_name: "food")
                    }
                }
            }
        }"""
        expected_args: Dict[str, Any] = {}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_target_coercion_4(self) -> None:
        query = """{
            Animal {
                out_Animal_RelatedEntity {
                   ... on Event {
                       name @output(out_name: "event")
                   }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                in_Entity_Related {
                    ... on Event {
                        name @output(out_name: "event")
                    }
                }
            }
        }"""
        expected_args: Dict[str, Any] = {}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_target_coercion_5(self) -> None:
        query = """{
            Animal {
                out_Animal_RelatedEntity {
                   ... on Animal {
                       name @output(out_name: "animal")
                   }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                in_Entity_Related {
                    ... on Animal {
                        name @output(out_name: "animal")
                    }
                }
            }
        }"""
        expected_args: Dict[str, Any] = {}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_target_coercion_with_filter_0(self) -> None:
        query = """{
            Animal {
                out_Animal_GrandparentOf {
                    ... on Animal @filter(op_name: "name_or_alias", value: ["$wanted"]) {
                        name @output(out_name: "grandkid")
                    }
                }
            }
        }"""
        args = {"wanted": "croissant"}

        expected_query = """{
            Animal {
                out_Animal_ParentOf {
                    out_Animal_ParentOf {
                        ... on Animal @filter(op_name: "name_or_alias", value: ["$wanted"]) {
                            name @output(out_name: "grandkid")
                        }
                    }
                }
            }
        }"""
        expected_args = {"wanted": "croissant"}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_target_coercion_with_filter_1(self) -> None:
        query = """{
            Animal {
                out_Animal_RelatedEntity {
                   ... on Food @filter(op_name: "name_or_alias", value: ["$wanted"]) {
                       name @output(out_name: "animal")
                   }
                }
            }
        }"""
        args = {"wanted": "croissant"}

        expected_query = """{
            Animal {
                in_Entity_Related {
                    ... on Food @filter(op_name: "name_or_alias", value: ["$wanted"]){
                        name @output(out_name: "animal")
                    }
                }
            }
        }"""
        expected_args = {"wanted": "croissant"}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_target_coercion_with_filter_3(self) -> None:
        query = """{
            Animal {
                out_Animal_GrandchildrenCalledNate {
                    name @output(out_name: "official_name")
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["$wanted"]) {
                        name @output(out_name: "official_name")
                    }
                }
            }
        }"""
        expected_args = {
            "wanted": "Nate",
        }

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_target_coercion_with_filter_4(self) -> None:
        query = """{
            Animal {
                out_Animal_GrandchildrenCalledNate @filter(op_name: "name_or_alias",
                                                           value: ["$something"]) {
                    name @output(out_name: "official_name")
                }
            }
        }"""
        args = {
            "something": "Peter",
        }

        expected_query = """{
            Animal {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["$wanted"])
                                        @filter(op_name: "name_or_alias", value: ["$something"]) {
                        name @output(out_name: "official_name")
                    }
                }
            }
        }"""
        expected_args = {
            "something": "Peter",
            "wanted": "Nate",
        }

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_arguments(self) -> None:
        query = """{
            Location {
                name @filter(op_name: "=", value: ["$location"])
                out_Location_Orphans {
                    name @output(out_name: "name")
                }
            }
        }"""
        args = {
            "location": "Europe",
        }

        expected_query = """{
            Location {
                name @filter(op_name: "=", value: ["$location"])
                in_Animal_LivesIn {
                    name @output(out_name: "name")
                    in_Animal_ParentOf @filter(op_name: "has_edge_degree", value: ["$num_parents"])
                                       @optional {
                        uuid
                    }
                }
            }
        }"""
        expected_args = {
            "location": "Europe",
            "num_parents": 0,
        }

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_edge_tag_collision(self) -> None:
        query = """{
            Animal {
                net_worth @tag(tag_name: "parent_net_worth")
                out_Animal_RichSiblings {
                    net_worth @filter(op_name: ">", value: ["%parent_net_worth"])
                    name @output(out_name: "sibling")
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                net_worth @tag(tag_name: "parent_net_worth")
                in_Animal_ParentOf {
                    net_worth @tag(tag_name: "parent_net_worth_macro_edge_0")
                    out_Animal_ParentOf {
                        net_worth @filter(op_name: ">", value: ["%parent_net_worth_macro_edge_0"])
                                  @filter(op_name: ">", value: ["%parent_net_worth"])
                        name @output(out_name: "sibling")
                    }
                }
            }
        }"""
        expected_args: Dict[str, Any] = {}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    @pytest.mark.xfail(
        strict=True, reason="tag deduplication not implemented yet", raises=GraphQLCompilationError
    )
    def test_macro_edge_colocated_tags(self) -> None:
        query = """{
            Animal {
                net_worth @tag(tag_name: "animal_net_worth")
                out_Animal_RichYoungerSiblings {
                    net_worth @filter(op_name: "<", value: ["%animal_net_worth"])
                              @output(out_name: "sibling_net_worth")
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                net_worth @tag(tag_name: "animal_net_worth")
                out_Animal_BornAt {
                    event_date @tag(tag_name: "birthday")
                }
                in_Animal_ParentOf {
                    out_Animal_ParentOf {
                        net_worth @filter(op_name: ">", value: ["%animal_net_worth"])
                                  @filter(op_name: "<", value: ["%animal_net_worth"])
                                  @output(out_name: "sibling_net_worth")
                        out_Animal_BornAt {
                            event_date @filter(op_name: "<", value: ["%birthday"])
                        }
                    }
                }
            }
        }"""
        expected_args: Dict[str, Any] = {}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    @pytest.mark.xfail(
        strict=True, reason="tag deduplication not implemented yet", raises=GraphQLCompilationError
    )
    def test_macro_edge_colocated_tags_with_same_name(self) -> None:
        query = """{
            Animal {
                net_worth @tag(tag_name: "net_worth")
                out_Animal_RichYoungerSiblings {
                    net_worth @filter(op_name: "<=", value: ["%net_worth"])
                              @output(out_name: "sibling_net_worth")
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                net_worth @tag(tag_name: "net_worth")
                out_Animal_BornAt {
                    event_date @tag(tag_name: "birthday")
                }
                in_Animal_ParentOf {
                    out_Animal_ParentOf {
                        net_worth @filter(op_name: ">", value: ["%net_worth"])
                                  @filter(op_name: "<=", value: ["%net_worth"])
                                  @output(out_name: "sibling_net_worth")
                        out_Animal_BornAt {
                            event_date @filter(op_name: "<", value: ["%birthday"])
                        }
                    }
                }
            }
        }"""
        expected_args: Dict[str, Any] = {}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_nested_use(self) -> None:
        query = """{
            Animal {
                out_Animal_GrandparentOf {
                    out_Animal_GrandparentOf {
                        name @output(out_name: "grandgrandkid")
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                out_Animal_ParentOf {
                    out_Animal_ParentOf {
                        out_Animal_ParentOf {
                            out_Animal_ParentOf {
                                name @output(out_name: "grandgrandkid")
                            }
                        }
                    }
                }
            }
        }"""
        expected_args: Dict[str, Any] = {}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_parallel_use(self) -> None:
        query = """{
            Animal {
                out_Animal_GrandparentOf {
                   name @output(out_name: "grandkid")
                }
                in_Animal_ParentOf {
                    out_Animal_GrandparentOf {
                       name @output(out_name: "nephew")
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        expected_query = """{
            Animal {
                out_Animal_ParentOf {
                    out_Animal_ParentOf {
                        name @output(out_name: "grandkid")
                    }
                }
                in_Animal_ParentOf {
                    out_Animal_ParentOf {
                        out_Animal_ParentOf {
                            name @output(out_name: "nephew")
                        }
                    }
                }
            }
        }"""
        expected_args: Dict[str, Any] = {}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_expansion_with_filter_directive(self) -> None:
        query = """{
            Animal {
                out_Animal_GrandparentOf @filter(op_name: "name_or_alias", value: ["$wanted"]) {
                    name @output(out_name: "grandkid")
                }
            }
        }"""
        args = {"wanted": "Larry"}

        expected_query = """{
            Animal {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["$wanted"]) {
                        name @output(out_name: "grandkid")
                    }
                }
            }
        }"""
        expected_args = {"wanted": "Larry"}

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)

    def test_macro_expansion_with_optional_directives(self) -> None:
        query = """{
            Animal {
                name @filter(op_name: "=", value: ["$name"])

                out_Animal_MaybeYoungerSiblings {
                    name @output(out_name: "sibling_name")
                }
            }
        }"""
        args = {
            "name": "Nate",
        }

        expected_query = """{
            Animal {
                name @filter(op_name: "=", value: ["$name"])

                out_Animal_BornAt @optional {
                    event_date @tag(tag_name: "birthday")
                }
                in_Animal_ParentOf {
                    out_Animal_ParentOf {
                        name @output(out_name: "sibling_name")
                        out_Animal_BornAt @optional {
                            event_date @filter(op_name: ">", value: ["%birthday"])
                        }
                    }
                }
            }
        }"""
        expected_args = {
            "name": "Nate",
        }

        expanded_query, new_args = perform_macro_expansion(
            self.macro_registry, self.schema_with_macros, query, args
        )
        compare_graphql(self, expected_query, expanded_query)
        self.assertEqual(expected_args, new_args)
