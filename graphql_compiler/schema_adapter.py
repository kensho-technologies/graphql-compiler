# Copyright 2020-present Kensho Technologies, LLC.
"""Module to create a schema adapter to run queries over a schema's information.

This module provides a schema adapter that allows you to write queries to query over
schema information, like type names, docstrings, property types, etc.

In our adapter's schema, VertexType only considers objects of GraphQLObject and GraphQLInterface
types as these are the only types that have relation to each other (via edges and implementations).
Property, in our adapter's schema, represent fields (that are not edges) on GraphQL schema types.
Hence, in our adapter's schema, there is an edge from VertexType to Property that denotes this
relationship between types and their fields.

To use this schema adapter, say schema A is the GraphQL schema we want to query its information,
we must first create an adapter (essentially the middleware to run queries on an arbitrary data
source) by instantiating a schema adapter:

```
adapter = SchemaAdapter(A)
```

Then, you can write a simple query with args and then use the `execute_query` API to actually
execute the query on the schema adapter you created above. The following query gets the name of
all the vertices in schema A.

```
query = '''
{
    VertexType {
        name @output(out_name: "vertex_name")
    }
}
'''
args: Dict[str, Any] = {}

results = list(execute_query(adapter, query, args))
```
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, Iterable, List, Tuple, TypeVar, Union, cast

from graphql import (
    GraphQLField,
    GraphQLInterfaceType,
    GraphQLObjectType,
    GraphQLSchema,
    build_ast_schema,
    is_interface_type,
    is_list_type,
    is_object_type,
    parse,
)

from graphql_compiler.compiler.compiler_frontend import graphql_to_ir
from graphql_compiler.interpreter import DataContext, InterpreterAdapter, interpret_ir
from graphql_compiler.interpreter.typedefs import EdgeInfo
from graphql_compiler.schema import (
    INBOUND_EDGE_FIELD_PREFIX,
    OUTBOUND_EDGE_FIELD_PREFIX,
    is_vertex_field_name,
)


SCHEMA_BASE = """
schema {
    query: RootSchemaQuery
}
directive @filter(
    \"\"\"Name of the filter operation to perform.\"\"\"
    op_name: String!
    \"\"\"List of string operands for the operator.\"\"\"
    value: [String!]
) repeatable on FIELD | INLINE_FRAGMENT
directive @tag(
    \"\"\"Name to apply to the given property field.\"\"\"
    tag_name: String!
) on FIELD
directive @output(
    \"\"\"What to designate the output field generated from this property field.\"\"\"
    out_name: String!
) on FIELD
directive @output_source on FIELD
directive @optional on FIELD
directive @recurse(
    \"\"\"
    Recurse up to this many times on this edge. A depth of 1 produces the current
    vertex and its immediate neighbors along the given edge.
    \"\"\"
    depth: Int!
) on FIELD
directive @fold on FIELD
directive @macro_edge on FIELD_DEFINITION
directive @stitch(source_field: String!, sink_field: String!) on FIELD_DEFINITION
"""


SCHEMA_TEXT = (
    SCHEMA_BASE
    + """
type VertexType {
    name: String
    description: String
    is_interface: Boolean
    out_VertexType_Property: [Property]
    out_VertexType_Neighbor: [VertexType]
    out_VertexType_InboundEdge: [EdgeType]
    out_VertexType_OutboundEdge: [EdgeType]
}

type Property {
    name: String
    description: String
    is_deprecated: Boolean
    type: String
}

type EdgeType {
    name: String
    in_VertexType_InboundEdge: [VertexType]
    in_VertexType_OutboundEdge: [VertexType]
}

