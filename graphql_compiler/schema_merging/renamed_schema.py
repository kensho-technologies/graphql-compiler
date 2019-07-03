from graphql import build_ast_schema, parse
from graphql.language.printer import print_ast
from graphql.language.visitor import Visitor, visit

from .utils import SchemaError, get_schema_data


class RenamedSchema(object):
    def __init__(self, schema_string, rename_func=lambda name: name):
        """Create a RenamedSchema, where types and root fields are renamed using rename_func.

        Args:
            schema_string: string describing a valid schema that does not contain extensions
            rename_func: callable that takes string to string, used to transform the names of
                         types, interfaces, enums, and root fields. Defaults to identity

        Raises:
            SchemaError if input schema_string does not represent a valid schema without extensions
        """
        self.schema_ast = None  # type: Document
        self.reverse_name_map = {}  # maps new names to original names
        self.reverse_root_field_map = {}  # maps new field names to original field names

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

        self._rename_schema(ast, rename_func, schema_data)

    @property
    def schema_string(self):
        return print_ast(self.schema_ast)

    def _rename_schema(self, ast, rename_func, schema_data):
        """Rename types/interfaces/enums and root fields

        Name and field maps will also be modified.

        Args:
            schema_string: string, in GraphQL schema language
            rename_func: callable that converts type names to renamed type names. Takes a string
                         as input and returns a string. Defaults to identity function
            schema_data: SchemaData, information about current schema

        Raises:
            SchemaError if the input schema contains extensions, as the renamer doesn't currently
                support extensions (build_ast_schema eats extensions), or if a renamed type in the
                schemas string causes a type name conflict, between types/interfaces/enums/scalars

        Return:
            string, the new renamed schema
        """
        # Rename types, interfaces, enums
        self._rename_types(ast, rename_func, schema_data.query_type, schema_data.scalars)

        # Rename root fields
        self._rename_root_fields(ast, rename_func, schema_data.query_type)

        self.schema_ast = ast

    def _rename_types(self, ast, rename_func, query_type_name, scalars):
        """Rename types, enums, interfaces, and more using rename_func.

        Types, interfaces, enum definitions will be renamed. The query type will not be renamed.
        Scalar types, field names, enum values will not be renamed.
        ast will be modified as a result.

        Args:
            ast: Document, the schema ast that we modify
            rename_func: callable, used to rename types, interfaces, enums, etc
            query_type_name: string, name of the query type, e.g. 'RootSchemaQuery'
            scalars: set of strings, the set of user defined scalars

        Raises:
            SchemaError if the rename causes name conflicts
        """
        visitor = RenameSchemaTypesVisitor(rename_func, query_type_name, scalars)
        visit(ast, visitor)

        self.reverse_name_map = visitor.reverse_name_map  # no aliasing, visitor goes oos

    def _rename_root_fields(self, ast, rename_func, query_type_name):
        """Rename root fieldd -- fields of the query type.

        ast will be modified as a result.

        Args:
            ast: Document, the schema ast that we modify
            rename_func: callable, used to rename fields of the query type
            query_type_name: string, name of the query type, e.g. 'RootSchemaQuery'

        Raises:
            SchemaError if rename causes root field names to clash
        """
        visitor = RenameRootFieldsVisitor(rename_func, query_type_name)
        visit(ast, visitor)

        self.reverse_root_field_map = visitor.reverse_field_map  # no aliasing, visitor goes oos


