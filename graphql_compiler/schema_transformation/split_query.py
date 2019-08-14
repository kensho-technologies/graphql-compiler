# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import copy

from graphql.language.ast import (
    Argument, Directive, Document, Field, InlineFragment, InterfaceTypeDefinition, Name,
    ObjectTypeDefinition, OperationDefinition, SelectionSet, StringValue
)
from graphql.language.visitor import TypeInfoVisitor, Visitor, visit
from graphql.utils.type_info import TypeInfo

from ..ast_manipulation import get_only_query_definition
from ..compiler.helpers import strip_non_null_and_list_from_type
from ..exceptions import GraphQLValidationError
from ..schema import FilterDirective, OptionalDirective, OutputDirective
from .utils import (
    SchemaStructureError, check_query_is_valid_to_split, is_property_field_ast,
    try_get_ast_by_name_and_type
)


QueryConnection = namedtuple(
    'QueryConnection', (
        'sink_query_node',  # SubQueryNode
        'source_field_out_name',
        # str, the unique out name on the @output of the the source property field in the stitch
        'sink_field_out_name',
        # str, the unique out name on the @output of the the sink property field in the stitch
    )
)


class SubQueryNode(object):
    def __init__(self, query_ast):
        """Represents one piece of a larger query, targeting one schema.

        Args:
            query_ast: Document, representing one piece of a query
        """
        self.query_ast = query_ast
        self.schema_id = None  # str, identifying the schema that this query targets
        self.parent_query_connection = None
        # SubQueryNode or None, the query that the current query depends on
        self.child_query_connections = []
        # List[SubQueryNode], the queries that depend on the current query


def _split_query_ast_one_level_recursive(
    query_node, ast, parent_selections, type_info, edge_to_stitch_fields,
    intermediate_out_name_assigner
):
    """Return a Node to replace the input AST by in the selections one level above.

    - If the input AST starts with a cross schema vertex field, the output will be a Field object
      representing the property field used in the stitch
      - If a property field of the expected name already exists in the selections one level
        above (in parent_selections), the new Field will contain any existing directives of
        this field
    - Otherwise, the process will be repeated on child selections (if any) of the input AST
      - If no child selection is modified, the exact same object as the input AST will be returned
      - If some child selection is modified, a copy of the AST with the new selections will be
        returned
        - If a modified child selection is a property field
          - If a property field of the same name already exists, the new field will replace the
            existing field
          - Otherwise, the property field will be inserted into selections after the last existing
            property field
        - Otherwise, the modified selection will be appended to selections

    Args:
        query_node: SubQueryNode, whose list of child query connections may be modified to include
                    children
        ast: type Node, the AST that we are trying to split into child components. It is not
             modified by this function
        parent_selections: List[Node], containing all property fields (and possibly some vertex
                           fields) in the level of selections that contains the input ast. It
                           is not modified by this function
        type_info: TypeInfo, used to get information about the types of fields while traversing
                   the query ast
        edge_to_stitch_fields: Dict[Tuple(str, str), Tuple(str, str)], mapping
                               (type name, vertex field name) to
                               (source field name, sink field name) used in the @stitch directive
                               for each cross schema edge
        intermediate_out_name_assigner: IntermediateOutNameAssigner, object used to generate
                                        and keep track of names of newly created @output
                                        directives

    Returns:
        Node object to replace the input AST in the selections one level above. If the output
        is unchanged from the input AST, the exact same object will be returned
    """
    # Check if there is a split here. If so, split AST, make child query node, return property
    # field. If not, recurse on all child selections (if any)
    if isinstance(ast, Field):
        parent_type_name = type_info.get_parent_type().name
        edge_field_name = ast.name.value
        if (parent_type_name, edge_field_name) in edge_to_stitch_fields:
            # parent_field_name and child_field_name are names of property fields in the stitch
            parent_field_name, child_field_name = \
                edge_to_stitch_fields[(parent_type_name, edge_field_name)]
            # Get parent field with existing directives
            parent_property_field = _get_property_field(
                parent_selections, parent_field_name, ast.directives
            )
            # Add @output if needed, record out_name
            parent_output_name = _get_out_name_optionally_add_output(
                parent_property_field, intermediate_out_name_assigner
            )
            # Create child query node around ast
            child_query_node, child_output_name = _get_child_query_node_and_out_name(
                ast, type_info, child_field_name, intermediate_out_name_assigner
            )
            # Create and add QueryConnections
            _add_query_connections(
                query_node, child_query_node, parent_output_name, child_output_name
            )
            # Return parent property field used in the stitch, to be added in selections above
            return parent_property_field

    # No split here
    if ast.selection_set is None:  # Property field, nothing to recurse on
        return ast
    selections = ast.selection_set.selections

    new_selections = []
    made_changes = False

    type_info.enter(ast.selection_set)
    for selection in selections:  # Recurse on children
        type_info.enter(selection)
        # By the time we reach any cross schema vertex fields, new_selections contains all
        # property fields, including any new property fields created by previous cross schema
        # vertex fields, and therefore will not create duplicate new fields
        new_selection = _split_query_ast_one_level_recursive(
            query_node, selection, new_selections, type_info, edge_to_stitch_fields,
            intermediate_out_name_assigner
        )

        if new_selection is not selection:
            made_changes = True
            if is_property_field_ast(new_selection):
                # If a property field is returned and is different from the input, then this is
                # a property field used in stitching. If no existing field has this name, insert
                # the new property field to end of property fields. If some existing field has
                # this name, replace the existing field with the returned field
                new_selections = _replace_or_insert_property_field(new_selections, new_selection)
                # The current actual selection is ignored, since it leads to a cut-off branch
            else:
                # Changes were made somewhere down the line, append changed version to end
                new_selections.append(new_selection)
        else:
            new_selections.append(new_selection)
        type_info.leave(selection)
    type_info.leave(ast.selection_set)

    if made_changes:
        ast_copy = copy(ast)
        ast_copy.selection_set = SelectionSet(selections=new_selections)
        return ast_copy
    else:
        return ast


