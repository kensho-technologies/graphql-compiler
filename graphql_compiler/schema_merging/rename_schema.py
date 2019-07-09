# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql import build_ast_schema, parse
from graphql.language.visitor import Visitor, visit

from .utils import (
    SchemaRenameConflictError, SchemaStructureError, check_root_fields_name_match,
    get_query_type_name, get_scalar_names
)


RenamedSchema = namedtuple(
    'RenamedSchema', (
        'schema_ast',  # type: Document, ast representing the renamed schema
        'reverse_name_map',  # type: Dict[str, str], renamed type/root field name to original name
    )
)


def rename_schema(schema_string, rename_dict):
    """Create a RenamedSchema, where types and query root fields are renamed using rename_dict.

    Any type, interface, enum, or root field (fields of the root type/query type) whose name
    appears in rename_dict will be renamed to the corresponding value. Any such names that do not
    appear in rename_dict will be unchanged. Scalars, directives, enum values, and fields not
    belonging to the root type will never be renamed.

    Args:
        schema_string: string describing a valid schema that does not contain extensions,
                       input object definitions, mutations, or subscriptions, whose root fields
                       share the same name as the types they query
        rename_dict: Dict[str, str], mapping original type/field names to renamed type/field names.
                     Type or root field names that do not appear in the dict will be unchanged.
                     Any dict-like object that implements get(key, [default]) and
                     __contains__ may also be used

    Returns:
        RenamedSchema, a namedtuple that contains the ast of the renamed schema, and the map
        of renamed type/root field names to original names. All names are included in the map,
        even those that are unchanged

    Raises:
        GraphQLSyntaxError if input string cannot be parsed
        SchemaStructureError if the schema does not have the expected form; in particular, if
        the parsed ast does not represent a valid schema, if any root field does not have the
        same name as the type that it queries, if the schema contains type definitions or
        input object definitions, or if the schema contains mutations or subscriptions
        SchemaRenameConflictError if there are conflicts between the renamed types or root fields
    """
    # Check that the input string is a parseable
    # May raise GraphQLSyntaxerror
    ast = parse(schema_string)

    # Check that the ast can be built into a valid schema
    try:
        # May raise Exception -- see graphql/utils/build_ast_schema.py
        schema = build_ast_schema(ast)
    except Exception as e:
        raise SchemaStructureError('Input is not a valid schema. Message: {}'.format(e))

    if schema.get_mutation_type() is not None:
        raise SchemaStructureError('Schema contains mutations.')

    if schema.get_subscription_type() is not None:
        raise SchemaStructureError('Schema contains subscriptions.')

    query_type = get_query_type_name(schema)
    scalars = get_scalar_names(schema)

    # Check root field names match up with their queried types
    check_root_fields_name_match(ast, query_type)

    # Rename types, interfaces, enums
    reverse_name_map = _rename_types(ast, rename_dict, query_type, scalars)

    # Rename root fields
    _rename_root_fields(ast, rename_dict, query_type)

    return RenamedSchema(schema_ast=ast, reverse_name_map=reverse_name_map)


def _rename_types(ast, rename_dict, query_type, scalars):
    """Rename types, enums, interfaces using rename_dict.

    The query type will not be renamed. Scalar types, field names, enum values will not be renamed.

    ast will be modified as a result.

    Args:
        ast: Document, the schema ast that we modify
        rename_dict: Dict[str, str], mapping original type/interface/enum name to renamed name. If
                     a name does not appear in the dict, it will be unchanged
        query_type: str, name of the query type, e.g. 'RootSchemaQuery'
        scalars: Set[str], the set of all scalars used in the schema, including user defined
                 scalars and and used builtin scalars, excluding unused builtins

    Returns:
        Dict[str, str], the renamed type name to original type name map

    Raises:
        SchemaRenameConflictError if the rename causes name conflicts
    """
    visitor = RenameSchemaTypesVisitor(rename_dict, query_type, scalars)
    visit(ast, visitor)

    return visitor.reverse_name_map


def _rename_root_fields(ast, rename_dict, query_type):
    """Rename root fields, aka fields of the query type.

    ast will be modified as a result.

    Args:
        ast: Document, the schema ast that we modify
        rename_dict: Dict[str, str], mapping original root field name to renamed name. If a name
                     does not appear in the dict, it will be unchanged
        query_type: string, name of the query type, e.g. 'RootSchemaQuery'

    Raises:
        SchemaRenameConflictError if rename causes root field name conflicts
    """
    visitor = RenameRootFieldsVisitor(rename_dict, query_type)
    visit(ast, visitor)


