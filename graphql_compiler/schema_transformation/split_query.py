# Copyright 2019-present Kensho Technologies, LLC.
from collections import OrderedDict, namedtuple
from copy import copy

from graphql.language.ast import (
    Argument, Directive, Document, Field, InlineFragment, InterfaceTypeDefinition, Name,
    ObjectTypeDefinition, OperationDefinition, SelectionSet, StringValue
)
from graphql.language.visitor import TypeInfoVisitor, Visitor, visit
from graphql.utils.type_info import TypeInfo
import six

from ..ast_manipulation import get_only_query_definition
from ..compiler.helpers import strip_non_null_and_list_from_type
from ..exceptions import GraphQLValidationError
from ..schema import FilterDirective, OptionalDirective, OutputDirective
from .utils import (
    SchemaStructureError, check_query_is_valid_to_split, is_property_field_ast,
    try_get_ast_by_name_and_type, try_get_inline_fragment
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
    query_node, ast, type_info, edge_to_stitch_fields, name_assigner
):
    """Return an AST node with which to replace the input AST in the selections that contain it.

    This function examines the selections of the input AST, and recursively calls either
    _split_query_ast_one_level_recursive_type_coercion or
    _split_query_ast_one_level_recursive_normal_fields
    depending on whether the selections contains a single InlineFragment or a number of normal
    fields.

    Args:
        query_node: SubQueryNode, whose list of child query connections may be modified to
                    include new children
        ast: Field, InlineFragment, or OperationDefinition, the AST that we are trying to split
             into child components. It is not modified by this function
        type_info: TypeInfo, used to get information about the types of fields while traversing
                   the query AST
        edge_to_stitch_fields: Dict[Tuple(str, str), Tuple(str, str)], mapping
                               (type name, vertex field name) to
                               (source field name, sink field name) used in the @stitch directive
                               for each cross schema edge
        name_assigner: IntermediateOutNameAssigner, object used to generate and keep track of
                       names of newly created @output directives

    Returns:
        Field, InlineFragment, or OperationDefinition, the AST with which to replace the input
        AST in the selections that contain it
    """
    type_info.enter(ast.selection_set)
    selections = ast.selection_set.selections
    if try_get_inline_fragment(selections) is not None:
        # Case 1: type coercion
        new_selections = _split_query_ast_one_level_recursive_type_coercion(
            query_node, selections, type_info, edge_to_stitch_fields, name_assigner
        )
    else:
        # Case 2: normal fields
        new_selections = _split_query_ast_one_level_recursive_normal_fields(
            query_node, selections, type_info, edge_to_stitch_fields, name_assigner
        )
    type_info.leave(ast.selection_set)

    # Return input, or make copy
    if new_selections is not selections:
        new_ast = copy(ast)
        new_ast.selection_set = SelectionSet(selections=new_selections)
        return new_ast
    else:
        return ast


def _split_query_ast_one_level_recursive_type_coercion(
    query_node, selections, type_info, edge_to_stitch_fields, name_assigner
):
    """One case of splitting query, selections contains a single inline fragment.

    _split_query_ast_one_level_recursive will be called recursively on the single selection.

    Args:
        query_node: SubQueryNode, whose list of child query connections may be modified to
                    include new children
        selections: List[InlineFragment], containing a single inline fragment (type coercion)
        type_info: TypeInfo, used to get information about the types of fields while traversing
                   the query AST
        edge_to_stitch_fields: Dict[Tuple(str, str), Tuple(str, str)], mapping
                               (type name, vertex field name) to
                               (source field name, sink field name) used in the @stitch directive
                               for each cross schema edge
        name_assigner: IntermediateOutNameAssigner, object used to generate and keep track of
                       names of newly created @output directives

    Returns:
        List[InlineFragment], containing a single inline fragment, used to replace the
        list of selections in the SelectionSet one level above. If no changes were made, the
        exact input list object will be returned
    """
    type_coercion = try_get_inline_fragment(selections)

    type_info.enter(type_coercion)
    new_type_coercion = _split_query_ast_one_level_recursive(
        query_node, type_coercion, type_info, edge_to_stitch_fields, name_assigner
    )
    type_info.leave(type_coercion)

    if new_type_coercion is not type_coercion:
        return [new_type_coercion]
    else:
        return selections


