# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import copy

from graphql.language import ast as ast_types
from graphql.language.visitor import TypeInfoVisitor, Visitor, visit
from graphql.utils.type_info import TypeInfo
from graphql.validation import validate

from ..ast_manipulation import get_only_query_definition
from ..compiler.helpers import strip_non_null_and_list_from_type
from ..exceptions import GraphQLValidationError
from .utils import SchemaStructureError, try_get_ast


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


def split_query(query_ast, merged_schema_descriptor):
    """Split input query AST into a tree of SubQueryNodes targeting each individual schema.

    Property fields used in the stitch will be added if not already present. @output directives
    will be added on property fields if not already present. All output names of @output
    directives will be unique, and thus used to identify fields later down the line for adding
    @filter directives.

    Args:
        query_ast: Document, representing a GraphQL query to split
        merged_schema_descriptor: MergedSchemaDescriptor namedtuple, containing:
                                  schema_ast: Document representing the merged schema
                                  schema: GraphQLSchema representing the merged schema
                                  type_name_to_schema_id: Dict[str, str], mapping name of each
                                                          type to the id of the schema it came
                                                          from

    Returns:
        Tuple[SubQueryNode, frozenset[str]]. The first element is the root of the tree of
        QueryNodes. Each node contains an AST representing a part of the overall query,
        targeting aspecific schema. The second element is the set of all intermediate output
        names that are to be removed at the end

    Raises:
        - GraphQLValidationError if the query doesn't validate against the schema, contains
          unsupported directives, or some property field occurs after a vertex field in some
          selection
        - SchemaStructureError if the input merged_schema_descriptor appears to be invalid
          or inconsistent
    """
    _check_query_is_valid_to_split(merged_schema_descriptor.schema, query_ast)

    # If schema directives are correctly represented in the schema object, type_info is all
    # that's needed to detect and address stitching fields. However, before this issue is
    # fixed, it's necessary to use additional information from pre-processing the schema AST
    edge_to_stitch_fields = _get_edge_to_stitch_fields(merged_schema_descriptor)
    intermediate_out_name_assigner = IntermediateOutNameAssigner()

    root_query_node = SubQueryNode(query_ast)
    query_nodes_to_split = [root_query_node]

    # Construct full tree of SubQueryNodes in a dfs pattern
    while len(query_nodes_to_split) > 0:
        current_node_to_split = query_nodes_to_split.pop()

        _split_query_one_level(current_node_to_split, merged_schema_descriptor,
                               edge_to_stitch_fields, intermediate_out_name_assigner)

        query_nodes_to_split.extend(
            child_query_connection.sink_query_node
            for child_query_connection in current_node_to_split.child_query_connections
        )

    return root_query_node, frozenset(intermediate_out_name_assigner.intermediate_output_names)


def _split_query_one_level(query_node, merged_schema_descriptor, edge_to_stitch_fields,
                           intermediate_out_name_assigner):
    """Split the query node, creating children out of all branches across cross schema edges.

    The input query_node will be modified. Its query_ast will be replaced by a new AST with
    branches leading out of cross schema edges removed, and new property fields and @output
    directives added as necessary. Its child_query_connections will be modified by tacking
    on SubQueryNodes created from these cut-off branches.

    Args:
        query_node: SubQueryNode that we're splitting into its child components. Its query_ast
                    will be replaced (but the original AST will not be modified) and its
                    child_query_connections will be modified
        merged_schema_descriptor: MergedSchemaDescriptor, the schema that the query AST contained
                                  in the input query_node targets
        edge_to_stitch_fields: Dict[Tuple(str, str), Tuple(str, str)], mapping
                               (type name, edge field name) to
                               (source field name, sink field name) used in the @stitch directive
                               for each cross schema edge
        intermediate_out_name_assigner: IntermediateOutNameAssigner, object used to generate
                                        and keep track of names of newly created @output
                                        directives

    Raises:
        - GraphQLValidationError if the query AST contained in the input query_node is invalid,
          for example, having an @output directive on a cross schema edge
        - SchemaStructureError if the merged_schema_descriptor provided appears to be invalid
          or inconsistent
    """
    type_info = TypeInfo(merged_schema_descriptor.schema)

    operation_definition = get_only_query_definition(query_node.query_ast, GraphQLValidationError)

    type_info.enter(operation_definition)
    new_operation_definition = _split_query_ast_one_level_recursive(
        query_node, operation_definition, [operation_definition], type_info,
        edge_to_stitch_fields, intermediate_out_name_assigner
    )
    type_info.leave(operation_definition)

    query_node.query_ast = ast_types.Document(
        definitions=[new_operation_definition]
    )
    # Set schema id, check for consistency
    visitor = TypeInfoVisitor(
        type_info,
        SchemaIdSetterVisitor(
            type_info, query_node, merged_schema_descriptor.type_name_to_schema_id
        )
    )
    visit(query_node.query_ast, visitor)

    if query_node.schema_id is None:
        raise AssertionError(
            u'Unreachable code reached. The schema id of query piece "{}" has not been '
            u'determined.'.format(query_node.query_ast)
        )


