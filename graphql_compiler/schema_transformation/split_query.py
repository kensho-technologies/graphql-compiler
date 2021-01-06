# Copyright 2019-present Kensho Technologies, LLC.
from collections import OrderedDict
from copy import copy
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple, TypeVar, Union

from graphql import TypeInfo, TypeInfoVisitor, Visitor, validate, visit
from graphql.language.ast import (
    ArgumentNode,
    BooleanValueNode,
    DirectiveNode,
    DocumentNode,
    FieldNode,
    InlineFragmentNode,
    InterfaceTypeDefinitionNode,
    NameNode,
    ObjectTypeDefinitionNode,
    OperationDefinitionNode,
    OperationType,
    SelectionNode,
    SelectionSetNode,
    StringValueNode,
)
from graphql.type.definition import GraphQLOutputType
import six

from graphql_compiler.typedefs import ScalarConstantValueNodes

from ..ast_manipulation import get_only_query_definition
from ..compiler.helpers import get_uniquely_named_objects_by_name, strip_non_null_and_list_from_type
from ..exceptions import GraphQLValidationError
from ..schema import FilterDirective, OptionalDirective, OutputDirective
from .merge_schemas import MergedSchemaDescriptor
from .utils import (
    SchemaStructureError,
    check_query_is_valid_to_split,
    is_property_field_ast,
    try_get_ast_by_name_and_type,
    try_get_inline_fragment,
)


AstType = TypeVar("AstType", FieldNode, InlineFragmentNode, OperationDefinitionNode)


@dataclass(frozen=True)
class QueryConnection:
    """Describes what fields queries are connected on."""

    # SubQueryNode
    sink_query_node: "SubQueryNode"

    # The unique out name on the @output of the source property field in the stitch.
    source_field_out_name: str

    # The unique out name on the @output of the sink property field in the stitch.
    sink_field_out_name: str


class SubQueryNode(object):
    def __init__(self, query_ast: DocumentNode) -> None:
        """Build a SubQueryNode object representing a piece of a larger query, targeting one schema.

        Args:
            query_ast: representing one piece of a larger query on an individual schema.
        """
        # The query on schema represented by schema_id.
        self.query_ast: DocumentNode = query_ast

        # The schema the query_ast is over.
        self.schema_id: Optional[str] = None

        # Query that the current query depends on. None if current query does not depend on another.
        self.parent_query_connection: Optional[QueryConnection] = None

        # List of queries that depend on the current query.
        self.child_query_connections: List[QueryConnection] = []


class IntermediateOutNameAssigner(object):
    """Used to generate and keep track of out_name of @output directives."""

    def __init__(self):
        """Create assigner with empty records."""
        self.intermediate_output_names = set()
        self.intermediate_output_count = 0

    def assign_and_return_out_name(self) -> str:
        """Assign and return name, increment count, add name to records."""
        out_name = "__intermediate_output_" + str(self.intermediate_output_count)
        self.intermediate_output_count += 1
        self.intermediate_output_names.add(out_name)
        return out_name


