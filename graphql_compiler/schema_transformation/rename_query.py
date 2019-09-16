# Copyright 2019-present Kensho Technologies, LLC.
from graphql.language.ast import Field
from graphql.language.visitor import Visitor, visit
from graphql.validation import validate

from ..exceptions import GraphQLValidationError
from .utils import get_copy_of_node_with_new_name


def rename_query(ast, renamed_schema_descriptor):
    """Translate names of types using reverse_name_map of the input RenamedSchemaDescriptor.

    The direction in which types and fields are renamed is opposite of the process that
    produced the renamed schema descriptor. If a type X was renamed to Y in the schema, then
    any occurrences of type Y in the input query ast will be renamed to X.

    All type names (including ones in type coercions), as well as root vertex fields (fields
    of the query type) will be renamed. No other field names will be renamed.

    Args:
        ast: Document, representing a query
        renamed_schema_descriptor: RenamedSchemaDescriptor, a namedtuple including the
                                   attribute reverse_name_map, which maps the new, renamed
                                   names of types to their original names. This function will
                                   revert these renamed types in the query ast back to their
                                   original names

    Returns:
        Document, a new AST representing the renamed query

    Raises:
        - GraphQLValidationError if the AST does not have the expected form; in particular,
          if the AST fails GraphQL's builtin validation against the provided schema, if it
          contains Fragments, or if it contains an InlineFragment at the root level
    """
    built_in_validation_errors = validate(renamed_schema_descriptor.schema, ast)
    if len(built_in_validation_errors) > 0:
        raise GraphQLValidationError(
            u'AST does not validate: {}'.format(built_in_validation_errors)
        )

    if len(ast.definitions) > 1:  # includes either multiple queries, or fragment definitions
        raise GraphQLValidationError(
            u'Only one query may be included, and fragments are not allowed.'
        )

    query_definition = ast.definitions[0]

    for selection in query_definition.selection_set.selections:
        if not isinstance(selection, Field):  # possibly an InlineFragment
            raise GraphQLValidationError(
                u'Each root selection must be of type "Field", not "{}" as in '
                u'selection "{}"'.format(type(selection).__name__, selection)
            )

    visitor = RenameQueryVisitor(renamed_schema_descriptor.reverse_name_map)
    renamed_ast = visit(ast, visitor)

    return renamed_ast


class RenameQueryVisitor(Visitor):
    def __init__(self, renamings):
        """Create a visitor for renaming types and root vertex fields in a query AST.

        Args:
            renamings: Dict[str, str]. Any type or root field of the AST whose name appears as
                       a key in the dict will be renamed to the corresponding value in the dict.
                       Any name not in the dict will be unchanged
        """
        self.renamings = renamings
        self.selection_set_level = 0

    def _rename_name(self, node):
        """Change the name of the input node if necessary, according to renamings.

        Args:
            node: Field, an object representing a field in an AST, containing a .name attribute
                  corresponding to an AST node of type Name. It is not modified

        Returns:
            Field, possibly with a new name. If the name was not changed, the returned object
            is the exact same object as the input
        """
        name_string = node.name.value
        new_name_string = self.renamings.get(name_string, name_string)  # Default use original
        if new_name_string == name_string:
            return node
        else:
            node_with_new_name = get_copy_of_node_with_new_name(node, new_name_string)
            return node_with_new_name

    def enter_NamedType(self, node, *args):
        """Rename name of node."""
        # NamedType nodes describe types in the schema, appearing in InlineFragments
        renamed_node = self._rename_name(node)
        if renamed_node is node:  # Name unchanged, continue traversal
            return None
        else:  # Name changed, return new node, `visit` will make shallow copies along path
            return renamed_node

    def enter_SelectionSet(self, node, *args):
        """Record that we entered another nested level of selections."""
        self.selection_set_level += 1

    def leave_SelectionSet(self, node, *args):
        """Record that we left a level of selections."""
        self.selection_set_level -= 1

    def enter_Field(self, node, *args):
        """Rename root vertex fields."""
        # For a Field to be a root vertex field, it needs to be the first level of
        # selections (fields in more nested selections are normal fields that should not be
        # modified)
        # As FragmentDefinition is not allowed, the parent of the selection must be a query
        # As a query may not start with an inline fragment, all first level selections are
        # fields
        if self.selection_set_level == 1:
            renamed_node = self._rename_name(node)
            if renamed_node is node:  # Name unchanged, continue traversal
                return None
            else:  # Name changed, return new node, `visit` will make shallow copies along path
                return renamed_node
