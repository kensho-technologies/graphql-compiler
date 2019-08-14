# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import copy

from graphql.language import ast as ast_types
from graphql.language.visitor import TypeInfoVisitor, Visitor, visit
from graphql.utils.type_info import TypeInfo

from ..ast_manipulation import get_only_query_definition
from ..compiler.helpers import strip_non_null_and_list_from_type
from ..exceptions import GraphQLValidationError
from ..schema import FilterDirective, OptionalDirective, OutputDirective
from .utils import (
    SchemaStructureError, check_query_is_valid_to_split, is_property_field_ast,
    try_get_ast_by_name_and_type
)


QueryConnection = namedtuple(
    'QueryConnection', (
        'sink_query_node',  # SubQueryNode
        'source_field_out_name',
        # str, the unique out name on the @output of the the source property field in the stitch
        'sink_field_out_name',
        # str, the unique out name on the @output of the the sink property field in the stitch
    )
)


class SubQueryNode(object):
    def __init__(self, query_ast):
        """Represents one piece of a larger query, targeting one schema.

        Args:
            query_ast: Document, representing one piece of a query
        """
        self.query_ast = query_ast
        self.schema_id = None  # str, identifying the schema that this query targets
        self.parent_query_connection = None
        # SubQueryNode or None, the query that the current query depends on
        self.child_query_connections = []
        # List[SubQueryNode], the queries that depend on the current query


def _get_output_directive(out_name):
    """Return a Directive representing an @output with the input out_name."""
    return ast_types.Directive(
        name=ast_types.Name(value=OutputDirective.name),
        arguments=[
            ast_types.Argument(
                name=ast_types.Name(value=u'out_name'),
                value=ast_types.StringValue(value=out_name),
            ),
        ],
    )


def _get_query_document(root_vertex_field_name, root_selections):
    """Return a Document representing a query with the specified name and selections."""
    return ast_types.Document(
        definitions=[
            ast_types.OperationDefinition(
                operation='query',
                selection_set=ast_types.SelectionSet(
                    selections=[
                        ast_types.Field(
                            name=ast_types.Name(value=root_vertex_field_name),
                            selection_set=ast_types.SelectionSet(
                                selections=root_selections,
                            ),
                            directives=[],
                        )
                    ]
                )
            )
        ]
    )


def _add_query_connections(parent_query_node, child_query_node, parent_field_out_name,
                           child_field_out_name):
    """Modify parent and child SubQueryNodes by adding QueryConnections between them."""
    # Create QueryConnections
    new_query_connection_from_parent = QueryConnection(
        sink_query_node=child_query_node,
        source_field_out_name=parent_field_out_name,
        sink_field_out_name=child_field_out_name,
    )
    new_query_connection_from_child = QueryConnection(
        sink_query_node=parent_query_node,
        source_field_out_name=child_field_out_name,
        sink_field_out_name=parent_field_out_name,
    )
    # Add QueryConnections
    parent_query_node.child_query_connections.append(new_query_connection_from_parent)
    child_query_node.parent_query_connection = new_query_connection_from_child


class IntermediateOutNameAssigner(object):
    """Used to generate and keep track of out_name of @output directives."""

    def __init__(self):
        """Create assigner with empty records."""
        self.intermediate_output_names = set()
        self.intermediate_output_count = 0

    def assign_and_return_out_name(self):
        """Assign and return name, increment count, add name to records."""
        out_name = '__intermediate_output_' + str(self.intermediate_output_count)
        self.intermediate_output_count += 1
        self.intermediate_output_names.add(out_name)
        return out_name