class RenameSchemaTypesVisitor(Visitor):
    """Traverse a Document AST, editing the names of nodes."""

    noop_types = frozenset({
        'Argument',
        'BooleanValue',
        'Directive',
        'DirectiveDefinition',
        'Document',
        'EnumValue',
        'EnumValueDefinition',
        'FieldDefinition',
        'FloatValue',
        'InputValueDefinition',
        'IntValue',
        'ListValue',
        'ListType',
        'Name',
        'NonNullType',
        'OperationTypeDefinition',
        'ScalarTypeDefinition',
        'SchemaDefinition',
        'StringValue',
    })
    rename_types = frozenset({
        'EnumTypeDefinition',
        'InterfaceTypeDefinition',
        'NamedType',
        'ObjectTypeDefinition',
        'UnionTypeDefinition',
    })
    unexpected_types = frozenset({
        'Field',
        'FragmentDefinition',
        'FragmentSpread',
        'InlineFragment',
        'ObjectField',
        'ObjectValue',
        'OperationDefinition',
        'SelectionSet',
        'Variable',
        'VariableDefinition',
    })
    disallowed_types = frozenset({
        'InputObjectTypeDefinition',
        'TypeExtensionDefinition',
    })

    def __init__(self, rename_dict, query_type, scalar_types):
        self.rename_dict = rename_dict
        # Dict[str, str], from original type name to renamed type name; any name not in the dict
        # will be unchanged
        self.reverse_name_map = {}  # Dict[str, str], from renamed type name to original type name
        self.query_type = query_type  # str
        self.scalar_types = frozenset(scalar_types)  # Set[str], all scalars in schema
        self.builtin_types = frozenset({'String', 'Int', 'Float', 'Boolean', 'ID'})

    def _rename_name_add_to_record(self, node):
        """Rename the value of the node, and add the name mapping to reverse_name_map.

        Don't rename if the type is the query type, a scalar type, or a builtin type.

        Modifies node and potentially modifies reverse_name_map.

        Args:
            node: type Name (see graphql/language/ast), an object describing the name of an ast
                  element such as type, interface, or scalar (user defined or builtin)

        Raises:
            SchemaRenameConflictError if the newly renamed node causes name conflicts with
            existing types, scalars, or builtin types
        """
        name_string = node.value

        if name_string == self.query_type or name_string in self.scalar_types:
            return

        new_name_string = self.rename_dict.get(name_string, name_string)  # Default use original

        if (
            new_name_string in self.reverse_name_map and
            self.reverse_name_map[new_name_string] != name_string
        ):
            raise SchemaRenameConflictError(
                u'"{}" and "{}" are both renamed to "{}"'.format(
                    name_string, self.reverse_name_map[new_name_string], new_name_string
                )
            )
        if new_name_string in self.scalar_types or new_name_string in self.builtin_types:
            raise SchemaRenameConflictError(
                u'"{}" was renamed to "{}", clashing with scalar "{}"'.format(
                    name_string, new_name_string, new_name_string
                )
            )

        node.value = new_name_string
        self.reverse_name_map[new_name_string] = name_string

    def enter(self, node, key, parent, path, ancestors):
        """Upon entering a node, operate depending on node type."""
        node_type = type(node).__name__
        if node_type in self.noop_types:
            # Do nothing, continue traversal
            return None
        elif node_type in self.rename_types:
            # Rename and put into record the name attribute of current node; continue traversal
            self._rename_name_add_to_record(node.name)
        elif node_type in self.unexpected_types:
            # Node type unexpected in schema definition, raise error
            raise SchemaStructureError(
                u'Node type "{}" unexpected in schema AST'.format(node_type)
            )
        elif node_type in self.disallowed_types:
            # Node type possible in schema definition but disallowed, raise error
            raise SchemaStructureError(
                u'Node type "{}" not allowed'.format(node_type)
            )
        else:
            # All Node types should've been taken care of, this line should never be reached
            raise AssertionError(u'Missed type: "{}"'.format(node_type))


class RenameRootFieldsVisitor(Visitor):
    def __init__(self, rename_dict, query_type):
        self.in_query_type = False
        self.rename_dict = rename_dict
        # Dict[str, str], from original field name to renamed field name; any name not in the dict
        # will be unchanged
        self.reverse_field_map = {}  # Dict[str, str], renamed field name to original field name
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

            new_field_name = self.rename_dict.get(field_name, field_name)  # Default use original

            if (
                new_field_name in self.reverse_field_map and
                self.reverse_field_map[new_field_name] != field_name
            ):
                raise SchemaRenameConflictError(
                    u'"{}" and "{}" are both renamed to "{}"'.format(
                        field_name, self.reverse_field_map[new_field_name], new_field_name
                    )
                )

            node.name.value = new_field_name
            self.reverse_field_map[new_field_name] = field_name
