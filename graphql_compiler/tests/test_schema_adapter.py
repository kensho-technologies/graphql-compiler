# Copyright 2020-present Kensho Technologies, LLC.
from typing import Any, ClassVar, Dict, List
from unittest import TestCase

from ..schema_adapter import SchemaAdapter, execute_query
from .test_helpers import get_schema


test_schema = get_schema()


def _ensure_query_produces_expected_output(
    test_case: "TestSchemaAdapter",
    query: str,
    args: Dict[str, Any],
    expected_results: List[Dict[str, Any]],
) -> None:
    actual_results = list(execute_query(test_case.adapter, query, args))
    # order-agnostic output comparison
    test_case.assertCountEqual(actual_results, expected_results)


class TestSchemaAdapter(TestCase):
    adapter: ClassVar[SchemaAdapter]

    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = SchemaAdapter(test_schema)

    def setUp(self) -> None:
        """Disable max diff limits for all tests."""
        self.maxDiff = None

    def test_vertex_properties_projection(self) -> None:
        query = """
        {
            VertexType {
                name @output(out_name: "vertex_name") @filter(op_name: "=", value: ["$vertex_name"])
                description @output(out_name: "vertex_description")
                is_interface @output(out_name: "is_vertex_interface")
            }
        }
        """
        args: Dict[str, Any] = {"vertex_name": "Entity"}

        expected_results = [
            {"vertex_name": "Entity", "vertex_description": None, "is_vertex_interface": True}
        ]

        _ensure_query_produces_expected_output(self, query, args, expected_results)

        args: Dict[str, Any] = {"vertex_name": "Animal"}

        expected_results = [
            {"vertex_name": "Animal", "vertex_description": None, "is_vertex_interface": False}
        ]

        _ensure_query_produces_expected_output(self, query, args, expected_results)

    def test_union_types_are_not_vertex(self) -> None:
        query = """
        {
            VertexType {
                name @output(out_name: "vertex_name") @filter(op_name: "=", value: ["$vertex_name"])
            }
        }
        """
        args: Dict[str, Any] = {"vertex_name": "Union__Food__FoodOrSpecies__Species"}

        expected_results = []

        _ensure_query_produces_expected_output(self, query, args, expected_results)

    def test_vertex_type_property_edge(self) -> None:
        query = """
        {
            VertexType {
                name @filter(op_name: "=", value: ["$vertex_name"])

                out_VertexType_Property {
                    name @output(out_name: "property_name")
                    description @output(out_name: "property_description")
                    is_deprecated @output(out_name: "is_property_deprecated")
                    type @output(out_name: "property_type")
                }
            }
        }
        """
        args: Dict[str, Any] = {"vertex_name": "UniquelyIdentifiable"}

        expected_results = [
            {
                "property_name": "_x_count",
                "property_description": None,
                "is_property_deprecated": False,
                "property_type": "Int",
            },
            {
                "property_name": "uuid",
                "property_description": None,
                "is_property_deprecated": False,
                "property_type": "ID",
            },
        ]

        _ensure_query_produces_expected_output(self, query, args, expected_results)

    # def test_vertex_type_with_no_properties(self) -> None:
    #     query = """
    #     {
    #         VertexType {
    #             name @filter(op_name: "=", value: ["$vertex_name"])

    #             out_VertexType_Property {
    #                 name @output(out_name: "property_name")
    #             }
    #         }
    #     }
    #     """
    #     args: Dict[str, Any] = {"vertex_name": "NoProperty"}

    #     expected_results = []

    #     _ensure_query_produces_expected_output(self, query, args, expected_results)