class SchemaIdSetterVisitor(Visitor):
    def __init__(
        self, type_info: TypeInfo, query_node: SubQueryNode, type_name_to_schema_id: Dict[str, str]
    ) -> None:
        """Create a visitor for setting the schema_id of the input query node.

        Args:
            type_info: Used to keep track of types of fields while traversing the AST.
            query_node: Representation of a subquery whose schema_id will be modified.
            type_name_to_schema_id: Mapping the names of types to the id of the schema from
                                    which they came.
        """
        self.type_info = type_info
        self.query_node = query_node
        self.type_name_to_schema_id = type_name_to_schema_id

    def enter_field(
        self, node: Any, key: Any, parent: Any, path: List[Any], ancestors: List[Any]
    ) -> None:
        """Check the schema of the type that the field leads to."""
        type_to_check = self.type_info.get_type()
        if type_to_check is None:
            raise AssertionError(
                "type_to_check is unexpectedly None, but was expected to be one of "
                f"{GraphQLOutputType}."
            )
        child_type_name = strip_non_null_and_list_from_type(type_to_check).name
        self._check_or_set_schema_id(child_type_name)

    def enter_inline_fragment(
        self, node: InlineFragmentNode, key: Any, parent: Any, path: List[Any], ancestors: List[Any]
    ) -> None:
        """Check the schema of the coerced type."""
        self._check_or_set_schema_id(node.type_condition.name.value)

    def _check_or_set_schema_id(self, type_name: str) -> None:
        """Set the schema id of the root node if not yet set, otherwise check schema ids agree.

        Args:
            type_name: Name of the type whose schema id we're comparing against the
                       previously recorded schema id.
        """
        if type_name in self.type_name_to_schema_id:  # It may be a scalar, and thus not found
            current_type_schema_id = self.type_name_to_schema_id[type_name]
            prior_type_schema_id = self.query_node.schema_id
            if prior_type_schema_id is None:  # First time checking schema_id
                self.query_node.schema_id = current_type_schema_id
            elif current_type_schema_id != prior_type_schema_id:
                # A single query piece has types from two schemas -- merged_schema_descriptor
                # is invalid: an edge field without a @stitch directive crosses schemas,
                # or type_name_to_schema_id is wrong
                raise SchemaStructureError(
                    "The provided merged schema descriptor may be invalid. Perhaps some "
                    "vertex field that does not have a @stitch directive crosses schemas. As "
                    'a result, query piece "{}" appears to contain types from more than '
                    'one schema. Type "{}" belongs to schema "{}", while some other type '
                    'belongs to schema "{}".'.format(
                        self.query_node.query_ast,
                        type_name,
                        current_type_schema_id,
                        prior_type_schema_id,
                    )
                )


def split_query(
    query_ast: DocumentNode, merged_schema_descriptor: MergedSchemaDescriptor
) -> Tuple[SubQueryNode, FrozenSet[str]]:
    """Split input query AST into a tree of SubQueryNodes targeting each individual schema.

    Property fields used in the stitch will be added if not already present. @output directives
    will be added on used property fields if not already present. All output names of @output
    directives will be unique, and thus used to identify fields later down the line for adding
    @filter directives.

    Args:
        query_ast: representing a GraphQL query to split.
        merged_schema_descriptor: description of the merged schema to split the query over.

    Returns:
        Tuple of:
            - The root of the tree of SubQueryNodes, where each node contains an AST representing a
              part of the overall query, targeting a specific schema.
            - The set of all intermediate output names that are to be removed at the end.

    Raises:
        - GraphQLValidationError if the query doesn't validate against the schema, contains
          unsupported directives, some property field occurs after a vertex field in some
          selection, or some inline fragment coexists with other fields or inline fragment
          on the same scope
        - SchemaStructureError if the input merged_schema_descriptor appears to be invalid
          or inconsistent
    """
    check_query_is_valid_to_split(merged_schema_descriptor.schema, query_ast)

    # If schema directives are correctly represented in the schema object, type_info is all
    # that's needed to detect and address stitching fields. However, GraphQL currently ignores
    # schema directives when converting an AST to a schema object. Until this issue is
    # fixed, it's necessary to use additional information from pre-processing the schema AST.
    edge_to_stitch_fields = _get_edge_to_stitch_fields(merged_schema_descriptor)
    name_assigner = IntermediateOutNameAssigner()

    root_query_node = SubQueryNode(query_ast)
    query_nodes_to_split = [root_query_node]

    # Construct full tree of SubQueryNodes in a depth first search pattern.
    while len(query_nodes_to_split) > 0:
        current_node_to_split = query_nodes_to_split.pop()

        _split_query_one_level(
            current_node_to_split, merged_schema_descriptor, edge_to_stitch_fields, name_assigner
        )

        query_nodes_to_split.extend(
            child_query_connection.sink_query_node
            for child_query_connection in current_node_to_split.child_query_connections
        )

    return root_query_node, frozenset(name_assigner.intermediate_output_names)