def _split_query_ast_one_level_recursive_normal_fields(
    query_node, selections, type_info, edge_to_stitch_fields, name_assigner
):
    """One case of splitting query, selections contains a number of fields, no inline fragments.

    The input selections will be divided into three sets: property fields, intra-schema vertex
    fields, and cross-schema vertex fields.

    Each cross-schema vertex field will not be included in the output selections. The AST
    branch that each cross-schema vertex field leads to will be made into its own separate query
    AST. The parent and child property fields used in the stich will be added to the parent and
    child ASTs, if not already present. @outpt directives will be added to these parent and
    child property fields, if not already present. @filter directives will not be added to
    child property fields in this step. This is because one may choose to rearrange and reroot
    the tree of SubQueryNodes to achieve an execution order with better performance. @filter
    directives should be added only once the tree's structure is fixed.

    _split_query_ast_one_level_recursive will be called recursive on each intra-schema vertex
    field.

    Args:
        query_node: SubQueryNode, whose list of child query connections may be modified to
                    include new children
        selections: List[Field], containing a number of property fields and vertex fields
        type_info: TypeInfo, used to get information about the types of fields while traversing
                   the query AST
        edge_to_stitch_fields: Dict[Tuple(str, str), Tuple(str, str)], mapping
                               (type name, vertex field name) to
                               (source field name, sink field name) used in the @stitch directive
                               for each cross schema edge
        name_assigner: IntermediateOutNameAssigner, object used to generate and keep track of
                       names of newly created @output directives

    Returns:
        List[Field], with which to replace the list of selections in the SelectionSet one level
        above. All cross schema edges in the input list will be removed, and in their place,
        property fields added or modified. If no changes were made, the exact input list object
        will be returned
    """
    parent_type_name = type_info.get_parent_type().name

    made_changes = False

    # First, collection all property fields, but don't make any changes to them yet
    property_fields_map, vertex_fields = _split_selections_property_and_vertex(selections)

    # Second, process cross schema fields. This will modify our record of property fields, and
    # create child SubQueryNodes attached to the input SubQueryNode
    intra_schema_fields, cross_schema_fields = _split_vertex_fields_intra_and_cross_schema(
        vertex_fields, parent_type_name, edge_to_stitch_fields
    )
    for cross_schema_field in cross_schema_fields:
        type_info.enter(cross_schema_field)
        child_type = type_info.get_type()
        if child_type is not None:
            child_type_name = strip_non_null_and_list_from_type(child_type).name
        else:
            raise AssertionError(
                u'The query may be invalid against the schema, causing TypeInfo to lose track '
                u'of the types of fields. This occurs at the cross schema field "{}", while '
                u'splitting the AST "{}"'.format(
                    cross_schema_field, query_node.query_ast
                )
            )
        stitch_data_key = (parent_type_name, cross_schema_field.name.value)
        parent_field_name, child_field_name = edge_to_stitch_fields[stitch_data_key]
        _process_cross_schema_field(
            query_node, cross_schema_field, property_fields_map, child_type_name,
            parent_field_name, child_field_name, name_assigner
        )
        made_changes = True  # Cross schema edges are removed from the output, causing changes
        type_info.leave(cross_schema_field)

    # Third, process intra schema edges by recursing on them
    new_intra_schema_fields = []
    for intra_schema_field in intra_schema_fields:
        type_info.enter(intra_schema_field)
        new_intra_schema_field = _split_query_ast_one_level_recursive(
            query_node, intra_schema_field, type_info, edge_to_stitch_fields, name_assigner
        )
        if new_intra_schema_field is not intra_schema_field:
            made_changes = True
        new_intra_schema_fields.append(new_intra_schema_field)
        type_info.leave(intra_schema_field)

    # Return input, or make copy
    if made_changes:
        new_selections = _get_selections_from_property_and_vertex_fields(
            property_fields_map, new_intra_schema_fields
        )
        return new_selections
    else:
        return selections


