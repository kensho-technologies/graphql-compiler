from collections import namedtuple

from graphql import build_ast_schema, parse
from graphql.language.visitor import Visitor, visit

from .utils import SchemaError, get_schema_data


RenamedSchema = namedtuple(
    'RenamedSchema', [
        'schema_ast',  # type: Document, ast representing the renamed schema
        'reverse_name_map',  # type: Dict[str, str], new type name to old type name
        'reverse_root_field_map'  # type: Dict[str, str], new root field name to old root field
    ]
)


def rename_schema(schema_string, rename_func=lambda name: name):
    """Create a RenamedSchema, where types and query root fields are renamed using rename_func.

    Args:
        schema_string: string describing a valid schema that does not contain extensions
        rename_func: callable that takes string to string, used to transform the names of
                     types, interfaces, enums, and root fields. Defaults to identity

    Returns:
        RenamedSchema

    Raises:
        SchemaError if input schema_string does not represent a valid schema without extensions,
            or if there are conflicts between the renamed types or root fields
    """
    # Check that the input string is a parseable and valid schema.
    try:
        ast = parse(schema_string)
        build_ast_schema(ast)
    except Exception as e:  # Can't be more specific -- see graphql/utils/build_ast_schema.py
        raise SchemaError('Input schema does not define a valid schema.\n'
                          'Message: {}'.format(e))

    schema_data = get_schema_data(ast)
    # Check that the input schema has no extensions
    if schema_data.has_extension:
        raise SchemaError('Input schema should not contain extensions.')

    # Rename types, interfaces, enums
    reverse_name_map = _rename_types(ast, rename_func, schema_data.query_type, schema_data.scalars)

    # Rename root fields
    reverse_root_field_map = _rename_root_fields(ast, rename_func, schema_data.query_type)

    return RenamedSchema(schema_ast=ast, reverse_name_map=reverse_name_map,
                         reverse_root_field_map=reverse_root_field_map)


def _rename_types(ast, rename_func, query_type, scalars):
    """Rename types, enums, interfaces using rename_func.

    The query type will not be renamed. Scalar types, field names, enum values will not be renamed.

    ast will be modified as a result.

    Args:
        ast: Document, the schema ast that we modify
        rename_func: callable, used to rename types, interfaces, enums, etc
        query_type: string, name of the query type, e.g. 'RootSchemaQuery'
        scalars: set of strings, the set of user defined scalars

    Returns:
        Dict[str, str], the new type name to original type name map

    Raises:
        SchemaError if the rename causes name conflicts
    """
    visitor = RenameSchemaVisitor(rename_func, query_type, scalars)
    visit(ast, visitor)

    return visitor.reverse_name_map


def _rename_root_fields(ast, rename_func, query_type):
    """Rename root fields, aka fields of the query type.

    ast will be modified as a result.

    Args:
        ast: Document, the schema ast that we modify
        rename_func: callable, used to rename fields of the query type
        query_type: string, name of the query type, e.g. 'RootSchemaQuery'

    Returns:
        Dict[str, str], the new root field name to original root field name map

    Raises:
        SchemaError if rename causes root field name conflicts
    """
    visitor = RenameRootFieldsVisitor(rename_func, query_type)
    visit(ast, visitor)

    return visitor.reverse_field_map