def _get_edge_to_stitch_fields(
    merged_schema_descriptor: MergedSchemaDescriptor,
) -> Dict[Tuple[str, str], Tuple[str, str]]:
    """Get a map from type/field of each cross schema edge, to the fields that the edge stitches.

    This is necessary only because GraphQL currently doesn't process schema directives correctly.
    Once schema directives are correctly added to GraphQLSchema objects, this part may be
    removed as directives on a schema field can be directly accessed.

    Args:
        merged_schema_descriptor: containing a schema AST and a map from names of types to
                                  their schema ids.

    Returns:
        Dictionary mapping (type name, vertex field name) to (source field name, sink field name)
        used in the @stitch directive, for each cross schema edge.
    """
    edge_to_stitch_fields = {}
    for type_definition in merged_schema_descriptor.schema_ast.definitions:
        if isinstance(type_definition, (ObjectTypeDefinitionNode, InterfaceTypeDefinitionNode)):
            for field_definition in type_definition.fields:
                stitch_directive = try_get_ast_by_name_and_type(
                    field_definition.directives, "stitch", DirectiveNode
                )
                if stitch_directive is not None:
                    if not isinstance(stitch_directive, DirectiveNode):
                        raise AssertionError(
                            "stitch_directive should be a DirectiveNode, "
                            f"but was of type {type(stitch_directive)}."
                        )
                    fields_by_name = get_uniquely_named_objects_by_name(stitch_directive.arguments)
                    source_field_value = fields_by_name["source_field"].value
                    sink_field_value = fields_by_name["sink_field"].value
                    if not isinstance(source_field_value, ScalarConstantValueNodes) or isinstance(
                        source_field_value, BooleanValueNode
                    ):
                        raise AssertionError(
                            f"Source field value must be one of type {ScalarConstantValueNodes}, "
                            f"but was of type {type(source_field_value)}."
                        )
                    source_field_name = source_field_value.value
                    if not isinstance(sink_field_value, ScalarConstantValueNodes) or isinstance(
                        sink_field_value, BooleanValueNode
                    ):
                        raise AssertionError(
                            f"Sink field value must be one of type {ScalarConstantValueNodes}, "
                            f"but was of type {type(sink_field_value)}."
                        )
                    sink_field_name = sink_field_value.value
                    stitch_data_key = (type_definition.name.value, field_definition.name.value)
                    edge_to_stitch_fields[stitch_data_key] = (source_field_name, sink_field_name)

    return edge_to_stitch_fields


def _split_query_one_level(
    query_node: SubQueryNode,
    merged_schema_descriptor: MergedSchemaDescriptor,
    edge_to_stitch_fields: Dict[Tuple[str, str], Tuple[str, str]],
    name_assigner: IntermediateOutNameAssigner,
) -> None:
    """Split the query node, creating children out of all branches across cross schema edges.

    The input query_node will be modified. Its query_ast will be replaced by a new AST with
    branches leading out of cross schema edges removed, and new property fields and @output
    directives added as necessary. Its child_query_connections will be modified by tacking
    on SubQueryNodes created from these cut-off branches.

    Args:
        query_node: Query to be split into its child components. Its query_ast
                    will be replaced (but the original AST will not be modified) and its
                    child_query_connections will be modified.
        merged_schema_descriptor: The schema that the query AST contained in the input
                                  query_node targets.
        edge_to_stitch_fields: Mapping (type name, vertex field name) to
                               (source field name, sink field name) used in the @stitch directive
                               for each cross schema edge.
        name_assigner: Object used to generate and keep track of names of newly created
                       @output directive.

    Raises:
        - GraphQLValidationError if the query AST contained in the input query_node is invalid,
          for example, having an @output directive on a cross schema edge
        - SchemaStructureError if the merged_schema_descriptor provided appears to be invalid
          or inconsistent
    """
    type_info = TypeInfo(merged_schema_descriptor.schema)

    operation_definition = get_only_query_definition(query_node.query_ast, GraphQLValidationError)
    if not isinstance(operation_definition, OperationDefinitionNode):
        raise AssertionError(
            f"Expected operation_definition to be an OperationDefinitionNode, but it was of"
            f"type {type(operation_definition)}. This should be impossible."
        )

    type_info.enter(operation_definition)
    new_operation_definition = _split_query_ast_one_level_recursive(
        query_node, operation_definition, type_info, edge_to_stitch_fields, name_assigner
    )
    type_info.leave(operation_definition)

    if new_operation_definition is not operation_definition:
        query_node.query_ast = DocumentNode(definitions=[new_operation_definition])

    # Check resulting AST is valid
    validation_errors = validate(merged_schema_descriptor.schema, query_node.query_ast)
    if len(validation_errors) > 0:
        raise AssertionError(
            'The resulting split query "{}" is invalid, with the following error messages: {}'
            "".format(query_node.query_ast, validation_errors)
        )

    # Set schema id, check for consistency
    visitor = TypeInfoVisitor(
        type_info,
        SchemaIdSetterVisitor(
            type_info, query_node, merged_schema_descriptor.type_name_to_schema_id
        ),
    )
    visit(query_node.query_ast, visitor)

    if query_node.schema_id is None:
        raise AssertionError(
            'Unreachable code reached. The schema id of query piece "{}" has not been '
            "determined.".format(query_node.query_ast)
        )