def _split_query_ast_one_level_recursive(
    query_node, ast, parent_selections, type_info, edge_to_stitch_fields,
    intermediate_out_name_assigner
):
    """Return a Node to replace the input AST by in the selections one level above.

    - If the input AST starts with a cross schema edge, the output will be a Field object
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
                           fields) in the level of selections that contains the input ast. If
                           is not modified by this function
        type_info: TypeInfo, used to get information about the types of fields while traversing
                   the query ast
        edge_to_stitch_fields: Dict[Tuple(str, str), Tuple(str, str)], mapping
                               (type name, edge field name) to
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
    if isinstance(ast, ast_types.Field):
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
        # NOTE: By the time we reach any cross schema edge fields, new_selections contains all
        # property fields, including any new property fields created by previous cross schema
        # edge fields, and therefore will not create duplicate new fields
        new_selection = _split_query_ast_one_level_recursive(
            query_node, selection, new_selections, type_info, edge_to_stitch_fields,
            intermediate_out_name_assigner
        )

        if new_selection is not selection:
            made_changes = True
            if _is_property_field(new_selection):
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
        ast_copy.selection_set = ast_types.SelectionSet(selections=new_selections)
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
    where out_Human is a vertex edge going to type Human, the resulting document will be
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
    child_query_ast = _get_query_document(child_type_name, child_selections)
    child_query_node = SubQueryNode(child_query_ast)

    return child_query_node, child_output_name


def _get_property_field(selections, field_name, directives_from_edge):
    """Return a Field object with field_name, sharing directives with any such existing field.

    Any valid directives in directives_on_edge will be transferred over to the new field.
    If there is an existing Field in parent_selection with field_name, the returned new Field
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
    new_field = ast_types.Field(
        name=ast_types.Name(value=field_name),
        directives=[],
    )

    # Check parent_selection for existing field of given name
    parent_field = try_get_ast(selections, field_name, ast_types.Field)
    if parent_field is not None:
        # Existing field, add all its directives
        directives_from_existing_field = parent_field.directives
        if directives_from_existing_field is not None:
            new_field.directives.extend(directives_from_existing_field)

    # Transfer directives from edge
    if directives_from_edge is not None:
        for directive in directives_from_edge:
            if directive.name.value == u'output':  # output is illegal on edge field
                raise GraphQLValidationError(
                    u'Directive "{}" is not allowed on an edge field, as @output directives '
                    u'can only exist on property fields.'.format(directive)
                )
            elif directive.name.value == u'optional':
                if try_get_ast(new_field.directives, u'optional', ast_types.Directive) is None:
                    # New optional directive
                    new_field.directives.append(directive)
            elif directive.name.value == u'filter':
                new_field.directives.append(directive)
            elif directive.name.value == u'stitch':
                continue
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
        isinstance(child_selection_set.selections[0], ast_types.InlineFragment)
    ):
        type_coercion_inline_fragment = child_selection_set.selections[0]
        child_type_name = type_coercion_inline_fragment.type_condition.name.value
        child_selection_set = type_coercion_inline_fragment.selection_set

    return child_type_name, child_selection_set.selections