def _get_child_query_node_and_out_name(ast, type_info, child_field_name,
                                       intermediate_out_name_assigner):
    """Create a query node out of ast, return node and unique out_name on field with input name.

    Create a new document out of the input AST, that has the same structure as the input. For
    instance, if the input AST can be represented by
        out_Human {
          name
        }
    where out_Human is a vertex field going to type Human, the resulting document will be
        {
          Human {
            name
          }
        }
    If the input AST starts with a type coercion, the resulting document will start with the
    coerced type, rather than the original union or interface type.

    The output child_node will be wrapped around this new Document. In addition, if no field
    of child_field_name currently exists, such a field will be added. If there is no @output
    directive on this field, a new @output directive will be added.

    Args:
        ast: type Node, representing the AST that we're using to build a child node. It is not
             modified by this function
        type_info: TypeInfo, at the location of the ast
        child_field_name: str. If no field of this name currently exists as a part of the root
                          selections of the input AST, a new field will be created in the AST
                          contained in the output child query node
        intermediate_out_name_assigner: IntermediateOutNameAssigner, which will be used to
                                        generate an out_name, if it's necessary to create a
                                        new @output directive

    Returns:
        Tuple[SubQueryNode, str], the child sub query node wrapping around the input ast, and
        the out_name of the @output directive uniquely identifying the field used or stitching
        in this sub query node
    """
    child_type_name, child_selections = _get_child_type_and_selections(ast, type_info)
    # Get existing field with name in child
    child_property_field = _get_property_field(child_selections, child_field_name, [])
    # Add @output if needed, record out_name
    child_output_name = _get_out_name_optionally_add_output(
        child_property_field, intermediate_out_name_assigner
    )
    # Get new child_selections
    child_selections = _replace_or_insert_property_field(child_selections, child_property_field)
    # Wrap around
    # NOTE: if child_type_name does not actually exist as a root field (not all types are
    # required to have a corresponding root vertex field), then this query will be invalid
    child_query_ast = _get_query_document(child_type_name, child_selections)
    child_query_node = SubQueryNode(child_query_ast)

    return child_query_node, child_output_name