def _process_cross_schema_field(
    query_node, cross_schema_field, property_fields_map, child_type_name, parent_field_name,
    child_field_name, name_assigner
):
    """Construct child SubQueryNode from branch, update record of property fields.

    Args:
        query_node: SubQueryNode, the "parent" query node. The new child SubQueryNode will be
                    added as a child of this node
        cross_schema_field: Field, representing an edge crossing schemas. It is not modified
                            by this function. The branch that this edge leads to will be used
                            to create a new SubQueryNode
        property_fields_map: OrderedDict[str, Field], mapping the name of each property field
                             to its representation. It is modified by this function. If no
                             property field of the specified name already exists, one will be
                             created and added. If one already exists, it will be replaced by
                             a new Field object. The new Field will contains directives from
                             the existing field and the cross schema vertex fields, as well
                             as a generated @output directive if one doesn't yet exist
        child_type_name: str, name of the type that this cross schema field leads to
        parent_field_name: str, name of the property field that the parent (source of the cross
                           schema edge) stitches on
        child_field_name: str, name of the property field that the child (the type that this
                          cross schema field leads to) stitches on
        name_assigner: IntermediateOutNameAssigner, object used to generate and keep track of
                       names of newly created @output directives
    """
    existing_property_field = property_fields_map.get(parent_field_name, None)
    # Get property field inheriting the right directives
    parent_property_field = _get_property_field(
        existing_property_field, parent_field_name, cross_schema_field.directives
    )
    # Add @output if needed, record out_name
    parent_output_name = _get_out_name_optionally_add_output(
        parent_property_field, name_assigner
    )
    # Create child query node around ast
    child_query_node, child_output_name = _get_child_query_node_and_out_name(
        cross_schema_field, child_type_name, child_field_name, name_assigner
    )
    # Create and add QueryConnections
    _add_query_connections(
        query_node, child_query_node, parent_output_name, child_output_name
    )
    # Add or replace the new property field
    property_fields_map[parent_property_field.name.value] = parent_property_field


def _split_selections_property_and_vertex(selections):
    """Split input selections into property fields and vertex fields/type coercions.

    Args:
        selections: List[Union[Field]], not modified by this function

    Returns:
        Tuple[OrderedDict[str, Field], List[Field]]. The first element of the tuple is a map
        from the names of property fields to their representations. The second element is a
        list of vertex fields

    Raises:
        GraphQLValidationError if some property field is repeated
    """
    if selections is None:
        raise AssertionError(u'Input selections is None, rather than a list.')
    property_fields_map = OrderedDict()
    vertex_fields = []
    for selection in selections:
        if is_property_field_ast(selection):
            name = selection.name.value
            if name in property_fields_map:
                raise GraphQLValidationError(
                    u'The field named "{}" occurs more than once in the selection {}.'.format(
                        name, selections
                    )
                )
            property_fields_map[name] = selection
        else:
            vertex_fields.append(selection)
    return property_fields_map, vertex_fields


def _split_vertex_fields_intra_and_cross_schema(
    vertex_fields, parent_type_name, edge_to_stitch_fields
):
    """Split input list of vertex fields into intra-schema and cross-schema fields.

    Args:
        vertex_fields: List[Field], not modified by this function
        parent_type_name: str, name of the type that has the input list of vertex fields as fields
        edge_to_stitch_fields: Dict[Tuple(str, str), Tuple(str, str)], mapping
                               (type name, vertex field name) to
                               (source field name, sink field name) used in the @stitch directive
                               for each cross schema edge

    Returns:
        Tuple[List[Field], List[Field]]. The first element is a list of intra schema fields,
        the second element is a list of cross schema fields
    """
    intra_schema_fields = []
    cross_schema_fields = []
    for vertex_field in vertex_fields:
        if isinstance(vertex_field, Field):
            stitch_data_key = (parent_type_name, vertex_field.name.value)
            if stitch_data_key in edge_to_stitch_fields:
                cross_schema_fields.append(vertex_field)
            else:
                intra_schema_fields.append(vertex_field)
        else:
            raise AssertionError(
                u'Input vertex field {} is not a Field'.format(vertex_field)
            )
    return intra_schema_fields, cross_schema_fields