def _split_query_ast_one_level_recursive(
    query_node: SubQueryNode,
    ast: AstType,
    type_info: TypeInfo,
    edge_to_stitch_fields: Dict[Tuple[str, str], Tuple[str, str]],
    name_assigner: IntermediateOutNameAssigner,
) -> AstType:
    """Return an AST node with which to replace the input AST in the selections that contain it.

    This function examines the selections of the input AST, and recursively calls either
    _split_query_ast_one_level_recursive or _split_query_ast_one_level_recursive_normal_fields
    depending on whether the selections contains a single InlineFragmentNode or a number of normal
    fields.

    Args:
        query_node: SubQueryNode, whose list of child query connections may be modified to
                    include new children.
        ast: The AST that we are trying to split into child components.
             It is not modified by this function.
        type_info: Used to get information about the types of fields while traversing the query AST.
        edge_to_stitch_fields: Mapping (type name, vertex field name) to
                               (source field name, sink field name) used in the @stitch directive
                               for each cross schema edge.
        name_assigner: Object used to generate and keep track of names of newly created
                       @output directives.

    Returns:
        The AST with which to replace the input AST in the selections that contain it.
    """
    if ast.selection_set is None:
        raise AssertionError("AST's selection_set cannot be None.")
    type_info.enter(ast.selection_set)
    selections = ast.selection_set.selections

    type_coercion = try_get_inline_fragment(selections)
    if type_coercion is not None:
        # Case 1: type coercion
        type_info.enter(type_coercion)
        new_type_coercion = _split_query_ast_one_level_recursive(
            query_node, type_coercion, type_info, edge_to_stitch_fields, name_assigner
        )
        type_info.leave(type_coercion)

        if new_type_coercion is type_coercion:
            new_selections: Sequence[SelectionNode] = selections
        else:
            new_selections = [new_type_coercion]
    else:
        # Case 2: normal fields
        new_selections = _split_query_ast_one_level_recursive_normal_fields(
            query_node, selections, type_info, edge_to_stitch_fields, name_assigner
        )
    type_info.leave(ast.selection_set)

    # Return input, or make copy
    if new_selections is not selections:
        new_ast = copy(ast)
        new_ast.selection_set = SelectionSetNode(selections=new_selections)
        return new_ast
    else:
        return ast


