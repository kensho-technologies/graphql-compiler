# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple, OrderedDict
from copy import copy
import six

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
    query_node, ast, type_info, edge_to_stitch_fields, intermediate_out_name_assigner
):
    """Return an AST node with which to replace the input AST in the selections that contain it.

    This function examines the selections of the input AST, and divides them into three sets:
    property fields, intra-schema vertex fields, and cross-schema vertex fields.

    Each cross-schema vertex field will have its branch removed from the output AST, and made
    into its own separate query AST. The parent and child property fields used in
    the stitch will be added to the parent and child ASTs. @output directives will be added
    to the parent and child property fields, if not already present.

    The function will be called recursively on each intra-schema vertex field.

    Args:
        query_node: SubQueryNode, whose list of child query connections may be modified to
                    include new children
        ast: Field, InlineFragment, or OperationDefinition, the AST that we are trying to split
             into child components. It is not modified by this function
        type_info: TypeInfo, used to get information about the types of fields while traversing
                   the query ast
        edge_to_stitch_fields: Dict[Tuple(str, str), Tuple(str, str)], mapping
                               (type name, vertex field name) to
                               (source field name, sink field name) used in the @stitch directive
                               for each cross schema edge
        intermediate_out_name_assigner: IntermediateOutNameAssigner, object used to generate
                                        and keep track of names of newly created @output
                                        directives
    """
    # Split selections into three kinds: property fields, cross schema vertex fields, normal
    # vertex fields/type coercions
    type_info.enter(ast.selection_set)
    parent_type_name = type_info.get_parent_type().name

    property_fields_map, vertex_fields = _split_selections_property_and_vertex(
        ast.selection_set.selections
    )
    intra_schema_fields, cross_schema_fields = _split_vertex_fields_intra_and_cross_schema(
        vertex_fields, parent_type_name, edge_to_stitch_fields
    )

    made_changes = False
    if len(cross_schema_fields) > 0:
        made_changes = True

    # First, process cross schema fields
    for cross_schema_field in cross_schema_fields:
        type_info.enter(cross_schema_field)

        if type_info.get_type() is not None:
            child_type_name = strip_non_null_and_list_from_type(type_info.get_type()).name
        else:
            raise AssertionError(u'')

        parent_field_name, child_field_name = edge_to_stitch_fields[
            (parent_type_name, cross_schema_field.name.value)
        ]
        _process_cross_schema_field(
            query_node, cross_schema_field, property_fields_map, child_type_name,
            parent_field_name, child_field_name, intermediate_out_name_assigner
        )
        type_info.leave(cross_schema_field)

    # Then, process intra schema edges by recursing on them
    new_intra_schema_fields = []
    for intra_schema_field in intra_schema_fields:
        type_info.enter(intra_schema_field)
        new_intra_schema_field = _split_query_ast_one_level_recursive(
            query_node, intra_schema_field, type_info, edge_to_stitch_fields,
            intermediate_out_name_assigner
        )
        if new_intra_schema_field is not intra_schema_field:
            made_changes = True
        new_intra_schema_fields.append(new_intra_schema_field)
        type_info.leave(intra_schema_field)

    type_info.leave(ast.selection_set)

    # Make copy, or return input if unchanged
    if made_changes:
        # Construct new selections
        new_ast = copy(ast)
        new_selections = _get_selections_from_property_and_vertex_fields(
            property_fields_map, new_intra_schema_fields
        )
        new_ast.selection_set = SelectionSet(selections=new_selections)
        return new_ast
    else:
        return ast


