# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql.language.ast import (
    Argument, Directive, Document, Field, Name, OperationDefinition, SelectionSet, StringValue
)

from ..schema import OutputDirective


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
    return Directive(
        name=Name(value=OutputDirective.name),
        arguments=[
            Argument(
                name=Name(value=u'out_name'),
                value=StringValue(value=out_name),
            ),
        ],
    )


def _get_query_document(root_vertex_field_name, root_selections):
    """Return a Document representing a query with the specified name and selections."""
    return Document(
        definitions=[
            OperationDefinition(
                operation='query',
                selection_set=SelectionSet(
                    selections=[
                        Field(
                            name=Name(value=root_vertex_field_name),
                            selection_set=SelectionSet(
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
    if child_query_node.parent_query_connection is not None:
        raise AssertionError(
            u'The input child query node already has a parent connection, {}'.format(
                child_query_node.parent_query_connection
            )
        )
    if any(
        query_connection_from_parent.sink_query_node is child_query_node
        for query_connection_from_parent in parent_query_node.child_query_connections
    ):
        raise AssertionError(
            u'The input parent query node already has the child query node in a child query '
            u'connection.'
        )
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
