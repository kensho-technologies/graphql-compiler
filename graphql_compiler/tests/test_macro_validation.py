# Copyright 2019-present Kensho Technologies, LLC.
from typing import Any, Dict
import unittest

from ..exceptions import GraphQLInvalidArgumentError, GraphQLInvalidMacroError
from ..macros import register_macro_edge
from .test_helpers import get_empty_test_macro_registry


class MacroValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        """Disable max diff limits for all tests."""
        self.maxDiff = None

    def test_bad_operation_type(self) -> None:
        macro_edge_definition = """mutation {
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_with_output_directive(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid @output(out_name: "uuid")
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_with_output_source_directive(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf @output_source {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_with_target_at_optional(self) -> None:
        macro_edge_definition_template = """{
            Animal @macro_edge_definition(name: "out_Animal_OptionalGrandparentOf_Invalid") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf %(target_and_optional)s {
                        uuid
                    }
                }
            }
        }"""
        target_and_optional_orders = (
            # Ensure we test both directive orders, to ensure the validation is not sensitive
            # to the directive order.
            "@optional @macro_edge_target",
            "@macro_edge_target @optional",
        )

        args: Dict[str, Any] = {}

        for target_and_optional in target_and_optional_orders:
            macro_edge_definition = macro_edge_definition_template % {
                "target_and_optional": target_and_optional
            }

            macro_registry = get_empty_test_macro_registry()
            with self.assertRaises(GraphQLInvalidMacroError):
                register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_with_target_inside_optional(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_OptionalGrandparentOf_Invalid") {
                out_Animal_ParentOf @optional {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_with_target_at_fold(self) -> None:
        macro_edge_definition_template = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf %(target_and_fold)s {
                        _x_count @filter(op_name: ">=", value: ["$min_count"])
                    }
                }
            }
        }"""
        args = {
            "min_count": 1,
        }

        target_and_fold_orders = (
            # Ensure we test both directive orders, to ensure the validation is not sensitive
            # to the directive order.
            "@fold @macro_edge_target",
            "@macro_edge_target @fold",
        )

        for target_and_fold in target_and_fold_orders:
            macro_edge_definition = macro_edge_definition_template % {
                "target_and_fold": target_and_fold
            }

            macro_registry = get_empty_test_macro_registry()
            with self.assertRaises(GraphQLInvalidMacroError):
                register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_with_target_inside_fold(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf @fold {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_with_target_outside_fold(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
                out_Animal_LivesIn @fold {
                    _x_count @filter(op_name: "=", value: ["$num_locations"])
                }
            }
        }"""
        args = {
            "num_locations": 1,
        }

        # It should compile successfully
        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_missing_target(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf {
                        uuid
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_multiple_targets(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf @macro_edge_target {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_multiple_targets_2(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Invalid") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_missing_definition(self) -> None:
        macro_edge_definition = """{
            Animal {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_invalid_definition(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_target_directive_starting_with_coercion_disallowed(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_AvailableFood_Invalid") {
                out_Animal_LivesIn {
                    in_Entity_Related @macro_edge_target {
                        ... on Food {
                            uuid
                        }
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_invalid_no_op_1(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_Self") @macro_edge_target {
                uuid
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_invalid_no_op_2(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_Filter") @macro_edge_target {
                net_worth @filter(op_name: "=", value: ["$net_worth"])
                color @filter(op_name: "=", value: ["$color"])
            }
        }"""
        args = {
            "net_worth": 4,
            "color": "green",
        }

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_missing_args(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                net_worth @filter(op_name: "=", value: ["$net_worth"])
                color @filter(op_name: "=", value: ["$color"])
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args = {
            "net_worth": 4,
        }

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidArgumentError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_extra_args(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                net_worth @filter(op_name: "=", value: ["$net_worth"])
                color @filter(op_name: "=", value: ["$color"])
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args = {"net_worth": 4, "color": "green", "asdf": 5}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidArgumentError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_incorrect_arg_types(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                net_worth @filter(op_name: "=", value: ["$net_worth"])
                color @filter(op_name: "=", value: ["$color"])
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args = {
            # Expecting GraphQLInt for net_worth, but providing string.
            # Only valid values are six.integer_types minus bool.
            "net_worth": "incorrect_net_worth_type",
            "color": "green",
        }

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidArgumentError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_multiple_definitions(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf_Copy") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_duplicate_definition(self) -> None:
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                out_Animal_ParentOf {
                    out_Animal_ParentOf @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, macro_edge_definition, args)
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_duplicating_real_edge_name(self) -> None:
        macro_edge_definition = """{
            Species @macro_edge_definition(name: "out_Species_Eats") {
                out_Entity_Related {
                    out_Entity_Related {
                        ... on Animal @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_with_bad_name(self) -> None:
        macro_edge_definition = """{
            Species @macro_edge_definition(name: "not_edge_like_name") {
                out_Entity_Related {
                    out_Entity_Related {
                        ... on Animal @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_duplicate_definition_on_subclass(self) -> None:
        macro_edge_definition = """{
            Entity @macro_edge_definition(name: "out_RelatedOfRelated") {
                out_Entity_Related {
                    out_Entity_Related @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        macro_edge_definition_on_subclass = """{
            Event @macro_edge_definition(name: "out_RelatedOfRelated") {
                out_Entity_Related {
                    out_Entity_Related @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        # Try registering on the superclass first
        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, macro_edge_definition, args)
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition_on_subclass, args)

        # Try registering on the subclass first
        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, macro_edge_definition_on_subclass, args)
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_duplicating_real_edge_name_at_target(self) -> None:
        """Macro edges, when reversed, cannot duplicate existing edges at that type."""
        macro_edge_definition = """{
            Species @macro_edge_definition(name: "in_Animal_BornAt") {
                out_Entity_Related {
                    out_Entity_Related {
                        ... on Animal @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_duplicate_definition_on_target_subclass(self) -> None:
        # No matter in what order these macros are defined, their corresponding reversed macro edges
        # always conflict since they are named the same thing and start on a pair of types in a
        # subclass-superclass relationship with each other.
        macro_edge_definition_on_superclass = """{
            Animal @macro_edge_definition(name: "out_RelatedOfRelated") {
                out_Entity_Related {
                    out_Entity_Related @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""
        macro_edge_definition_on_subclass = """{
            Species @macro_edge_definition(name: "out_RelatedOfRelated") {
                out_Entity_Related {
                    out_Entity_Related {
                        ... on Event @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }"""
        args: Dict[str, Any] = {}

        # Try registering on the superclass target first
        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, macro_edge_definition_on_superclass, args)
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition_on_subclass, args)

        # Try registering on the subclass target first
        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, macro_edge_definition_on_subclass, args)
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition_on_superclass, args)

    def test_macro_edge_reversal_validation_rules_valid_case(self) -> None:
        """Test that valid reverse macro edges can be defined manually."""
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                out_Animal_ParentOf @macro_edge_target {
                    uuid
                }
            }
        }"""

        # This edge is named the same as the reversal of "out_Animal_GrandparentOf" above, and is
        # allowed since it points from Animal to Animal and therefore matches the types of the
        # original edge -- even though it does something completely different.
        allowed_macro_edge_definition = """{
            Animal @macro_edge_definition(name: "in_Animal_GrandparentOf") {
                out_Entity_Related {
                    ... on Animal @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""

        args: Dict[str, Any] = {}

        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, macro_edge_definition, args)

        # This call must succeed and not raise errors.
        register_macro_edge(macro_registry, allowed_macro_edge_definition, args)

    def test_macro_edge_reversal_validation_rules_origin_incompatible_conflict(self) -> None:
        # Reversing a macro edge must not conflict with an existing macro edge
        # defined between different types. The first one produces a macro edge from Animal to Animal
        # whereas the reversal of the second one produces a macro edge with the same name
        # from Animal to Species.
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                out_Animal_ParentOf @macro_edge_target {
                    uuid
                }
            }
        }"""

        # Meaningless macro edge that (when reversed) has the same origin type (Animal) and name,
        # but a different target type (Species) and is therefore invalid.
        duplicate_macro_edge_definition = """{
            Species @macro_edge_definition(name: "in_Animal_GrandparentOf") {
                out_Entity_Related {
                    ... on Animal @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""

        args: Dict[str, Any] = {}

        # The two macros above are mutually incompatible, regardless of registration order.
        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, macro_edge_definition, args)
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, duplicate_macro_edge_definition, args)

        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, duplicate_macro_edge_definition, args)
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_reversal_validation_rules_target_incompatible_conflict(self) -> None:
        # Reversing a macro edge must not conflict with an existing macro edge defined
        # between different types. The first one produces a macro edge from Species to Animal
        # whereas the reversal of the second one produces a macro edge with the same name
        # from Animal to Entity.
        macro_edge_definition = """{
            Species @macro_edge_definition(name: "out_DistantRelatedAnimal") {
                out_Entity_Related {
                    out_Entity_Related {
                        ... on Animal @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }"""

        # Meaningless macro edge that when reversed has the same name and points to Entity
        # (a superclass of Species, causing the conflict), but has a different target type (Animal)
        # and is therefore invalid.
        duplicate_macro_edge_definition = """{
            Entity @macro_edge_definition(name: "in_DistantRelatedAnimal") {
                out_Entity_Related {
                    out_Entity_Related {
                        ... on Animal @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }"""

        args: Dict[str, Any] = {}

        # The two macros above are mutually incompatible, regardless of registration order.
        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, macro_edge_definition, args)
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, duplicate_macro_edge_definition, args)

        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, duplicate_macro_edge_definition, args)
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_reversal_validation_rules_origin_subclass_conflict(self) -> None:
        # Reversing a macro edge must not conflict with an existing macro edge
        # defined between different types. The first one produces a macro edge from Animal to Animal
        # whereas the reversal of the second one produces a macro edge with the same name
        # from Animal to Entity. Entity is a superclass of Animal, but it still is disallowed.
        macro_edge_definition = """{
            Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
                out_Animal_ParentOf @macro_edge_target {
                    uuid
                }
            }
        }"""

        # Meaningless macro edge that (when reversed) has the same origin type (Animal) and name,
        # but a different target type (Entity) and is therefore invalid.
        duplicate_macro_edge_definition = """{
            Entity @macro_edge_definition(name: "in_Animal_GrandparentOf") {
                out_Entity_Related {
                    ... on Animal @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""

        args: Dict[str, Any] = {}

        # The two macros above are mutually incompatible, regardless of registration order.
        # The first order tests "origin superclass" conflicts, where the conflict is caused due to
        # the fact that the origin type of the reversed edge is a superclass of the original.
        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, macro_edge_definition, args)
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, duplicate_macro_edge_definition, args)

        # The second order tests "target subclass" conflicts, where the conflict is caused due to
        # the fact that the target type of the reversed edge is a subclass of the original.
        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, duplicate_macro_edge_definition, args)
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)

    def test_macro_edge_reversal_validation_rules_origin_superclass_conflict(self) -> None:
        # Reversing a macro edge must not conflict with an existing macro edge
        # defined between different types. The first one produces a macro edge from Entity to Entity
        # whereas the reversal of the second one produces a macro edge with the same name
        # from Animal to Entity. Entity is a superclass of Animal, but it still is disallowed.
        macro_edge_definition = """{
            Entity @macro_edge_definition(name: "out_DistantRelatedEntity") {
                out_Entity_Related {
                    out_Entity_Related @macro_edge_target {
                        uuid
                    }
                }
            }
        }"""

        # Meaningless macro edge that (when reversed) has the same origin type (Animal) and name,
        # but a different target type (Entity) and is therefore invalid.
        duplicate_macro_edge_definition = """{
            Entity @macro_edge_definition(name: "in_DistantRelatedEntity") {
                in_Entity_Related {
                    in_Entity_Related {
                        ... on Animal @macro_edge_target {
                            uuid
                        }
                    }
                }
            }
        }"""

        args: Dict[str, Any] = {}

        # The two macros above are mutually incompatible, regardless of registration order.
        # The first order tests "origin subclass" conflicts, where the conflict is caused due to
        # the fact that the origin type of the reversed edge is a subclass of the original.
        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, macro_edge_definition, args)
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, duplicate_macro_edge_definition, args)

        # The second order tests "target superclass" conflicts, where the conflict is caused due to
        # the fact that the target type of the reversed edge is a superclass of the original.
        macro_registry = get_empty_test_macro_registry()
        register_macro_edge(macro_registry, duplicate_macro_edge_definition, args)
        with self.assertRaises(GraphQLInvalidMacroError):
            register_macro_edge(macro_registry, macro_edge_definition, args)
