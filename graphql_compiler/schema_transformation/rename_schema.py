# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import deepcopy

from graphql import build_ast_schema
from graphql.language.visitor import Visitor, visit
import six

from .utils import (
    SchemaNameConflictError, check_ast_schema_is_valid, check_type_name_is_valid,
    get_query_type_name, get_scalar_names
)


RenamedSchemaDescriptor = namedtuple(
    'RenamedSchemaDescriptor', (
        'schema_ast',  # Document, AST representing the renamed schema
        'reverse_name_map',  # Dict[str, str], renamed type/query type field name to original name
        # reverse_name_map only contains names that were changed
    )
)


def rename_schema(ast, renamings):
    """Create a RenamedSchemaDescriptor; types and query type fields are renamed using renamings.

    Any type, interface, enum, or fields of the root type/query type whose name
    appears in renamings will be renamed to the corresponding value. Any such names that do not
    appear in renamings will be unchanged. Scalars, directives, enum values, and fields not
    belonging to the root/query type will never be renamed.

    Args:
        ast: Document, representing a valid schema that does not contain extensions, input
             object definitions, mutations, or subscriptions, whose fields of the query type share
             the same name as the types they query. Not modified by this function
        renamings: Dict[str, str], mapping original type/field names to renamed type/field names.
                   Type or query type field names that do not appear in the dict will be unchanged.
                   Any dict-like object that implements get(key, [default]) may also be used

    Returns:
        RenamedSchemaDescriptor, a namedtuple that contains the AST of the renamed schema, and the
        map of renamed type/field names to original names. Only renamed names will be included
        in the map.

    Raises:
        - InvalidTypeNameError if the schema contains an invalid type name, or if the user attempts
          to rename a type to an invalid name. A name is considered invalid if it does not consist
          of alphanumeric characters and underscores, if it starts with a numeric character, or
          if it starts with double underscores
        - SchemaStructureError if the schema does not have the expected form; in particular, if
          the AST does not represent a valid schema, if any query type field does not have the
          same name as the type that it queries, if the schema contains type extensions or
          input object definitions, or if the schema contains mutations or subscriptions
        - SchemaNameConflictError if there are conflicts between the renamed types or fields
    """
    # Prevent modifying input
    ast = deepcopy(ast)

    # Check input schema satisfies various structural requirements
    check_ast_schema_is_valid(ast)

    schema = build_ast_schema(ast)
    query_type = get_query_type_name(schema)
    scalars = get_scalar_names(schema)

    # Rename types, interfaces, enums
    reverse_name_map = _rename_types(ast, renamings, query_type, scalars)
    reverse_name_map_changed_names_only = {
        renamed_name: original_name
        for renamed_name, original_name in six.iteritems(reverse_name_map)
        if renamed_name != original_name
    }

    # Rename query type fields
    _rename_query_type_fields(ast, renamings, query_type)

    return RenamedSchemaDescriptor(
        schema_ast=ast, reverse_name_map=reverse_name_map_changed_names_only
    )


def _rename_types(ast, renamings, query_type, scalars):
    """Rename types, enums, interfaces using renamings.

    The query type will not be renamed. Scalar types, field names, enum values will not be renamed.

    ast will be modified as a result.

    Args:
        ast: Document, the schema AST that we modify
        renamings: Dict[str, str], mapping original type/interface/enum name to renamed name. If
                   a name does not appear in the dict, it will be unchanged
        query_type: str, name of the query type, e.g. 'RootSchemaQuery'
        scalars: Set[str], the set of all scalars used in the schema, including user defined
                 scalars and and used builtin scalars, excluding unused builtins

    Returns:
        Dict[str, str], the renamed type name to original type name map. Map contains all types,
        including those that were not renamed.

    Raises:
        - InvalidTypeNameError if the schema contains an invalid type name, or if the user attempts
          to rename a type to an invalid name
        - SchemaNameConflictError if the rename causes name conflicts
    """
    visitor = RenameSchemaTypesVisitor(renamings, query_type, scalars)
    visit(ast, visitor)

    return visitor.reverse_name_map