class RenameSchemaVisitor(Visitor):
    """Traverse a Document AST, editing the names of nodes."""
    def __init__(self, rename_func, query_type, scalar_types):
        self.rename_func = rename_func  # callable that takes string to string
        self.reverse_name_map = {}  # Dict[str, str], from new name to original name
        self.query_type = query_type  # str
        self.scalar_types = frozenset(scalar_types)
        self.builtin_types = frozenset({'String', 'Int', 'Float', 'Boolean', 'ID'})

        # NOTE: behavior of Directive type is not completely clear
        self.noop_types = frozenset({
            'Name', 'Document', 'Argument', 'IntValue', 'FloatValue', 'StringValue',
            'BooleanValue', 'EnumValue', 'ListValue', 'Directive', 'ListType', 'NonNullType',
            'SchemaDefinition', 'OperationTypeDefinition', 'ScalarTypeDefinition',
            'FieldDefinition', 'InputValueDefinition', 'EnumValueDefinition',
            'DirectiveDefinition'
        })
        self.rename_types = frozenset({
            'NamedType', 'ObjectTypeDefinition', 'InterfaceTypeDefinition',
            'UnionTypeDefinition', 'EnumTypeDefinition'
        })
        self.unexpected_types = frozenset({
            'OperationDefinition', 'SelectionSet', 'Field', 'FragmentSpread',
            'InlineFragment', 'FragmentDefinition'
        })

    def _rename_name_add_to_record(self, node):
        """Rename the value of the node, and add the name mapping to reverse_name_map.

        Don't rename if the type is the query type, a scalar type, or a builtin type.

        Args:
            node: Name type Node

        Raises:
            SchemaError if the newly renamed node causes name conflicts with existing types,
                scalars, or builtin types
        """
        name_string = node.value

        if (
            name_string == self.query_type or
            name_string in self.scalar_types or
            name_string in self.builtin_types
        ):
            return

        new_name_string = self.rename_func(name_string)

        if (
            new_name_string in self.reverse_name_map and
            self.reverse_name_map[new_name_string] != name_string
        ):
            raise SchemaError(
                '"{}" and "{}" are both renamed to "{}"'.format(
                    name_string, self.reverse_name_map[new_name_string], new_name_string
                )
            )
        if new_name_string in self.scalar_types:
            raise SchemaError(
                '"{}" was renamed to "{}", clashing with scalar "{}"'.format(
                    name_string, new_name_string, new_name_string
                )
            )
        if new_name_string in self.builtin_types:
            raise SchemaError(
                '"{}" was renamed to "{}", clashing with builtin "{}"'.format(
                    name_string, new_name_string, new_name_string
                )
            )

        node.value = new_name_string
        self.reverse_name_map[new_name_string] = name_string

    def enter(self, node, key, parent, path, ancestors):
        node_type = type(node).__name__
        if node_type in self.noop_types:
            # Do nothing, continue traversal
            return None
        elif node_type in self.rename_types:
            # Rename and put into record the name attribute of current node; continue traversal
            self._rename_name_add_to_record(node.name)
        elif node_type in self.unexpected_types:
            # Node type unexpected in schema definition, raise error
            raise SchemaError('Node type "{}" unexpected in schema AST'.format(node_type))
        elif node_type == 'TypeExtensionDefinition':
            raise SchemaError('Extension definition not allowed')
        else:
            # VariableDefinition, Variable, ObjectValue, ObjectField, InputObjectTypeDefinition
            # The above types I'm not sure what to do about
            # TODO
            raise AssertionError('Missed type: "{}"'.format(node_type))


class RenameRootFieldsVisitor(Visitor):
    def __init__(self, rename_func, query_type):
        self.in_query_type = False
        self.reverse_field_map = {}
        self.rename_func = rename_func
        self.query_type = query_type

    def enter_ObjectTypeDefinition(self, node, *args):
        """If entering query type, set flag to True."""
        if node.name.value == self.query_type:
            self.in_query_type = True

    def leave_ObjectTypeDefinition(self, node, key, parent, path, ancestors):
        """If leaving query type, set flag to False."""
        if node.name.value == self.query_type:
            self.in_query_type = False

    def enter_FieldDefinition(self, node, *args):
        """If entering field under query type, rename and add to reverse map."""
        if self.in_query_type:
            field_name = node.name.value
            new_field_name = self.rename_func(field_name)

            if (
                new_field_name in self.reverse_field_map and
                self.reverse_field_map[new_field_name] != field_name
            ):
                raise SchemaError(
                    '"{}" and "{}" are both renamed to "{}"'.format(
                        field_name, self.reverse_field_map[new_field_name], new_field_name
                    )
                )

            node.name.value = new_field_name
            self.reverse_field_map[new_field_name] = field_name