def _get_property_field(selections, field_name, directives_from_edge):
    """Return a Field object with field_name, sharing directives with any such existing field.

    Any valid directives in directives_on_edge will be transferred over to the new field.
    If there is an existing Field in selection with field_name, the returned new Field
    will also contain all directives of the existing field with that name.

    Args:
        selections: List[Union[Field, InlineFragment]]. If there is a field with field_name,
                    the directives of this field will carry over to the output field. It is
                    not modified by this function
        field_name: str, the name of the output field
        directives_from_edge: List[Directive], the directives of a vertex field. The output
                              field will contain all @filter and any @optional directives
                              from this list

    Returns:
        Field object, with field_name as its name, containing directives from any field in the
        input selections with the same name and directives from the input list of directives
    """
    new_field = Field(
        name=Name(value=field_name),
        directives=[],
    )

    # Check parent_selection for existing field of given name
    parent_field = try_get_ast_by_name_and_type(selections, field_name, Field)
    if parent_field is not None:
        # Existing field, add all its directives
        directives_from_existing_field = parent_field.directives
        if directives_from_existing_field is not None:
            new_field.directives.extend(directives_from_existing_field)

    # Transfer directives from edge
    if directives_from_edge is not None:
        for directive in directives_from_edge:
            if directive.name.value == OutputDirective.name:  # output illegal on vertex field
                raise GraphQLValidationError(
                    u'Directive "{}" is not allowed on a vertex field, as @output directives '
                    u'can only exist on property fields.'.format(directive)
                )
            elif directive.name.value == OptionalDirective.name:
                if try_get_ast_by_name_and_type(
                    new_field.directives, OptionalDirective.name, Directive
                ) is None:
                    # New optional directive
                    new_field.directives.append(directive)
            elif directive.name.value == FilterDirective.name:
                new_field.directives.append(directive)
            else:
                raise AssertionError(
                    u'Unreachable code reached. Directive "{}" is of an unsupported type, and '
                    u'was not caught in a prior validation step.'.format(directive)
                )

    return new_field


def _get_child_type_and_selections(ast, type_info):
    """Get the type (root field) and selection set of the input AST.

    For instance, if the root of the AST is a vertex field that goes to type Animal, the
    returned type name will be Animal.

    If the input AST is a type coercion, the root field name will be the coerced type rather
    than the union or interface type, and the selection set will contain actual fields
    rather than a single inline fragment.

    Args:
        ast: type Node, the AST that, if split off into its own Document, would have the the
             type (named the same as the root vertex field) and root selections that this
             function outputs
        type_info: TypeInfo, used to check for the type that fields lead to

    Returns:
        Tuple[str, List[Union[Field, InlineFragment]]], name and selections of the root
        vertex field of the input AST if it were made into its own separate Document
    """
    child_type = type_info.get_type()  # GraphQLType
    if child_type is None:
        raise SchemaStructureError(
            u'The provided merged schema descriptor may be invalid, as the type '
            u'corresponding to the field "{}" under type "{}" cannot be '
            u'found.'.format(ast.name.value, type_info.get_parent_type())
        )
    child_type_name = strip_non_null_and_list_from_type(child_type).name

    child_selection_set = ast.selection_set
    # Adjust for type coercion
    if (
        child_selection_set is not None and
        len(child_selection_set.selections) == 1 and
        isinstance(child_selection_set.selections[0], InlineFragment)
    ):
        type_coercion_inline_fragment = child_selection_set.selections[0]
        child_type_name = type_coercion_inline_fragment.type_condition.name.value
        child_selection_set = type_coercion_inline_fragment.selection_set

    return child_type_name, child_selection_set.selections


