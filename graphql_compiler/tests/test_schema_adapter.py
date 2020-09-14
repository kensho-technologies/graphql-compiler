# Copyright 2020-present Kensho Technologies, LLC.
from typing import Any, ClassVar, Dict, List
from unittest import TestCase

from graphql import build_ast_schema, parse

from ..schema_adapter import SchemaAdapter, execute_query
from .test_helpers import SCHEMA_TEXT, get_schema


test_schema = get_schema()

# Schema with a type that has no property
no_property_schema = build_ast_schema(
    parse(
        SCHEMA_TEXT
        + (
            """
    type NoProperty {
        out_NoProperty_Edge: [NoProperty]
    }
    """
        )
    )
)


def _ensure_query_produces_expected_output(
    test_case: "TestSchemaAdapter",
    adapter: SchemaAdapter,
    query: str,
    args: Dict[str, Any],
    expected_results: List[Dict[str, Any]],
) -> None:
    actual_results = list(execute_query(adapter, query, args))
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

        _ensure_query_produces_expected_output(self, self.adapter, query, args, expected_results)

        args = {"vertex_name": "Animal"}

        expected_results = [
            {"vertex_name": "Animal", "vertex_description": None, "is_vertex_interface": False}
        ]

        _ensure_query_produces_expected_output(self, self.adapter, query, args, expected_results)

    def test_union_types_are_not_vertex(self) -> None:
        query = """
        {
            VertexType {
                name @output(out_name: "vertex_name") @filter(op_name: "=", value: ["$vertex_name"])
            }
        }
        """
        args: Dict[str, Any] = {"vertex_name": "Union__Food__FoodOrSpecies__Species"}

        expected_results: List[Dict[str, Any]] = []

        _ensure_query_produces_expected_output(self, self.adapter, query, args, expected_results)

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

        _ensure_query_produces_expected_output(self, self.adapter, query, args, expected_results)

    def test_vertex_type_with_no_properties(self) -> None:
        # use special custom adapter with the NoProperty type
        no_property_adapter = SchemaAdapter(no_property_schema)

        query = """
        {
            VertexType {
                name @filter(op_name: "=", value: ["$vertex_name"])

                out_VertexType_Property {
                    name @output(out_name: "property_name")
                }
            }
        }
        """
        args: Dict[str, Any] = {"vertex_name": "NoProperty"}

        expected_results: List[Dict[str, Any]] = []

        _ensure_query_produces_expected_output(
            self, no_property_adapter, query, args, expected_results
        )

        # make sure NoProperty vertex exists
        query = """
        {
            VertexType {
                name @filter(op_name: "=", value: ["$vertex_name"])
                     @output(out_name: "vertex_name")
            }
        }
        """
        args = {"vertex_name": "NoProperty"}

        expected_results = [{"vertex_name": "NoProperty"}]

        _ensure_query_produces_expected_output(
            self, no_property_adapter, query, args, expected_results
        )