def _rename_query_type_fields(ast, renamings, query_type):
    """Rename all fields of the query type.

    ast will be modified as a result.

    Args:
        ast: Document, the schema AST that we modify
        renamings: Dict[str, str], mapping original field name to renamed name. If a name
                   does not appear in the dict, it will be unchanged
        query_type: string, name of the query type, e.g. 'RootSchemaQuery'
    """
    visitor = RenameQueryTypeFieldsVisitor(renamings, query_type)
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
        'Field',
        'FieldDefinition',
        'FloatValue',
        'FragmentDefinition',
        'FragmentSpread',
        'InlineFragment',
        'InputObjectTypeDefinition',
        'InputValueDefinition',
        'IntValue',
        'ListType',
        'ListValue',
        'Name',
        'NonNullType',
        'ObjectField',
        'ObjectValue',
        'OperationDefinition',
        'OperationTypeDefinition',
        'ScalarTypeDefinition',
        'SchemaDefinition',
        'SelectionSet',
        'StringValue',
        'TypeExtensionDefinition',
        'Variable',
        'VariableDefinition',
    })
    rename_types = frozenset({
        'EnumTypeDefinition',
        'InterfaceTypeDefinition',
        'NamedType',
        'ObjectTypeDefinition',
        'UnionTypeDefinition',
    })

    def __init__(self, renamings, query_type, scalar_types):
        """Create a visitor for renaming types in a schema AST.

        Args:
            renamings: Dict[str, str], mapping from original type name to renamed type name.
                       Any name not in the dict will be unchanged
            query_type: str, name of the query type (e.g. RootSchemaQuery), which will not
                        be renamed
            scalar_types: Set[str], set of names of all scalars used in the schema, including
                          all user defined scalars and any builtin scalars that were used
        """
        self.renamings = renamings
        self.reverse_name_map = {}  # Dict[str, str], from renamed type name to original type name
        # reverse_name_map contains all types, including those that were unchanged
        self.query_type = query_type
        self.scalar_types = frozenset(scalar_types)
        self.builtin_types = frozenset({'String', 'Int', 'Float', 'Boolean', 'ID'})

    def _rename_name_and_add_to_record(self, node):
        """Rename the value of the node, and add the name pair to reverse_name_map.

        Don't rename if the type is the query type, a scalar type, or a builtin type.

        Modifies node and potentially modifies reverse_name_map.

        Args:
            node: type Name (see graphql/language/ast), an object describing the name of an AST
                  element such as type, interface, or scalar (user defined or builtin)

        Raises:
            - InvalidTypeNameError if either the node's current name or renamed name is invalid
            - SchemaNameConflictError if the newly renamed node causes name conflicts with
              existing types, scalars, or builtin types
        """
        name_string = node.value

        if name_string == self.query_type or name_string in self.scalar_types:
            return

        new_name_string = self.renamings.get(name_string, name_string)  # Default use original
        check_type_name_is_valid(new_name_string)

        if (
            new_name_string in self.reverse_name_map and
            self.reverse_name_map[new_name_string] != name_string
        ):
            raise SchemaNameConflictError(
                u'"{}" and "{}" are both renamed to "{}"'.format(
                    name_string, self.reverse_name_map[new_name_string], new_name_string
                )
            )
        if new_name_string in self.scalar_types or new_name_string in self.builtin_types:
            raise SchemaNameConflictError(
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
            self._rename_name_and_add_to_record(node.name)
        else:
            # All Node types should've been taken care of, this line should never be reached
            raise AssertionError(u'Missed type: "{}"'.format(node_type))


class RenameQueryTypeFieldsVisitor(Visitor):
    def __init__(self, renamings, query_type):
        """Create a visitor for renaming fields of the query type in a schema AST.

        Args:
            renamings: Dict[str, str], from original field name to renamed field name. Any
                       name not in the dict will be unchanged
            query_type: str, name of the query type (e.g. RootSchemaQuery)
        """
        # Note that as field names and type names have been confirmed to match up, any renamed
        # field already has a corresponding renamed type. If no errors, due to either invalid
        # names or name conflicts, were raised when renaming type, no errors will occur when
        # renaming query type fields.
        self.in_query_type = False
        self.renamings = renamings
        self.query_type = query_type

    def enter_ObjectTypeDefinition(self, node, *args):
        """If the node's name matches the query type, record that we entered the query type."""
        if node.name.value == self.query_type:
            self.in_query_type = True

    def leave_ObjectTypeDefinition(self, node, key, parent, path, ancestors):
        """If the node's name matches the query type, record that we left the query type."""
        if node.name.value == self.query_type:
            self.in_query_type = False

    def enter_FieldDefinition(self, node, *args):
        """If inside the query type, rename field and add the name pair to reverse_field_map."""
        if self.in_query_type:
            field_name = node.name.value
            new_field_name = self.renamings.get(field_name, field_name)  # Default use original
            node.name.value = new_field_name