def _split_query_ast_one_level_recursive_normal_fields(
    query_node: SubQueryNode,
    selections: List[SelectionNode],
    type_info: TypeInfo,
    edge_to_stitch_fields: Dict[Tuple[str, str], Tuple[str, str]],
    name_assigner: IntermediateOutNameAssigner,
) -> Sequence[SelectionNode]:
    """One case of splitting query, selections contains a number of fields, no inline fragments.

    The input selections will be divided into three sets: property fields, intra-schema vertex
    fields, and cross-schema vertex fields.

    Each cross-schema vertex field will not be included in the output selections. The AST
    branch that each cross-schema vertex field leads to will be made into its own separate query
    AST. The parent and child property fields used in the stitch will be added to the parent and
    child ASTs, if not already present. @output directives will be added to these parent and
    child property fields, if not already present. @filter directives will not be added to
    child property fields in this step. This is because one may choose to rearrange and reroot
    the tree of SubQueryNodes to achieve an execution order with better performance. @filter
    directives should be added only once the tree's structure is fixed.

    _split_query_ast_one_level_recursive will be called recursive on each intra-schema vertex
    field.

    Args:
        query_node: Containing list of child query connections may be modified to
                    include new children.
        selections: Containing a number of property fields and vertex fields.
        type_info: Used to get information about the types of fields while traversing the query AST.
        edge_to_stitch_fields: Mapping (type name, vertex field name) to
                               (source field name, sink field name) used in the @stitch directive
                               for each cross schema edge.
        name_assigner: Used to generate and keep track of names of newly created @output directives.

    Returns:
        List of SelectionNodes to replace the list of selections in the SelectionSet one level
        above. All cross schema edges in the input list will be removed, and in their place,
        property fields added or modified. If no changes were made, the exact input list object
        will be returned.
    """
    parent_type = type_info.get_parent_type()
    if parent_type is None:
        raise AssertionError("parent_type cannot be None.")
    parent_type_name = parent_type.name

    made_changes = False

    # First, collect all property fields, but don't make any changes to them yet
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
                "The query may be invalid against the schema, causing TypeInfo to lose track "
                'of the types of fields. This occurs at the cross schema field "{}", while '
                'splitting the AST "{}"'.format(cross_schema_field, query_node.query_ast)
            )
        stitch_data_key = (parent_type_name, cross_schema_field.name.value)
        parent_field_name, child_field_name = edge_to_stitch_fields[stitch_data_key]
        _process_cross_schema_field(
            query_node,
            cross_schema_field,
            property_fields_map,
            child_type_name,
            parent_field_name,
            child_field_name,
            name_assigner,
        )
        made_changes = True  # Cross schema edges are removed from the output, causing changes
        type_info.leave(cross_schema_field)

    # Third, process intra schema edges by recursing on them
    new_intra_schema_fields: List[SelectionNode] = []
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
        new_selections: Sequence[SelectionNode] = _get_selections_from_property_and_vertex_fields(
            property_fields_map, new_intra_schema_fields
        )
        return new_selections
    else:
        return selections


def _process_cross_schema_field(
    query_node: SubQueryNode,
    cross_schema_field: FieldNode,
    # OrderedDict is unsubscriptable (pylint E1136)
    property_fields_map: "OrderedDict[str, SelectionNode]",
    child_type_name: str,
    parent_field_name: str,
    child_field_name: str,
    name_assigner: IntermediateOutNameAssigner,
) -> None:
    """Construct child SubQueryNode from branch, update record of property fields.

    Args:
        query_node: The "parent" query node. The new child SubQueryNode will be added as a child
                    of this node.
        cross_schema_field: Representing an edge crossing schemas. It is not modified
                            by this function. The branch that this edge leads to will be used
                            to create a new SubQueryNode.
        property_fields_map: Mapping the name of each property field to its representation.
                             It is modified by this function. If no property field of the specified
                             name already exists, one will be created and added. If one already
                             exists, it will be replaced by a new FieldNode. The new FieldNode
                             will contains directives from the existing FieldNode and the cross
                             schema vertex fields, as well as a generated @output directive if one
                             doesn't yet exist.
        child_type_name: Name of the type to which this cross schema field leads.
        parent_field_name: Name of the property field that the parent (source of the cross
                           schema edge) stitches on.
        child_field_name: Name of the property field that the child (the type that this
                          cross schema field leads to) stitches on.
        name_assigner: Object used to generate and keep track of names of newly created
                       @output directives.
    """
    existing_property_field = property_fields_map.get(parent_field_name, None)
    # Get property field inheriting the right directives
    parent_property_field = _get_property_field(
        existing_property_field, parent_field_name, cross_schema_field.directives
    )
    # Add @output if needed, record out_name
    parent_property_field, parent_output_name = _get_out_name_optionally_add_output(
        parent_property_field, name_assigner
    )
    # Create child query node around ast
    child_query_node, child_output_name = _get_child_query_node_and_out_name(
        cross_schema_field, child_type_name, child_field_name, name_assigner
    )
    # Create and add QueryConnections
    _add_query_connections(query_node, child_query_node, parent_output_name, child_output_name)
    # Add or replace the new property field
    property_fields_map[parent_property_field.name.value] = parent_property_field


