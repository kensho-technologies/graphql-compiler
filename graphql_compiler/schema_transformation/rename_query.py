# Copyright 2019-present Kensho Technologies, LLC.
from copy import deepcopy

from graphql.language import ast as ast_types
from graphql.language.visitor import Visitor, visit

from .utils import QueryStructureError


def rename_query(ast, renamings):
    """Translate names of types and root vertex fields using renamings.

    Root vertex fields are fields of the query type. Other fields will not be renamed.

    This function is intended to be used in conjunction with rename_schema.

    Args:
        ast: Document, representing a valid query. It is assumed to have passed GraphQL's
             builtin validation -- validate(schema, ast), in that it has the structure of a
             valid query, does not reference non-existent types or fields, and passes type
             checks. The ast is not modified by this function
        renamings: Dict[str, str], mapping original type/root vertex field names to renamed
                   names. Names not appearing in the dict will be unchanged

    Returns:
        Document, a new AST representing the renamed query

    Raises:
        - QueryStrutureError if the ast does not have the expected form; in particular, if the
          AST contains Fragments, or if it contains an InlineFragment at the root level
    """
    # NOTE: There is a validation section in graphql-core that takes in a schema and a
    # query ast, and checks whether the query is valid -- for example, type names are known in
    # the schema, all leaf nodes are scalars, arguments are of the correct type, etc.
    # We assume this validation step has been done.
    if len(ast.definitions) > 1:  # includes either multiple queries, or fragment definitions
        raise QueryStructureError(
            u'Only one query may be included, and fragments are not allowed.'
        )

    query_definition = ast.definitions[0]

    for selection in query_definition.selection_set.selections:
        if not isinstance(selection, ast_types.Field):  # possibly an InlineFragment
            raise QueryStructureError(
                u'Each root selections must be of type "Field", not "{}" as in '
                u'selection "{}"'.format(type(selection).__name__, selection)
            )

    ast = deepcopy(ast)

    visitor = RenameQueryVisitor(renamings)
    visit(ast, visitor)

    return ast


class RenameQueryVisitor(Visitor):
    def __init__(self, renamings):
        """Create a visitor for renaming types and root vertex fields in a query AST.

        Args:
            renamings: Dict[str, str], mapping from original type name to renamed type name.
                       Any name not in the dict will be unchanged
        """
        self.renamings = renamings
        self.selection_set_level = 0

    def _rename_name(self, node):
        """Modify node as according to renamings.

        Args:
            node: type Name, an AST Node object that describes the name of its parent node in
                  the AST
        """
        name_string = node.value
        new_name_string = self.renamings.get(name_string, name_string)  # Default use original
        node.value = new_name_string

    def enter_NamedType(self, node, *args):
        """Rename name of node."""
        # NamedType nodes describe types in the schema, appearing in InlineFragments
        self._rename_name(node.name)

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
            self._rename_name(node.name)
