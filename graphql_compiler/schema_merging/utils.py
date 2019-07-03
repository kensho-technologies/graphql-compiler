from graphql.language.visitor import Visitor, visit


class SchemaError(Exception):
    pass


class SchemaData(object):
    def __init__(self):
        self.query_type = None  # str, name of the query type, e.g. 'RootSchemaQuery'
        self.scalars = set()  # Set(str), names of scalar types
        self.directives = set()  # Set(str), names of directives
        self.has_extension = False


class GetSchemaDataVisitor(Visitor):
    """Gather information about the schema to aid any transforms."""
    def __init__(self):
        self.schema_data = SchemaData()

    def enter_TypeExtensionDefinition(self, node, *args):
        self.schema_data.has_extension = True

    def enter_OperationTypeDefinition(self, node, *args):
        if node.operation == 'query':
            self.schema_data.query_type = node.type.name.value

    def enter_ScalarTypeDefinition(self, node, *args):
        self.schema_data.scalars.add(node.name.value)

    def enter_DirectiveDefinition(self, node, *args):
        # NOTE: currently we don't check if the definitions of the directives agree.
        self.schema_data.directives.add(node.name.value)


def get_schema_data(ast):
    """Get schema data of input ast.

    Args:
        ast: Document

    Return:
        SchemaData
    """
    get_schema_data_visitor = GetSchemaDataVisitor()
    visit(ast, get_schema_data_visitor)
    return get_schema_data_visitor.schema_data