def _is_property_field(selection):
    """Return True if selection is a property field, False if a vertex field or type coercion.

    Args:
        selection: an element occuring inside a SelectionSet, which should be of type Field or
                   InlineFragment

    Returns:
        True if the selection is a property field, False if it's a vertex field or type coercion
    """
    if isinstance(selection, ast_types.InlineFragment):
        return False
    if isinstance(selection, ast_types.Field):
        if (
            selection.selection_set is None or
            selection.selection_set.selections is None or
            selection.selection_set.selections == []
        ):
            return True
        else:
            return False
    else:
        raise AssertionError(
            u'Input selection "{}" is not of type Field or InlineFragment.'.format(selection)
        )


def _get_edge_to_stitch_fields(merged_schema_descriptor):
    """Get a map from type/field of each cross schema edge, to the fields that the edge stitches.

    This is necessary only because graphql currently doesn't process schema directives correctly.
    Once schema directives are correctly added to GraphQLSchema objects, this part may be
    removed as directives on a schema field can be directly accessed.

    Args:
        merged_schema_descriptor: MergedSchemaDescriptor namedtuple, containing a schema ast
                                  and a map from names of types to their schema ids

    Returns:
        Dict[Tuple(str, str), Tuple(str, str)], mapping (type name, edge field name) to
        (source field name, sink field name) used in the @stitch directive, for each cross
        schema edge
    """
    edge_to_stitch_fields = {}
    for type_definition in merged_schema_descriptor.schema_ast.definitions:
        if isinstance(type_definition, (
            ast_types.ObjectTypeDefinition, ast_types.InterfaceTypeDefinition
        )):
            for field_definition in type_definition.fields:
                stitch_directive = try_get_ast(
                    field_definition.directives, u'stitch', ast_types.Directive
                )
                if stitch_directive is not None:
                    source_field_name = stitch_directive.arguments[0].value.value
                    sink_field_name = stitch_directive.arguments[1].value.value
                    edge = (type_definition.name.value, field_definition.name.value)
                    edge_to_stitch_fields[edge] = (source_field_name, sink_field_name)

    return edge_to_stitch_fields


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
            isinstance(selection, ast_types.Field) and
            selection.name.value == new_field.name.value
        ):
            selections[index] = new_field
            return selections
        if not _is_property_field(selection):
            selections.insert(index, new_field)
            return selections
    # No vertex fields and no property fields of the same name
    selections.append(new_field)
    return selections


def _add_query_connections(parent_query_node, child_query_node, parent_field_out_name,
                           child_field_out_name):
    """Modify parent and child SubQueryNodes by adding QueryConnections between them."""
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


def _get_query_document(root_vertex_field_name, root_selections):
    """Return a Document representing a query with the specified name and selections."""
    return ast_types.Document(
        definitions=[
            ast_types.OperationDefinition(
                operation='query',
                selection_set=ast_types.SelectionSet(
                    selections=[
                        ast_types.Field(
                            name=ast_types.Name(value=root_vertex_field_name),
                            # NOTE: if the root_vertex_field_name does not actually exist
                            # as a root field (not all types are required to have a
                            # corresponding root vertex field), then this query will be
                            # invalid
                            # TODO: warn the user?
                            selection_set=ast_types.SelectionSet(
                                selections=root_selections,
                            ),
                            directives=[],
                        )
                    ]
                )
            )
        ]
    )


def _get_output_directive(out_name):
    """Return a Directive representing an @output with the input out_name."""
    return ast_types.Directive(
        name=ast_types.Name(value=u'output'),
        arguments=[
            ast_types.Argument(
                name=ast_types.Name(value=u'out_name'),
                value=ast_types.StringValue(value=out_name),
            ),
        ],
    )