class RenameSchemaTypesVisitor(Visitor):
    """Traverse a Document AST, editing the names of nodes."""
    def __init__(self, rename_func, query_type, scalar_types):
        self.rename_func = rename_func  # callable that takes string to string
        self.reverse_name_map = {}  # Dict[str, str], from new name to original name
        self.query_type = query_type
        self.scalar_types = scalar_types
        self.builtin_types = {'String', 'Int', 'Float', 'Boolean', 'ID'}

    def _rename_name_add_to_record(self, node):
        """Rename the value of the node, and add the name mapping to reverse_name_map.

        Don't rename if the type is the query type, a scalar type, or a built in type.

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

    # In order of QUERY_DOCUMENT_KEYS

    def enter_Name(self, node, *args):
        pass

    def enter_Document(self, node, *args):
        pass

    def enter_OperationDefinition(self, node, *args):
        raise SchemaError('Node type "{}" unexpected in schema AST.'.format('OperationDefinition'))

    def enter_VariableDefinition(self, node, *args):
        raise AssertionError('Unimplemented')

    def enter_Variable(self, node, *args):
        raise AssertionError('Unimplemented')

    def enter_SelectionSet(self, node, *args):
        raise SchemaError('Node type "{}" unexpected in schema AST.'.format('SelectionSet'))

    def enter_Field(self, node, *args):
        raise SchemaError('Node type "{}" unexpected in schema AST.'.format('Field'))

    def enter_Argument(self, node, *args):
        # argument of directive
        pass

    def enter_FragmentSpread(self, node, *args):
        raise SchemaError('Node type "{}" unexpected in schema AST.'.format('FragmentSpread'))

    def enter_InlineFragment(self, node, *args):
        raise SchemaError('Node type "{}" unexpected in schema AST.'.format('InlineFragment'))

    def enter_FragmentDefinition(self, node, *args):
        raise SchemaError('Node type "{}" unexpected in schema AST.'.format('FragmentDefinition'))

    def enter_IntValue(self, node, *args):
        pass

    def enter_FloatValue(self, node, *args):
        pass

    def enter_StringValue(self, node, *args):
        pass

    def enter_BooleanValue(self, node, *args):
        pass

    def enter_EnumValue(self, node, *args):
        pass

    def enter_ListValue(self, node, *args):
        pass

    def enter_ObjectValue(self, node, *args):
        raise AssertionError('Unimplemented')

    def enter_ObjectField(self, node, *args):
        raise AssertionError('Unimplemented')

    def enter_Directive(self, node, *args):
        # TODO: behavior is not clear
        pass

    def enter_NamedType(self, node, *args):
        """Rename all named types that are not the query type, scalars, or builtins."""
        self._rename_name_add_to_record(node.name)

    def enter_ListType(self, node, *args):
        pass

    def enter_NonNullType(self, node, *args):
        pass

    def enter_SchemaDefinition(self, node, *args):
        pass

    def enter_OperationTypeDefinition(self, node, *args):
        pass

    def enter_ScalarTypeDefinition(self, node, *args):
        pass

    def enter_ObjectTypeDefinition(self, node, *args):
        # NamedType takes care of interfaces, FieldDefinition takes care of fields, Directive
        # takes care of directives
        self._rename_name_add_to_record(node.name)

    def enter_FieldDefinition(self, node, *args):
        # No rename name, InputValueDefinition takes care of arguments, NamedType cares care of
        # type, Directive takes care of directives
        # NOTE: the directives are interestingly not printed if you print node, but they do exist
        pass

    def enter_InputValueDefinition(self, node, *args):
        # No rename name, NamedType takes care of type, no rename default_value, Directive takes
        # care of directives
        pass

    def enter_InterfaceTypeDefinition(self, node, *args):
        # FieldDefinition takes care of fields, Directive takes care of directives
        self._rename_name_add_to_record(node.name)

    def enter_UnionTypeDefinition(self, node, *args):
        # NamedType takes care of types, Directive takes care of directives
        self._rename_name_add_to_record(node.name)

    def enter_EnumTypeDefinition(self, node, *args):
        # EnumValueDefinition takes care of values, Directive takes care of directives
        self._rename_name_add_to_record(node.name)

    def enter_EnumValueDefinition(self, node, *args):
        pass

    def enter_InputObjectTypeDefinition(self, node, *args):
        raise AssertionError('Unimplemented')

    def enter_TypeExtensionDefinition(self, node, *args):
        raise SchemaError('Extension definition not allowed')

    def enter_DirectiveDefinition(self, node, *args):
        pass


class RenameRootFieldsVisitor(Visitor):
    def __init__(self, rename_func, query_type_name):
        self.in_query_type = False
        self.reverse_field_map = {}
        self.rename_func = rename_func
        self.query_type_name = query_type_name

    def enter_ObjectTypeDefinition(self, node, *args):
        """If entering query type, set flag to True."""
        if node.name.value == self.query_type_name:
            self.in_query_type = True

    def leave_ObjectTypeDefinition(self, node, key, parent, path, ancestors):
        """If leaving query type, set flag to False."""
        if node.name.value == self.query_type_name:
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
