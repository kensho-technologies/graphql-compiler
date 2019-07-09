# Copyright 2019-present Kensho Technologies, LLC.
from graphql.type.definition import GraphQLScalarType
from graphql.language.ast import NamedType
from graphql.language.visitor import Visitor, visit


class SchemaError(Exception):
    """Parent of specific error classes."""


class SchemaStructureError(SchemaError):
    """Raised if a schema's structure is illegal.

    This may happen if an ast cannot be built into a schema, if the schema contains disallowed
    components, or if the schema contains root fields that are named differently from the type
    it queries.
    """


class SchemaRenameConflictError(SchemaError):
    """Raised when renaming types or root fields cause name conflicts."""


def get_query_type_name(schema):
    """Get the name of the query type of the input schema.

    Args:
        schema: GraphQLSchema

    Returns:
        str, name of the query type (e.g. RootSchemaQuery)
    """
    return schema.get_query_type().name


def get_scalar_names(schema):
    """Get names of all scalars used in the input schema.

    Includes all user defined scalars, as well as any builtin scalars used in the schema; excludes
    builtin scalars not used in the schema.

    Returns:
        Set[str], set of names of scalars used in the schema
    """
    type_map = schema.get_type_map()
    scalars = {
        type_name for type_name in type_map if isinstance(type_map[type_name], GraphQLScalarType)
    }
    return scalars


class CheckRootFieldsNameMatchVisitor(Visitor):
    """Check every root field's name is identical to the type it queries.

    If not, raise SchemaStructureError.
    """
    def __init__(self, query_type):
        self.query_type = query_type
        self.in_query_type = False

    def enter_ObjectTypeDefinition(self, node, *args):
        """If entering query type, set flag to True."""
        if node.name.value == self.query_type:
            self.in_query_type = True

    def leave_ObjectTypeDefinition(self, node, *args):
        """If leaving query type, set flag to False."""
        if node.name.value == self.query_type:
            self.in_query_type = False

    def enter_FieldDefinition(self, node, *args):
        """If entering field under query type (root field), check that the names match.

        Raises:
            SchemaStructureError if the root field name is not identical to the name of the type
            that it queries
        """
        if self.in_query_type:
            field_name = node.name.value
            type_node = node.type
            # NamedType node may be wrapped in several layers of NonNullType or ListType
            while not isinstance(type_node, NamedType):
                type_node = type_node.type
            queried_type_name = type_node.name.value
            if field_name != queried_type_name:
                raise SchemaStructureError(
                    'Root field name "{}" does not match corresponding queried type '
                    'name "{}"'.format(field_name, queried_type_name)
                )


def check_root_fields_name_match(ast, query_type):
    """Check every root field's name is identical to the type it queries.

    Args:
        ast: Document representing a schema
        query_type: str, name of the query type

    Raises:
        SchemaStructureError if any root field name is not identical to the name of the type that
        it queries
    """
    visitor = CheckRootFieldsNameMatchVisitor(query_type)
    visit(ast, visitor)
