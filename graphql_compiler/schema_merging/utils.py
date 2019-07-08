# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql.language.visitor import Visitor, visit


class SchemaError(Exception):
    pass


SchemaData = namedtuple('SchemaData', ['query_type', 'scalars', 'directives'])


class GetSchemaDataVisitor(Visitor):
    """Gather information about the schema to aid any transforms."""
    def __init__(self):
        self.query_type = None  # str, name of the query type, e.g. 'RootSchemaQuery'
        self.scalars = set()  # Set[str], names of scalar types
        self.directives = set()  # Set[str], names of directives
        self.schema_data = None

    def enter_OperationTypeDefinition(self, node, *args):
        """Set name of type query if entering query definition."""
        if node.operation == 'query':
            self.query_type = node.type.name.value

    def enter_ScalarTypeDefinition(self, node, *args):
        """Add to records the name of user defined scalar type."""
        self.scalars.add(node.name.value)

    def enter_DirectiveDefinition(self, node, *args):
        """Add to records the name of user defined directive type."""
        # NOTE: currently we don't check if the definitions of the directives agree.
        self.directives.add(node.name.value)

    def leave_Document(self, node, *args):
        """Organize information into a SchemaData object."""
        self.schema_data = SchemaData(query_type=self.query_type,
                                      scalars=self.scalars,
                                      directives=self.directives)


def get_schema_data(ast):
    """Get schema data of input ast.

    Args:
        ast: Document

    Returns:
        SchemaData
    """
    get_schema_data_visitor = GetSchemaDataVisitor()
    visit(ast, get_schema_data_visitor)
    return get_schema_data_visitor.schema_data