def _get_selections_from_property_and_vertex_fields(property_fields_map, vertex_fields):
    """Combine property fields and vertex fields into a list of selections.

    Args:
        property_fields_map: OrderedDict[str, Field], mapping name of field to their
                             representation. It is not modified by this function
        vertex_fields: List[Field]. It is not modified by this function

    Returns:
        List[Field], containing all property fields then all vertex fields, in order
    """
    selections = list(six.itervalues(property_fields_map))
    selections.extend(vertex_fields)
    return selections


def _get_child_query_node_and_out_name(ast, child_type_name, child_field_name, name_assigner):
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
        ast: Field or InlineFragment, representing the AST that we're using to build a child
             node. It is not modified by this function
        child_field_name: str. If no field of this name currently exists as a part of the root
                          selections of the input AST, a new field will be created in the AST
                          contained in the output child query node
        name_assigner: IntermediateOutNameAssigner, object used to generate and keep track of
                       names of newly created @output directives

    Returns:
        Tuple[SubQueryNode, str], the child sub query node wrapping around the input AST, and
        the out_name of the @output directive uniquely identifying the field used for stitching
        in this sub query node
    """
    # Get type and selections of child AST, taking into account type coercions
    child_selection_set = ast.selection_set
    type_coercion = try_get_inline_fragment(child_selection_set.selections)
    if type_coercion is not None:
        child_type_name = type_coercion.type_condition.name.value
        child_selection_set = type_coercion.selection_set
    child_selections = child_selection_set.selections

    # Get existing field with name in child
    existing_child_property_field = try_get_ast_by_name_and_type(
        child_selections, child_field_name, Field
    )
    child_property_field = _get_property_field(
        existing_child_property_field, child_field_name, None
    )
    # Add @output if needed, record out_name
    child_output_name = _get_out_name_optionally_add_output(child_property_field, name_assigner)
    # Get new child_selections by replacing or adding in new property field
    child_property_fields_map, child_vertex_fields = _split_selections_property_and_vertex(
        child_selections
    )
    child_property_fields_map[child_field_name] = child_property_field
    child_selections = _get_selections_from_property_and_vertex_fields(
        child_property_fields_map, child_vertex_fields
    )
    # Wrap around
    # NOTE: if child_type_name does not actually exist as a root field (not all types are
    # required to have a corresponding root vertex field), then this query will be invalid
    child_query_ast = _get_query_document(child_type_name, child_selections)
    child_query_node = SubQueryNode(child_query_ast)

    return child_query_node, child_output_name


def _get_property_field(existing_field, field_name, directives_from_edge):
    """Return a Field object with field_name, sharing directives with any such existing field.

    Any valid directives in directives_on_edge will be transferred over to the new field.
    If there is an existing Field in selection with field_name, the returned new Field
    will also contain all directives of the existing field with that name.

    Args:
        existing_field: Field or None. If it's not None, it is a field with field_name. The
                        directives of this field will carry output to the output field
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

    # Transfer directives from existing field of the same name
    if existing_field is not None:
        # Existing field, add all its directives
        directives_from_existing_field = existing_field.directives
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


def _get_out_name_optionally_add_output(field, name_assigner):
    """Return out_name of @output on field, creating new @output if needed.

    Args:
        field: Field object, whose directives we may modify by adding an @output directive
        name_assigner: IntermediateOutNameAssigner, object used to generate and keep track of
                       names of newly created @output directives

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
        out_name = name_assigner.assign_and_return_out_name()
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