type RootSchemaQuery {
    VertexType: [VertexType]
}
"""
)
SCHEMA = build_ast_schema(parse(SCHEMA_TEXT))


T = TypeVar("T")
GraphQLVertexType = Union[GraphQLObjectType, GraphQLInterfaceType]


@dataclass
class SchemaToken(Generic[T]):
    """Dataclass that represents a generic SchemaToken with the type name and actual value."""

    type_name: str
    value: T


@dataclass
class VertexType:
    """Dataclass VertexType represents a GraphQL type in the schema being queried."""

    named_type: GraphQLVertexType


@dataclass
class Property:
    """Dataclass Property represents a GraphQL field (of a type) in the schema being queried."""

    name: str
    field: GraphQLField


@dataclass
class EdgeType:
    """Dataclass EdgeType represents a directed edge between GraphQL types."""

    name: str
    inbound_named_type: GraphQLVertexType
    outbound_named_type: GraphQLVertexType


def _project_vertex_properties(field_name: str, token: SchemaToken[VertexType]) -> Any:
    """Compute property with field_name for VertexType objects."""
    vertex = token.value
    named_type = vertex.named_type
    if field_name == "name":
        return named_type.name
    elif field_name == "description":
        return named_type.description
    elif field_name == "is_interface":
        return is_interface_type(named_type)
    else:
        raise NotImplementedError(
            f"Unknown {field_name} property to project for {token.type_name}."
        )


def _project_property_properties(field_name: str, token: SchemaToken[Property]) -> Any:
    """Compute property with field_name for Property objects."""
    property_obj = token.value
    field = property_obj.field
    if field_name == "name":
        return property_obj.name
    elif field_name == "description":
        return field.description
    elif field_name == "is_deprecated":
        return field.is_deprecated
    elif field_name == "type":
        return str(field.type)
    else:
        raise NotImplementedError(
            f"Unknown {field_name} property to project for {token.type_name}."
        )


def _project_edge_properties(field_name: str, token: SchemaToken[EdgeType]) -> Any:
    """Compute property with field_name for EdgeType objects."""
    edge = token.value
    if field_name == "name":
        return edge.name
    else:
        raise NotImplementedError(
            f"Unknown {field_name} property to project for {token.type_name}."
        )


def _project_vertex_property_neighbors(
    token: SchemaToken[VertexType],
) -> List[SchemaToken[Property]]:
    """Compute all Property objects for a given VertexType for the out_VertexType_Property edge."""
    vertex = token.value
    named_type = vertex.named_type
    if not (is_interface_type(named_type) or is_object_type(named_type)):
        raise AssertionError(
            f"Cannot find property neighbors of {named_type.name} which is not an interface/object."
        )

    property_tokens = []
    for field_name, field in named_type.fields.items():
        if not is_vertex_field_name(field_name):
            property_tokens.append(SchemaToken[Property]("Property", Property(field_name, field)))
    return property_tokens


def _project_vertex_neighbors_neighbors(
    token: SchemaToken[VertexType],
) -> List[SchemaToken[VertexType]]:
    """Compute all neighboring VertexType objects for the given vertex."""
    vertex = token.value
    named_type = vertex.named_type
    neighbor_tokens = []
    for field_name, field in named_type.fields.items():
        if is_vertex_field_name(field_name):
            maybe_list_type = field.type
            if not is_list_type(maybe_list_type):
                raise AssertionError(f"{field_name} has edges that are not list type.")
            neighbor_type = maybe_list_type.of_type
            if not (is_interface_type(neighbor_type) or is_object_type(neighbor_type)):
                raise AssertionError(
                    f"Cannot find property neighbors of {neighbor_type.name}"
                    "which is not an interface/object."
                )
            neighbor_tokens.append(SchemaToken[VertexType]("VertexType", VertexType(neighbor_type)))
    return neighbor_tokens


def _project_vertex_outbound_neighbors(
    token: SchemaToken[VertexType],
) -> List[SchemaToken[EdgeType]]:
    """Compute all outbound edges (EdgeType) for a given vertex."""
    vertex = token.value
    named_type = vertex.named_type
    outbound_edges = []
    for field_name, field in named_type.fields.items():
        if field_name.startswith(OUTBOUND_EDGE_FIELD_PREFIX):
            maybe_list_type = field.type
            if not is_list_type(maybe_list_type):
                raise AssertionError(f"{field_name} has edges that are not list type.")
            neighbor_type = maybe_list_type.of_type
            if not (is_interface_type(neighbor_type) or is_object_type(neighbor_type)):
                raise AssertionError(
                    f"Cannot find property neighbors of {neighbor_type.name}"
                    "which is not an interface/object."
                )
            outbound_edges.append(
                SchemaToken[EdgeType]("EdgeType", EdgeType(field_name, neighbor_type, named_type))
            )
    return outbound_edges


def _project_vertex_inbound_neighbors(
    token: SchemaToken[VertexType],
) -> List[SchemaToken[EdgeType]]:
    """Compute all inbound edges (EdgeType) for a given vertex."""
    vertex = token.value
    named_type = vertex.named_type
    inbound_edges = []
    for field_name, field in named_type.fields.items():
        if field_name.startswith(INBOUND_EDGE_FIELD_PREFIX):
            maybe_list_type = field.type
            if not is_list_type(maybe_list_type):
                raise AssertionError(f"{field_name} has edges that are not list type.")
            neighbor_type = maybe_list_type.of_type
            if not (is_interface_type(neighbor_type) or is_object_type(neighbor_type)):
                raise AssertionError(
                    f"Cannot find property neighbors of {neighbor_type.name}"
                    "which is not an interface/object."
                )
            inbound_edges.append(
                SchemaToken[EdgeType]("EdgeType", EdgeType(field_name, named_type, neighbor_type))
            )
    return inbound_edges


def _project_edge_inbound_neighbors(token: SchemaToken[EdgeType]) -> List[SchemaToken[VertexType]]:
    """Compute all VertexType objects that are on the inbound end for a given edge."""
    edge = token.value
    return [SchemaToken[VertexType]("VertexType", VertexType(edge.inbound_named_type))]


def _project_edge_outbound_neighbors(token: SchemaToken[EdgeType]) -> List[SchemaToken[VertexType]]:
    """Compute all VertexType objects that are on the outbound end for a given edge."""
    edge = token.value
    return [SchemaToken[VertexType]("VertexType", VertexType(edge.outbound_named_type))]


def _get_vertex_tokens(schema: GraphQLSchema) -> List[SchemaToken[VertexType]]:
    """Compute all VertexType tokens in the schema being queried."""
    vertex_tokens = []
    for type_ in schema.type_map.values():
        # We filter out introspection types here also
        if (is_interface_type(type_) or is_object_type(type_)) and not type_.name.startswith("__"):
            vertex_type = VertexType(cast(GraphQLVertexType, type_))
            vertex_tokens.append(SchemaToken[VertexType]("VertexType", vertex_type))

    return vertex_tokens


class SchemaAdapter(InterpreterAdapter[SchemaToken]):
    def __init__(self, schema: GraphQLSchema) -> None:
        """Construct a SchemaAdapter object with the GraphQL schema to be queried over.

        Args:
            schema: GraphQL schema object (the data source for querying on schema),
                    obtained from the graphql library

        Returns:
            SchemaAdapter object which can be used to run queries on the given GraphQL schema object
        """
        self.schema = schema

    def get_tokens_of_type(self, type_name: str, **hints: Any) -> Iterable[SchemaToken]:
        """Compute tokens of a specific type given by the root query."""
        if type_name == "VertexType":
            return _get_vertex_tokens(self.schema)
        else:
            raise NotImplementedError(f"Failed to get tokens of type {type_name}.")

    def project_property(
        self,
        data_contexts: Iterable[DataContext[SchemaToken]],
        current_type_name: str,
        field_name: str,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[SchemaToken], Any]]:
        """Compute property with field_name for all data contexts."""
        dispatch: Dict[str, Callable[[str, SchemaToken], Any]] = {
            "Property": _project_property_properties,
            "VertexType": _project_vertex_properties,
            "EdgeType": _project_edge_properties,
        }
        for data_context in data_contexts:
            current_token = data_context.current_token
            current_value = None
            if current_token is not None:
                type_name = current_token.type_name
                handler = dispatch.get(type_name, None)
                if handler is None:
                    raise NotImplementedError(
                        f"Failed to find property projection handler for {type_name}."
                    )
                current_value = handler(field_name, current_token)

            yield (data_context, current_value)

    def project_neighbors(
        self,
        data_contexts: Iterable[DataContext[SchemaToken]],
        current_type_name: str,
        edge_info: EdgeInfo,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[SchemaToken], Iterable[SchemaToken]]]:
        """Compute neighbors of current_type_name and edge_info for all data contexts."""
        edge_handlers: Dict[Tuple[str, EdgeInfo], Callable[[SchemaToken], List[SchemaToken]]] = {
            ("VertexType", ("out", "VertexType_Property")): _project_vertex_property_neighbors,
            ("VertexType", ("out", "VertexType_Neighbor")): _project_vertex_neighbors_neighbors,
            ("VertexType", ("out", "VertexType_InboundEdge")): _project_vertex_inbound_neighbors,
            ("VertexType", ("out", "VertexType_OutboundEdge")): _project_vertex_outbound_neighbors,
            ("EdgeType", ("in", "VertexType_InboundEdge")): _project_edge_inbound_neighbors,
            ("EdgeType", ("in", "VertexType_OutboundEdge")): _project_edge_outbound_neighbors,
        }
        handler_key = (current_type_name, edge_info)
        handler_for_edge = edge_handlers.get(handler_key, None)
        if handler_for_edge is None:
            raise NotImplementedError(
                f"Failed to find neighbors projection handler for {handler_key}."
            )
        for data_context in data_contexts:
            token = data_context.current_token
            neighbors = []
            if token is not None:
                neighbors = handler_for_edge(token)

            yield (data_context, neighbors)

    def can_coerce_to_type(
        self,
        data_contexts: Iterable[DataContext[SchemaToken]],
        current_type_name: str,
        coerce_to_type_name: str,
        **hints: Any,
    ) -> Iterable[Tuple[DataContext[SchemaToken], bool]]:
        """Compute type coercions if necessary."""
        raise NotImplementedError(f"Failed to coerce {current_type_name} to {coerce_to_type_name}")


def execute_query(
    adapter: SchemaAdapter, query: str, args: Dict[str, Any]
) -> Iterable[Dict[str, Any]]:
    """Execute a query (with args) using the SchemaAdapter object (on a specific GraphQLSchema).

    Args:
        adapter: SchemaAdapter object, created using the get_adapter function
        query: string containing the query to be executed on the schema
        args: dict mapping strings to any type, containing the arguments for the query

    Returns:
        generator of dicts mapping strings to any type, the results of the query applied to schema

        (You can call list() on the generator to get full results.)
    """
    ir_and_metadata = graphql_to_ir(SCHEMA, query)
    return interpret_ir(adapter, ir_and_metadata, args)