def _split_selections_property_and_vertex(
    selections: Sequence[Union[SelectionNode]],
    # OrderedDict is unsubscriptable (pylint E1136)
) -> Tuple["OrderedDict[str, SelectionNode]", List[SelectionNode]]:
    """Split input selections into property fields and vertex fields/type coercions.

    Args:
        selections: Selections to be split into property fields and vertex fields/type coercions.
                    Not modified by this function.

    Returns:
        Tuple containing:
            - Map from the names of property fields to their representations.
            - List of vertex fields.

    Raises:
        GraphQLValidationError if some property field is repeated
    """
    if selections is None:
        raise AssertionError("Input selections is None, rather than a list.")
    property_fields_map: "OrderedDict[str, SelectionNode]" = OrderedDict()
    vertex_fields: List[SelectionNode] = []
    for selection in selections:
        if not isinstance(selection, FieldNode):
            raise AssertionError(
                f"selection is of type {type(selection)}, but was expected to be of type "
                "FieldNode."
            )
        if is_property_field_ast(selection):
            name = selection.name.value
            if name in property_fields_map:
                raise GraphQLValidationError(
                    'The field named "{}" occurs more than once in the selection {}.'.format(
                        name, selections
                    )
                )
            property_fields_map[name] = selection
        else:
            vertex_fields.append(selection)
    return property_fields_map, vertex_fields


def _split_vertex_fields_intra_and_cross_schema(
    vertex_fields: List[SelectionNode],
    parent_type_name: str,
    edge_to_stitch_fields: Dict[Tuple[str, str], Tuple[str, str]],
) -> Tuple[List[FieldNode], List[FieldNode]]:
    """Split input list of vertex fields into intra-schema and cross-schema fields.

    Args:
        vertex_fields: Vertex fields to split into intra- and cross-schema fields.
                       Not modified by this function.
        parent_type_name: Name of the type that has the input list of vertex fields as fields.
        edge_to_stitch_fields: Mapping (type name, vertex field name) to
                               (source field name, sink field name) used in the @stitch directive
                               for each cross schema edge.

    Returns:
        Tuple containing:
            - List of intra schema fields.
            - List of cross schema fields.
    """
    intra_schema_fields = []
    cross_schema_fields = []
    for vertex_field in vertex_fields:
        if isinstance(vertex_field, FieldNode):
            stitch_data_key = (parent_type_name, vertex_field.name.value)
            if stitch_data_key in edge_to_stitch_fields:
                cross_schema_fields.append(vertex_field)
            else:
                intra_schema_fields.append(vertex_field)
        else:
            raise AssertionError("Input vertex field {} is not a Field".format(vertex_field))
    return intra_schema_fields, cross_schema_fields


def _get_selections_from_property_and_vertex_fields(
    # OrderedDict is unsubscriptable (pylint E1136)
    property_fields_map: "OrderedDict[str, SelectionNode]",
    vertex_fields: List[SelectionNode],
) -> List[SelectionNode]:
    """Combine property fields and vertex fields into a list of selections.

    Args:
        property_fields_map: Mapping name of field to their representation.
                             Not modified by this function.
        vertex_fields: Vertex fields to be combined. Not modified by this function

    Returns:
        All property fields then all vertex fields, in order.
    """
    selections = list(six.itervalues(property_fields_map))
    selections.extend(vertex_fields)
    return selections