def _process_cross_schema_field(
    query_node, cross_schema_field, property_fields_map, child_type_name, parent_field_name,
    child_field_name, intermediate_out_name_assigner
):
    """Construct child SubQueryNode from branch, update record of property fields.

    Args:
        query_node: SubQueryNode
        cross_schema_field: Field, representing an edge crossing schemas, not modified by this
                            function
        property_fields_map: OrderedDict[str, Field], mapping the name of each property field
                             to its representation. It is modified by this function. If no
                             property field of the specified name already exists, one will be
                             created and added. If one already exists, it will be replace by
                             a new Field object. The new Field will contains directives from
                             the cross schema vertex field, as well as a generated @output
                             directive if one doesn't yet exist
        child_type_name: str, name of the type that this cross schema field leads to
        parent_field_name: str, name of the property field that the parent (source of the cross
                           schema edge) stitches on
        child_field_name: str, name of the property field that the child (the type that this
                          cross schema field leads to) stitches on
        intermediate_out_name_assigner: IntermediateOutNameAssigner, object used to generate
                                        and keep track of names of newly created @output
                                        directives
    """
    existing_property_field = property_fields_map.get(parent_field_name, None)
    # Get property field inheriting the right directives
    parent_property_field = _get_property_field(
        existing_property_field, parent_field_name, cross_schema_field.directives
    )
    # Add @output if needed, record out_name
    parent_output_name = _get_out_name_optionally_add_output(
        parent_property_field, intermediate_out_name_assigner
    )
    # Create child query node around ast
    child_query_node, child_output_name = _get_child_query_node_and_out_name(
        cross_schema_field, child_type_name, child_field_name, intermediate_out_name_assigner
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
        selections: List[Union[Field, InlineFragment]], not modified by this function

    Returns:
        Tuple[OrderedDict[str, Field], List[Union[Field, InlineFragment]]]. The first element
        of the tuple is a map from the names of property fields to their representations. The
        second element is a list of vertex fields and type coercions

    Raises:
        GraphQLValidationError if some property field is repeated
    """
    if selections is None:
        raise AssertionError(u'Input selections is None, rather than a list.')
    property_fields_map = OrderedDict()
    vertex_fields = []  # Also includes type coercions
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
        vertex_fields: List[Union[Field, InlineFragment]], not modified by this function
        parent_type_name: str, name of the type that has the input list of vertex fields as fields
        edge_to_stitch_fields: Dict[Tuple(str, str), Tuple(str, str)], mapping
                               (type name, vertex field name) to
                               (source field name, sink field name) used in the @stitch directive
                               for each cross schema edge

    Returns:
        Tuple[List[Union[Field, InlineFragment]], List[Field]]. The first element is a list of
        intra schema fields, the second element is a list of cross schema fields
    """
    intra_schema_fields = []
    cross_schema_fields = []
    for vertex_field in vertex_fields:
        if isinstance(vertex_field, Field):
            type_and_field = (parent_type_name, vertex_field.name.value)
            if type_and_field in edge_to_stitch_fields:
                cross_schema_fields.append(vertex_field)
            else:
                intra_schema_fields.append(vertex_field)
        elif isinstance(vertex_field, InlineFragment):
            intra_schema_fields.append(vertex_field)
        else:
            raise AssertionError(
                u'Input vertex field {} is neither a Field nor an InlineFragment'.format(
                    vertex_field
                )
            )
    return intra_schema_fields, cross_schema_fields


def _get_selections_from_property_and_vertex_fields(property_fields_map, vertex_fields):
    """Combine property fields and vertex fields into a list of selections.

    Args:
        property_fields_map: OrderedDict[str, Field], mapping name of field to their
                             representation. It is not modified by this function
        vertex_fields: List[Union[Field, InlineFragment]]. It is not modified by this function

    Returns:
        List[Union[Field, InlineFragment]], containing all property fields then all vertex fields,
        in order
    """
    selections = list(six.itervalues(property_fields_map))
    selections.extend(vertex_fields)
    return selections


def _get_child_query_node_and_out_name(ast, child_type_name, child_field_name,
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
    # Get type and selections of child AST, taking into account type coercions
    child_selection_set = ast.selection_set
    if (
        child_selection_set is not None and
        len(child_selection_set.selections) == 1 and
        isinstance(child_selection_set.selections[0], InlineFragment)
    ):
        type_coercion_inline_fragment = child_selection_set.selections[0]
        child_type_name = type_coercion_inline_fragment.type_condition.name.value
        child_selection_set = type_coercion_inline_fragment.selection_set
    child_selections = child_selection_set.selections

    # Get existing field with name in child
    existing_child_property_field = try_get_ast_by_name_and_type(
        child_selections, child_field_name, Field
    )
    child_property_field = _get_property_field(existing_child_property_field, child_field_name, [])
    # Add @output if needed, record out_name
    child_output_name = _get_out_name_optionally_add_output(
        child_property_field, intermediate_out_name_assigner
    )
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


def _get_property_field(parent_field, field_name, directives_from_edge):
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

    # Transfer directives from existing field of the same name
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