def _replace_or_insert_property_field(selections, new_field):
    """Return a copy of the input selections, with new_field added or replacing existing field.

    If there is an existing field with the same name as new_field, replace. Otherwise, insert
    new_field after the last existing property field.

    Inputs are not modified.

    Args:
        selections: List[Union[Field, InlineFragment]], where all property fields occur
                    before all vertex fields and inline fragments
        new_field: Field object, to be inserted into selections

    Returns:
        List[Union[Field, InlineFragment]]
    """
    selections = copy(selections)
    for index, selection in enumerate(selections):
        if (
            isinstance(selection, Field) and
            selection.name.value == new_field.name.value
        ):
            selections[index] = new_field
            return selections
        if not is_property_field_ast(selection):
            selections.insert(index, new_field)
            return selections
    # No vertex fields and no property fields of the same name
    selections.append(new_field)
    return selections


def _get_out_name_optionally_add_output(field, intermediate_out_name_assigner):
    """Return out_name of @output on field, creating new @output if needed.

    Args:
        field: Field object, whose directives we may modify by adding an @output directive
        intermediate_out_name_assigner: IntermediateOutNameAssigner, which will be used to
                                        generate an out_name, if it's necessary to create a
                                        new @output directive

    Returns:
        str, name of the out_name of the @output directive, either pre-existing or newly
        generated
    """
    # Check for existing directive
    output_directive = try_get_ast_by_name_and_type(
        field.directives, OutputDirective.name, Directive
    )
    if output_directive is None:
        # Create and add new directive to field
        out_name = intermediate_out_name_assigner.assign_and_return_out_name()
        output_directive = _get_output_directive(out_name)
        if field.directives is None:
            field.directives = []
        field.directives.append(output_directive)
        return out_name
    else:
        return output_directive.arguments[0].value.value  # Location of value of out_name


def _get_output_directive(out_name):
    """Return a Directive representing an @output with the input out_name."""
    return Directive(
        name=Name(value=OutputDirective.name),
        arguments=[
            Argument(
                name=Name(value=u'out_name'),
                value=StringValue(value=out_name),
            ),
        ],
    )


def _get_query_document(root_vertex_field_name, root_selections):
    """Return a Document representing a query with the specified name and selections."""
    return Document(
        definitions=[
            OperationDefinition(
                operation='query',
                selection_set=SelectionSet(
                    selections=[
                        Field(
                            name=Name(value=root_vertex_field_name),
                            selection_set=SelectionSet(
                                selections=root_selections,
                            ),
                            directives=[],
                        )
                    ]
                )
            )
        ]
    )


def _add_query_connections(parent_query_node, child_query_node, parent_field_out_name,
                           child_field_out_name):
    """Modify parent and child SubQueryNodes by adding QueryConnections between them."""
    if child_query_node.parent_query_connection is not None:
        raise AssertionError(
            u'The input child query node already has a parent connection, {}'.format(
                child_query_node.parent_query_connection
            )
        )
    if any(
        query_connection_from_parent.sink_query_node is child_query_node
        for query_connection_from_parent in parent_query_node.child_query_connections
    ):
        raise AssertionError(
            u'The input parent query node already has the child query node in a child query '
            u'connection.'
        )
    # Create QueryConnections
    new_query_connection_from_parent = QueryConnection(
        sink_query_node=child_query_node,
        source_field_out_name=parent_field_out_name,
        sink_field_out_name=child_field_out_name,
    )
    new_query_connection_from_child = QueryConnection(
        sink_query_node=parent_query_node,
        source_field_out_name=child_field_out_name,
        sink_field_out_name=parent_field_out_name,
    )
    # Add QueryConnections
    parent_query_node.child_query_connections.append(new_query_connection_from_parent)
    child_query_node.parent_query_connection = new_query_connection_from_child


class IntermediateOutNameAssigner(object):
    """Used to generate and keep track of out_name of @output directives."""

    def __init__(self):
        """Create assigner with empty records."""
        self.intermediate_output_names = set()
        self.intermediate_output_count = 0

    def assign_and_return_out_name(self):
        """Assign and return name, increment count, add name to records."""
        out_name = '__intermediate_output_' + str(self.intermediate_output_count)
        self.intermediate_output_count += 1
        self.intermediate_output_names.add(out_name)
        return out_name