def _get_child_query_node_and_out_name(
    ast: Union[FieldNode, InlineFragmentNode],
    child_type_name: str,
    child_field_name: str,
    name_assigner: IntermediateOutNameAssigner,
) -> Tuple[SubQueryNode, str]:
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

    The output child_node will be wrapped around this new DocumentNode. In addition, if no field
    of child_field_name currently exists, such a field will be added. If there is no @output
    directive on this field, a new @output directive will be added.

    Args:
        ast: Representing the AST that we're using to build a child node.
             It is not modified by this function.
        child_type_name: Name of the type to which this cross schema field leads.
        child_field_name: str. If no field of this name currently exists as a part of the root
                          selections of the input AST, a new field will be created in the AST
                          contained in the output child query node
        name_assigner: Object used to generate and keep track of names of newly created
                       @output directives.

    Returns:
        Tuple containing:
            - The child sub query node wrapping around the input AST.
            - The out_name of the @output directive uniquely identifying the field used for
              stitching in this sub query node.
    """
    # Get type and selections of child AST, taking into account type coercions
    child_selection_set = ast.selection_set
    if child_selection_set is None:
        raise AssertionError("Invalid AST. child_selection_set cannot be None.")
    type_coercion = try_get_inline_fragment(child_selection_set.selections)
    if type_coercion is not None:
        child_type_name = type_coercion.type_condition.name.value
        child_selection_set = type_coercion.selection_set
    child_selections: List[SelectionNode] = []
    for child_selection in child_selection_set.selections:
        if not isinstance(child_selection, FieldNode):
            raise AssertionError(
                "Expected child_selection to be of type FieldNode, but was of "
                f"type {type(child_selection)}."
            )
        child_selections.append(child_selection)

    # Get existing field with name in child
    existing_child_property_field = try_get_ast_by_name_and_type(
        child_selections, child_field_name, FieldNode
    )
    # Validate that existing_child_property_field is None or FieldNode.
    # It should be impossible for this to *not* be the case, but check so that mypy is happy.
    if not (
        existing_child_property_field is None
        or isinstance(existing_child_property_field, FieldNode)
    ):
        raise AssertionError(
            "Unreachable code reached! existing_child_property_field should be None or of type "
            f"FieldNode, but was type {type(existing_child_property_field)}."
        )
    child_property_field = _get_property_field(
        existing_child_property_field, child_field_name, None
    )
    # Add @output if needed, record out_name
    child_property_field, child_output_name = _get_out_name_optionally_add_output(
        child_property_field, name_assigner
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
    # required to have a corresponding root vertex field), then this query will be invalid.
    child_query_ast = _get_query_document(child_type_name, child_selections)
    child_query_node = SubQueryNode(child_query_ast)

    return child_query_node, child_output_name


def _get_property_field(
    existing_field: Optional[SelectionNode],
    field_name: str,
    directives_from_edge: Optional[List[DirectiveNode]],
) -> FieldNode:
    """Return a FieldNode with field_name, sharing directives with any such existing FieldNode.

    Any valid directives in directives_on_edge will be transferred over to the new FieldNode.
    If there is an existing FieldNode in selection with field_name, the returned new FieldNode
    will also contain all directives of the existing field with that name.

    Args:
        existing_field: None or a FieldNode with field_name. The directives of this field will
                        carry output to the output field.
        field_name: str, the name of the output field.
        directives_from_edge: None or list of the directives of a vertex field. The output
                              field will contain all @filter and any @optional directives
                              from this list.

    Returns:
        FieldNode, with field_name as its name, containing directives from any field in the
        input selections with the same name and directives from the input list of directives.
    """
    new_field_directives: List[DirectiveNode] = []

    # Transfer directives from existing field of the same name
    if existing_field is not None:
        if not isinstance(existing_field, FieldNode):
            raise AssertionError(
                f"Expected existing_field to be a FieldNode, but was a {type(existing_field)}."
            )
        # Existing field, add all its directives
        directives_from_existing_field = existing_field.directives
        if directives_from_existing_field is not None:
            new_field_directives.extend(directives_from_existing_field)
    # Transfer directives from edge
    if directives_from_edge is not None:
        for directive in directives_from_edge:
            if directive.name.value == OutputDirective.name:  # output illegal on vertex field
                raise GraphQLValidationError(
                    'Directive "{}" is not allowed on a vertex field, as @output directives '
                    "can only exist on property fields.".format(directive)
                )
            elif directive.name.value == OptionalDirective.name:
                if (
                    try_get_ast_by_name_and_type(
                        new_field_directives, OptionalDirective.name, DirectiveNode
                    )
                    is None
                ):
                    # New optional directive
                    new_field_directives.append(directive)
            elif directive.name.value == FilterDirective.name:
                new_field_directives.append(directive)
            else:
                raise AssertionError(
                    'Unreachable code reached. Directive "{}" is of an unsupported type, and '
                    "was not caught in a prior validation step.".format(directive)
                )

    new_field = FieldNode(
        name=NameNode(value=field_name),
        directives=new_field_directives,
    )
    return new_field


def _get_out_name_optionally_add_output(
    field: FieldNode, name_assigner: IntermediateOutNameAssigner
) -> Tuple[FieldNode, str]:
    """Return out_name of @output on field, creating new @output if needed.

    Args:
        field: FieldNode that may need an added an @output directive.
        name_assigner: Object used to generate and keep track of names of newly created
                       @output directives.

    Returns:
        Tuple containing:
            - Either the original field or a new FieldNode that has the same properties as the
              original field, but with an added @output directive.
            - Name of the out_name of the @output directive, either pre-existing or newly generated.
    """
    # Check for existing directive
    output_directive = try_get_ast_by_name_and_type(
        field.directives, OutputDirective.name, DirectiveNode
    )
    if output_directive is None:
        # Create and add new directive to field
        out_name = name_assigner.assign_and_return_out_name()
        output_directive = _get_output_directive(out_name)
        if field.directives is None:
            new_directives = []
        else:
            new_directives = list(field.directives)
        new_directives.append(output_directive)
        new_field = FieldNode(
            alias=field.alias,
            name=field.name,
            arguments=field.arguments,
            selection_set=field.selection_set,
            directives=new_directives,
            loc=field.loc,
        )
        return new_field, out_name
    else:
        if not isinstance(output_directive, DirectiveNode):
            raise AssertionError(
                "output_directive needs to be type DirectiveNode, but was type "
                f"{type(output_directive)}. This should be impossible and is a bug."
            )
        argument_value = output_directive.arguments[0].value
        if not isinstance(argument_value, ScalarConstantValueNodes) or isinstance(
            argument_value, BooleanValueNode
        ):
            raise AssertionError(
                "argument_value must be of type ScalarConstantValueNodes, but "
                f"was of type {type(argument_value)}."
            )
        return field, argument_value.value  # Location of value of out_name


def _get_output_directive(out_name: str) -> DirectiveNode:
    """Return a Directive representing an @output with the input out_name."""
    return DirectiveNode(
        name=NameNode(value=OutputDirective.name),
        arguments=[
            ArgumentNode(
                name=NameNode(value="out_name"),
                value=StringValueNode(value=out_name),
            ),
        ],
    )


def _get_query_document(
    root_vertex_field_name: str, root_selections: Sequence[SelectionNode]
) -> DocumentNode:
    """Return a DocumentNode representing a query with the specified name and selections."""
    return DocumentNode(
        definitions=[
            OperationDefinitionNode(
                operation=OperationType.QUERY,
                selection_set=SelectionSetNode(
                    selections=[
                        FieldNode(
                            name=NameNode(value=root_vertex_field_name),
                            selection_set=SelectionSetNode(
                                selections=root_selections,
                            ),
                            directives=[],
                        )
                    ]
                ),
            )
        ]
    )


def _add_query_connections(
    parent_query_node: SubQueryNode,
    child_query_node: SubQueryNode,
    parent_field_out_name: str,
    child_field_out_name: str,
) -> None:
    """Modify parent and child SubQueryNodes by adding QueryConnections between them."""
    if child_query_node.parent_query_connection is not None:
        raise AssertionError(
            "The input child query node already has a parent connection, {}".format(
                child_query_node.parent_query_connection
            )
        )
    if any(
        query_connection_from_parent.sink_query_node is child_query_node
        for query_connection_from_parent in parent_query_node.child_query_connections
    ):
        raise AssertionError(
            "The input parent query node already has the child query node in a child query "
            "connection."
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
