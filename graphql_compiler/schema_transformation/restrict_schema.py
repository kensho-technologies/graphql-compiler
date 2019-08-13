from copy import copy

from graphql import build_ast_schema
from graphql.language.visitor import REMOVE, Visitor, visit

from ..ast_manipulation import get_ast_with_non_null_and_list_stripped
from .utils import SchemaStructureError, get_query_type_name, get_scalar_names


def restrict_schema(schema_ast, types_to_keep):
    """Return new AST containing only a subset of types.

    In addition to all types named in types_to_keep, the query type will also be kept. All user
    defined scalars and enums will be kept.
    All property fields will be kept, and only vertex fields that go to kept types will be
    kept.

    Args:
        schema_ast: Document, representing the schema we're using to create a new schema with
                    fewer types. It is not modified by this function
        types_to_keep: Set[str], the set of names of types that we want to keep in the output
                       schema

    Returns:
        Document, representing the schema that is derived from the input schema AST, but only
        keeping a subset of types and a subset of vertex fields. The query type is additionally
        also always kept

    Raises:
        SchemaStructureError if types_to_keep is inconsistent, in that some union type is included
        but not all of its subtypes are included, or if some type has no remaining fields, or if
        for some other reason the resulting schema AST cannot be made into a valid schema
    """
    schema = build_ast_schema(schema_ast)
    query_type_name = get_query_type_name(schema)
    scalar_names = get_scalar_names(schema)
    visitor = RestrictSchemaVisitor(
        types_to_keep, query_type_name, scalar_names
    )
    restricted_schema = visit(schema_ast, visitor)
    # The restricted schema may contain types with no fields left
    try:
        build_ast_schema(schema_ast)
    except Exception as e:  # Can't be more specific, build_ast_schema throws Exceptions
        raise SchemaStructureError(u'The resulting schema is invalid. Message: {}'.format(e))

    # Note that it is possible for some types in the restricted schema to be unreachable
    return restricted_schema


class RestrictSchemaVisitor(Visitor):
    """Remove types that are not explicitly kept, and fields go these types."""
    def __init__(self, types_to_keep, query_type, scalars):
        """Create a visitor for removing types and fields.

        Args:
            types_to_keep: Set[str], the set of names of types that we want to keep in the schema
            query_type: str, name of the query type in the schema. The query type is always kept
            scalars: str, names of scalar types, both builtin and user defined. Used to identify
                     property fields, as such fields are kept
        """
        self.types_to_keep = types_to_keep
        self.query_type = query_type
        self.scalars = scalars

    def enter_ObjectTypeDefinition(self, node, *args):
        """Remove definition if needed, remove any interfaces it implements that are not kept."""
        node_name = node.name.value
        if node_name == self.query_type or node_name in self.types_to_keep:
            # Node is kept, now remove any interface necessary
            kept_interfaces = []
            made_changes = False
            if node.interfaces is not None:
                for interface in node.interfaces:
                    interface_name = interface.name.value
                    if interface_name in self.types_to_keep:
                        kept_interfaces.append(interface)
                    else:
                        made_changes = True
            if made_changes:
                node_with_new_interfaces = copy(node)
                node_with_new_interfaces.interfaces = kept_interfaces
                return node_with_new_interfaces
            else:
                return None
        else:
            return REMOVE

    def enter_InterfaceTypeDefinition(self, node, *args):
        """Remove definition if needed."""
        node_name = node.name.value
        if node_name in self.types_to_keep:
            return None
        else:
            return REMOVE

    def enter_UnionTypeDefinition(self, node, *args):
        """Remove definition if needed, check all subtypes also kept if definition kept."""
        node_name = node.name.value
        if node_name in self.types_to_keep:
            # Check that all subtypes of the union are also kept
            union_sub_types = [sub_type.name.value for sub_type in node.types]
            if any(
                union_sub_type not in self.types_to_keep
                for union_sub_type in union_sub_types
            ):
                raise SchemaStructureError(
                    u'Not all of the subtypes, {}, of the union type "{}" are in the set of '
                    u'types to keep, {}.'.format(union_sub_types, node_name, self.types_to_keep)
                )
            return None
        else:
            return REMOVE

    def enter_FieldDefinition(self, node, *args):
        """Remove definition if field goes to type that is removed."""
        field_type = get_ast_with_non_null_and_list_stripped(node.type)
        field_type_name = field_type.name.value
        if field_type_name in self.types_to_keep or field_type_name in self.scalars:
            return None
        else:  # Field is a vertex field going to a removed type
            return REMOVE

    def leave_ObjectTypeDefinition(self, node, *args):
        """Check not all fields were removed."""
        if len(node.fields) == 0:  # All fields removed
            raise SchemaStructureError(
                u'Type "{}" is kept, but all of its fields have been removed due to being '
                u'vertex fields to types that were removed.'.format(node.name.value)
            )

    def leave_InterfaceTypeDefinition(self, node, *args):
        """Check not all fields were removed."""
        if len(node.fields) == 0:  # All fields removed
            raise SchemaStructureError(
                u'Interface "{}" is kept, but all of its fields have been removed due to being '
                u'vertex fields to types that were removed.'.format(node.name.value)
            )