def _get_out_name_optionally_add_output(field, intermediate_out_name_assigner):
    """Return out_name of @output on field, creating new @output if needed.

    Args:
        field: Field object, whose directives we may modify by adding an @output directive

    Returns:
        str, name of the out_name of the @output directive, either pre-existing or newly
        generated
    """
    # Check for existing directive
    output_directive = try_get_ast(field.directives, u'output', ast_types.Directive)
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


def _check_query_is_valid_to_split(schema, query_ast):
    """Check the query is valid for splitting.

    In particular, ensure that the query validates against the schema, does not contain
    unsupported directives, and that in each selection, all property fields occur before all
    vertex fields.

    Args:
        schema: GraphQLSchema object
        query_ast: Document

    Raises:
        GraphQLValidationError if the query doesn't validate against the schema, contains
        unsupported directives, or some property field occurs after a vertex field in some
        selection
    """
    # Check builtin errors
    built_in_validation_errors = validate(schema, query_ast)
    if len(built_in_validation_errors) > 0:
        raise GraphQLValidationError(
            u'AST does not validate: {}'.format(built_in_validation_errors)
        )
    # Check no bad directives and fields are in order
    visitor = CheckQueryIsValidToSplitVisitor()
    visit(query_ast, visitor)


class CheckQueryIsValidToSplitVisitor(Visitor):
    """Check the query only has supported directives, and its fields are correctly ordered."""
    # This is very restrictive for now. Other cases (e.g. tags not crossing boundaries) are
    # also ok, but temporarily not allowed
    supported_directives = frozenset(('filter', 'output', 'optional', 'stitch'))

    def enter_Directive(self, node, *args):
        """Check that the directive is supported."""
        if node.name.value not in self.supported_directives:
            raise GraphQLValidationError(
                u'Directive "{}" is not yet supported, only "{}" are currently '
                u'supported.'.format(node.name.value, self.supported_directives)
            )

    def enter_SelectionSet(self, node, *args):
        """Check property fields occur before vertex fields and type coercions in selection."""
        past_property_fields = False  # Whether we're seen a vertex field
        for field in node.selections:
            if _is_property_field(field):
                if past_property_fields:
                    raise GraphQLValidationError(
                        u'In the selections {}, the property field {} occurs after a vertex '
                        u'field or a type coercion statement, which is not allowed, as all '
                        u'property fields must appear before all vertex fields.'.format(
                            node.selections, field
                        )
                    )
            else:
                past_property_fields = True


class SchemaIdSetterVisitor(Visitor):
    def __init__(self, type_info, query_node, type_name_to_schema_id):
        """Create a visitor for setting the schema_id of the input query node.

        Args:
            type_info: TypeInfo, used to keep track of types of fields while traversing the AST
            query_node: SubQueryNode, whose schema_id will be modified
            type_name_to_schema_id: Dict[str, str], mapping the names of types to the id of the
                                    schema that they came from
        """
        self.type_info = type_info
        self.query_node = query_node
        self.type_name_to_schema_id = type_name_to_schema_id

    def enter_Field(self, *args):
        """Check the schema of the type that the field leads to"""
        child_type_name = strip_non_null_and_list_from_type(self.type_info.get_type()).name
        self._check_or_set_schema_id(child_type_name)

    def enter_InlineFragment(self, node, *args):
        """Check the schema of the coerced type."""
        self._check_or_set_schema_id(node.type_condition.name.value)

    def _check_or_set_schema_id(self, type_name):
        """Set the schema id of the root node if not yet set, otherwise check schema ids agree.

        Args:
            type_name: str, name of the type whose schema id we're comparing against the
                       previously recorded schema id
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
                    u'The provided merged schema descriptor may be invalid. Perhaps '
                    u'some edge that does not have a @stitch directive crosses schemas. As '
                    u'a result, query piece "{}" appears to contain types from more than '
                    u'one schema. Type "{}" belongs to schema "{}", while some other type '
                    u'belongs to schema "{}".'.format(
                        self.query_node.query_ast, type_name, current_type_schema_id,
                        prior_type_schema_id
                    )
                )
