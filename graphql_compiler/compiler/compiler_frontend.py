# Copyright 2017-present Kensho Technologies, LLC.
"""Front-end for GraphQL to database queries compiler.

High-level overview of the GraphQL ingestion process that outputs the compiler's
internal representation (IR) via the graphql_to_ir() function:
    - The function receives a GraphQL string and a GraphQL schema.
      How the schema is constructed is beyond the scope of this package.
    - It uses the graphql library to parse the GraphQL string into
      an abstract syntax tree representation (AST).
    - It validates the GraphQL string using the schema.
    - Finally, it converts the validated GraphQL string into an internal representation (IR):
      a list of BasicBlock (blocks.py) objects, which may further contain
      Expression (expressions.py) objects.

To get from GraphQL AST to IR, we follow the following pattern:
    step 0. preprocessing:  (see _compile_ast_node_to_ir())
        - read any directives at the current AST node;
        - read the inline fragment at the current AST node, if one exists;
        - read any child fields of the current AST node, splitting them into two groups:
          property fields and vertex fields; all property fields must precede the vertex fields
          for the AST to be valid;

    step 1. apply all @filter directives that apply to the current field
            (see _compile_ast_node_to_ir() and directive_helpers.get_local_filter_directives())

    We now proceed with one of three cases (P, V and F), depending on whether
    the current AST node is a property AST node, vertex AST node, or inline fragment, respectively.
    The root AST node is always a vertex AST node.

    *** P-steps ***
    step P-2. Process @output directives.
    ***************

    *** V-steps ***
    step V-2. Process @tag directives at all property field children of the current AST node.

    step V-3. Recurse into any property field children of the current AST node
              (property fields cannot have property fields of their own, see _compile_vertex_ast()).

    step V-4. Property field processing complete:  (see _compile_vertex_ast())
        - mark the current location in the query, since all @filter directives that apply to the
          current field have already been processed;
        - process the output_source directive, if it exists

    step V-5. Recurse into any vertex field children of the current AST node:
              (see _compile_vertex_ast())
        - before recursing into each vertex:
          - process any @optional and @fold directives present on the child AST node;
          - process any @output within a @fold context,
            and prevent further traversal if one is present;
        - after returning from each vertex:
          - return to the marked query location using the appropriate manner,
            depending on whether @optional was present on the child or not;
          - if the visited vertex had a @fold or @optional directive,
            undo the processing performed at previous steps;
    ***************

    *** F-steps ***
    step F-2. Emit a type coercion block if appropriate, then recurse into the fragment's selection.
    ***************
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

from graphql import (
    DocumentNode,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLType,
    GraphQLUnionType,
)
from graphql.language.ast import FieldNode, InlineFragmentNode

from . import blocks, expressions
from ..ast_manipulation import (
    get_ast_field_name,
    get_only_query_definition,
    get_only_selection_from_ast,
    safe_parse_graphql,
)
from ..exceptions import GraphQLCompilationError, GraphQLValidationError
from ..global_utils import is_same_type
from ..schema import COUNT_META_FIELD_NAME, TypeEquivalenceHintsType, is_vertex_field_name
from ..typedefs import QueryArgumentGraphQLType
from .compiler_entities import BasicBlock
from .context_helpers import (
    get_context_fold_info,
    get_optional_scope_or_none,
    has_encountered_output_source,
    has_fold_count_filter,
    is_in_fold_innermost_scope,
    is_in_fold_scope,
    is_in_optional_scope,
    set_fold_count_filter,
    set_fold_innermost_scope,
    set_fold_scope_data,
    set_optional_scope_data,
    set_output_source_data,
    unmark_context_fold_scope,
    unmark_fold_count_filter,
    unmark_fold_innermost_scope,
    unmark_optional_scope,
    validate_context_for_visiting_vertex_field,
)
from .directive_helpers import (
    get_local_filter_directives,
    get_unique_directives,
    validate_property_directives,
    validate_root_vertex_directives,
    validate_vertex_directives,
    validate_vertex_field_directive_in_context,
    validate_vertex_field_directive_interactions,
)
from .filters import process_filter_directive
from .helpers import (
    FoldScopeLocation,
    Location,
    get_edge_direction_and_name,
    get_field_type_from_schema,
    get_parameter_name,
    get_uniquely_named_objects_by_name,
    get_vertex_field_type,
    invert_dict,
    is_tagged_parameter,
    strip_non_null_from_type,
    validate_output_name,
    validate_safe_string,
)
from .metadata import LocationInfo, OutputInfo, QueryMetadataTable, RecurseInfo, TagInfo
from .validation import validate_schema_and_query_ast


@dataclass(init=True, repr=True, eq=False, frozen=True)
class OutputMetadata:
    """Metadata about a query's outputs."""

    # The type of the output value.
    type: GraphQLType

    # Whether the output is part of an optional traversal, which would allow a value of null.
    optional: bool

    # Whether the output is within a fold scope. Note that if the output is within a fold scope,
    # the `type` is expected to be a GraphQLList unless the output field is an _x_count,
    # in which case the type must be GraphQLInt.
    folded: bool

    def __eq__(self, other):
        """Check another OutputMetadata object for equality against this one."""
        # Unfortunately, GraphQL types don't have an equality operator defined,
        # and instead have this "is_same_type" function. Hence, we have to override equality here.
        return (
            is_same_type(self.type, other.type)
            and self.optional == other.optional
            and self.folded == other.folded
        )

    def __ne__(self, other):
        """Check another OutputMetadata object for non-equality against this one."""
        return not self.__eq__(other)


@dataclass(frozen=True)
class IrAndMetadata:
    """Internal representation (IR) and metadata for a particular schema and query combination."""

    # List of basic block objects describing the query.
    ir_blocks: List[BasicBlock]

    # Mapping of expected input parameters -> inferred GraphQL type.
    input_metadata: Dict[str, QueryArgumentGraphQLType]

    # Mapping output name -> output metadata.
    output_metadata: Dict[str, OutputMetadata]

    # Describing the location metadata.
    query_metadata_table: QueryMetadataTable


def _get_fields(ast):
    """Return a list of vertex fields, and a list of property fields, for the given AST node.

    Also verifies that all property fields for the AST node appear before all vertex fields,
    raising GraphQLCompilationError if that is not the case.

    Args:
        ast: GraphQL AST node, obtained from the graphql library

    Returns:
        tuple of two lists
            - the first list contains ASTs for vertex fields
            - the second list contains ASTs for property fields
    """
    if not ast.selection_set:
        # There are no child fields.
        return [], []

    property_fields = []
    vertex_fields = []
    seen_field_names = set()
    switched_to_vertices = False  # Ensures that all property fields are before all vertex fields.
    for field_ast in ast.selection_set.selections:
        if not isinstance(field_ast, FieldNode):
            # We are getting Fields only, ignore everything else.
            continue

        name = get_ast_field_name(field_ast)
        seen_already = name in seen_field_names

        # Vertex fields start with 'out_' or 'in_', denoting the edge direction to that vertex.
        if is_vertex_field_name(name):
            if seen_already:
                raise GraphQLCompilationError("Encountered repeated vertex field: {}.".format(name))
            switched_to_vertices = True
            vertex_fields.append(field_ast)
        else:
            if seen_already:
                # If we ever allow repeated field names,
                # then we have to change the Location naming scheme to reflect the repetitions
                # and disambiguate between Recurse and Traverse visits to a Location.
                raise GraphQLCompilationError(
                    "Encountered repeated property field: {}. If you "
                    "are attempting to specify multiple directives on a "
                    "single property field, one way to do so is to "
                    "place all of them adjacent to the property field "
                    "as follows: propertyField @directive1 @directive2 "
                    "...".format(name)
                )
            if switched_to_vertices:
                raise GraphQLCompilationError(
                    "Encountered property field {} after vertex fields!".format(name)
                )
            property_fields.append(field_ast)

        seen_field_names.add(name)

    return vertex_fields, property_fields


def _get_inline_fragment(ast):
    """Return the inline fragment at the current AST node, or None if no fragment exists."""
    if not ast.selection_set:
        # There is nothing selected here, so no fragment.
        return None

    fragments = [
        ast_node
        for ast_node in ast.selection_set.selections
        if isinstance(ast_node, InlineFragmentNode)
    ]

    if not fragments:
        return None

    if len(fragments) > 1:
        raise GraphQLCompilationError(
            "Cannot compile GraphQL with more than one fragment in a given selection set."
        )

    return fragments[0]


def _mark_location(location):
    """Return a MarkLocation basic block that marks the present location in the query."""
    return blocks.MarkLocation(location)


def _process_output_source_directive(
    schema, current_schema_type, ast, location, context, local_unique_directives
):
    """Process the output_source directive, modifying the context as appropriate.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library
        location: Location object representing the current location in the query
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        local_unique_directives: dict, directive name string -> directive object, containing
                                 unique directives present on the current AST node *only*

    Returns:
        an OutputSource block, if one should be emitted, or None otherwise
    """
    # The 'ast' variable is only for function signature uniformity, and is currently not used.
    output_source_directive = local_unique_directives.get("output_source", None)
    if output_source_directive:
        if has_encountered_output_source(context):
            raise GraphQLCompilationError("Cannot have more than one output source!")
        if is_in_optional_scope(context):
            raise GraphQLCompilationError("Cannot have the output source in an optional block!")
        set_output_source_data(context, location)
        return blocks.OutputSource()
    else:
        return None


def _process_tag_directive(context, current_schema_type, location, tag_directive):
    """Process the tag directive, modifying the context as appropriate.

    Args:
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        current_schema_type: GraphQLType, the schema type at the current location
        location: Location object representing the current location in the query
        tag_directive: GraphQL Directive that we want to process
    """
    if is_in_fold_scope(context):
        raise GraphQLCompilationError(
            "Tagging values within a @fold vertex field is "
            "not allowed! Location: {}".format(location)
        )

    if location.field == COUNT_META_FIELD_NAME:
        raise GraphQLCompilationError(
            "Tags are prohibited within @fold, but unexpectedly found use of "
            "a tag on the {} meta field that is only allowed within a @fold!"
            "Location: {}".format(COUNT_META_FIELD_NAME, location)
        )

    # Schema validation has ensured that the fields below exist.
    tag_name = tag_directive.arguments[0].value.value
    if context["metadata"].get_tag_info(tag_name) is not None:
        raise GraphQLCompilationError("Cannot reuse tag name: {}".format(tag_name))
    validate_safe_string(tag_name)
    context["metadata"].record_tag_info(
        tag_name,
        TagInfo(
            location=location,
            optional=is_in_optional_scope(context),
            type=strip_non_null_from_type(current_schema_type),
        ),
    )


def _compile_property_ast(
    schema, current_schema_type, ast, location, context, unique_local_directives
):
    """Process property directives at this AST node, updating the query context as appropriate.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library. Only for function signature
             uniformity at the moment -- it is currently not used.
        location: Location object representing the current location in the query
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        unique_local_directives: dict, directive name string -> directive object, containing
                                 unique directives present on the current AST node *only*
    """
    validate_property_directives(unique_local_directives)

    if location.field == COUNT_META_FIELD_NAME:
        # Verify that uses of this field are within a @fold scope.
        if not is_in_fold_scope(context):
            raise GraphQLCompilationError(
                'Cannot use the "{}" meta field when not within a @fold '
                "vertex field, as counting elements only makes sense "
                "in a fold. Location: {}".format(COUNT_META_FIELD_NAME, location)
            )

    # step P-2: Process @output directives.
    output_directive = unique_local_directives.get("output", None)
    if output_directive:
        # Schema validation has ensured that the fields below exist.
        output_name = output_directive.arguments[0].value.value
        if context["metadata"].get_output_info(output_name):
            raise GraphQLCompilationError("Cannot reuse output name: {}".format(output_name))
        validate_output_name(output_name)

        graphql_type = strip_non_null_from_type(current_schema_type)
        if is_in_fold_scope(context):
            # Fold outputs are only allowed at the last level of traversal.
            set_fold_innermost_scope(context)

            if location.field != COUNT_META_FIELD_NAME:
                graphql_type = GraphQLList(graphql_type)

        output_info = OutputInfo(
            location=location,
            type=graphql_type,
            optional=is_in_optional_scope(context),
        )
        context["metadata"].record_output_info(output_name, output_info)


def _get_recurse_directive_depth(field_name, field_directives):
    """Validate and return the depth parameter of the recurse directive."""
    recurse_directive = field_directives["recurse"]
    optional_directive = field_directives.get("optional", None)

    if optional_directive:
        raise GraphQLCompilationError(
            "Found both @optional and @recurse on the same vertex field: {}".format(field_name)
        )

    recurse_args = get_uniquely_named_objects_by_name(recurse_directive.arguments)
    recurse_depth = int(recurse_args["depth"].value.value)
    if recurse_depth < 1:
        raise GraphQLCompilationError(
            "Found recurse directive with disallowed depth: {}".format(recurse_depth)
        )

    return recurse_depth


def _validate_recurse_directive_types(current_schema_type, field_schema_type, context):
    """Perform type checks on the enclosing type and the recursed type for a recurse directive.

    Args:
        current_schema_type: GraphQLType, the schema type at the current location
        field_schema_type: GraphQLType, the schema type at the inner scope
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
    """
    # Get the set of all allowed types in the current scope.
    type_hints = context["type_equivalence_hints"].get(field_schema_type)
    type_hints_inverse = context["type_equivalence_hints_inverse"].get(field_schema_type)
    allowed_current_types = {field_schema_type}

    if type_hints and isinstance(type_hints, GraphQLUnionType):
        allowed_current_types.update(type_hints.types)

    if type_hints_inverse and isinstance(type_hints_inverse, GraphQLUnionType):
        allowed_current_types.update(type_hints_inverse.types)

    # The current scope must be of the same type as the field scope, or an acceptable subtype.
    current_scope_is_allowed = current_schema_type in allowed_current_types

    is_implemented_interface = (
        isinstance(field_schema_type, GraphQLInterfaceType)
        and isinstance(current_schema_type, GraphQLObjectType)
        and field_schema_type in current_schema_type.interfaces
    )

    if not any((current_scope_is_allowed, is_implemented_interface)):
        raise GraphQLCompilationError(
            "Edges expanded with a @recurse directive must either "
            "be of the same type as their enclosing scope, a supertype "
            "of the enclosing scope, or be of an interface type that is "
            "implemented by the type of their enclosing scope. "
            "Enclosing scope type: {}, edge type: "
            "{}".format(current_schema_type, field_schema_type)
        )


def _compile_vertex_ast(
    schema, current_schema_type, ast, location, context, unique_local_directives, fields
):
    """Return a list of basic blocks corresponding to the vertex AST node.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library
        location: Location object representing the current location in the query
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        unique_local_directives: dict, directive name string -> directive object, containing
                                 unique directives present on the current AST node *only*
        fields: tuple of lists (property_fields, vertex_fields), with lists of field objects
                present on the current vertex AST node

    Returns:
        list of basic blocks, the compiled output of the vertex AST node
    """
    basic_blocks = []
    query_metadata_table = context["metadata"]
    current_location_info = query_metadata_table.get_location_info(location)

    vertex_fields, property_fields = fields

    validate_vertex_directives(unique_local_directives)

    # step V-2: process @tag directives
    for field_ast in property_fields:
        field_name = get_ast_field_name(field_ast)
        property_schema_type = get_field_type_from_schema(current_schema_type, field_name)
        inner_location = location.navigate_to_field(field_name)
        local_unique_directives = get_unique_directives(field_ast)
        tag_directive = local_unique_directives.get("tag", None)
        if tag_directive:
            if get_local_filter_directives(field_ast, property_schema_type, None):
                raise GraphQLCompilationError(
                    "Cannot filter and tag the same field {}".format(inner_location)
                )
            _process_tag_directive(context, property_schema_type, inner_location, tag_directive)

    # step V-3: step into property fields
    for field_ast in property_fields:
        field_name = get_ast_field_name(field_ast)
        property_schema_type = get_field_type_from_schema(current_schema_type, field_name)

        inner_location = location.navigate_to_field(field_name)
        inner_basic_blocks = _compile_ast_node_to_ir(
            schema, property_schema_type, field_ast, inner_location, context
        )
        basic_blocks.extend(inner_basic_blocks)

    # step V-4: mark the graph position, and process output_source directive
    basic_blocks.append(_mark_location(location))

    output_source = _process_output_source_directive(
        schema, current_schema_type, ast, location, context, unique_local_directives
    )
    if output_source:
        basic_blocks.append(output_source)

    # step V-5: step into vertex fields
    for field_ast in vertex_fields:
        field_name = get_ast_field_name(field_ast)
        validate_context_for_visiting_vertex_field(location, field_name, context)

        field_schema_type = get_vertex_field_type(current_schema_type, field_name)
        hinted_base = context["type_equivalence_hints_inverse"].get(field_schema_type, None)
        if hinted_base:
            field_schema_type = hinted_base

        inner_unique_directives = get_unique_directives(field_ast)
        validate_vertex_field_directive_interactions(location, field_name, inner_unique_directives)
        validate_vertex_field_directive_in_context(
            location, field_name, inner_unique_directives, context
        )

        recurse_directive = inner_unique_directives.get("recurse", None)
        optional_directive = inner_unique_directives.get("optional", None)
        fold_directive = inner_unique_directives.get("fold", None)
        in_topmost_optional_block = False

        edge_traversal_is_optional = optional_directive is not None
        edge_traversal_is_folded = fold_directive is not None
        edge_traversal_is_recursive = recurse_directive is not None

        # This is true for any vertex expanded within an @optional scope.
        within_optional_scope = is_in_optional_scope(context)

        if edge_traversal_is_optional:
            # Invariant: There must always be a marked location corresponding to the query position
            # immediately before any optional Traverse.
            #
            # This invariant is verified in the IR self-consistency check module
            # (ir_self_consistency_checks.py), in the function named
            # _assert_mark_location_preceding_optional_traverse().
            #
            # This marked location is the one that the @optional directive's corresponding
            # optional Backtrack will jump back to. If such a marked location isn't present,
            # the backtrack could rewind to an old marked location and might ignore
            # entire stretches of applied filtering.
            #
            # Assumption: The only way there might not be a marked location here is
            # if the current location already traversed into child locations, not including folds.
            non_fold_child_locations = {
                child_location
                for child_location in query_metadata_table.get_child_locations(location)
                if not isinstance(child_location, FoldScopeLocation)
            }
            if non_fold_child_locations:
                location = query_metadata_table.revisit_location(location)
                basic_blocks.append(_mark_location(location))

        if fold_directive:
            inner_location = location.navigate_to_fold(field_name)
        else:
            inner_location = location.navigate_to_subpath(field_name)

        inner_location_info = LocationInfo(
            parent_location=location,
            type=strip_non_null_from_type(field_schema_type),
            coerced_from_type=None,
            optional_scopes_depth=(
                current_location_info.optional_scopes_depth + edge_traversal_is_optional
            ),
            recursive_scopes_depth=(
                current_location_info.recursive_scopes_depth + edge_traversal_is_recursive
            ),
            is_within_fold=(current_location_info.is_within_fold or edge_traversal_is_folded),
        )
        query_metadata_table.register_location(inner_location, inner_location_info)

        if edge_traversal_is_optional:
            # Remember where the topmost optional context started.
            topmost_optional = get_optional_scope_or_none(context)
            if topmost_optional is None:
                set_optional_scope_data(context, inner_location)
                in_topmost_optional_block = True

        edge_direction, edge_name = get_edge_direction_and_name(field_name)

        if fold_directive:
            fold_block = blocks.Fold(inner_location)
            basic_blocks.append(fold_block)
            set_fold_scope_data(context, inner_location)
        elif recurse_directive:
            _validate_recurse_directive_types(current_schema_type, field_schema_type, context)
            recurse_depth = _get_recurse_directive_depth(field_name, inner_unique_directives)
            basic_blocks.append(
                blocks.Recurse(
                    edge_direction,
                    edge_name,
                    recurse_depth,
                    within_optional_scope=within_optional_scope,
                )
            )
            query_metadata_table.record_recurse_info(
                location,
                RecurseInfo(
                    edge_direction=edge_direction, edge_name=edge_name, depth=recurse_depth
                ),
            )
        else:
            basic_blocks.append(
                blocks.Traverse(
                    edge_direction,
                    edge_name,
                    optional=edge_traversal_is_optional,
                    within_optional_scope=within_optional_scope,
                )
            )

        inner_basic_blocks = _compile_ast_node_to_ir(
            schema, field_schema_type, field_ast, inner_location, context
        )
        basic_blocks.extend(inner_basic_blocks)

        if edge_traversal_is_folded:
            has_count_filter = has_fold_count_filter(context)
            _validate_fold_has_outputs_or_count_filter(
                get_context_fold_info(context), has_count_filter, query_metadata_table
            )
            basic_blocks.append(blocks.Unfold())
            unmark_context_fold_scope(context)
            if has_count_filter:
                unmark_fold_count_filter(context)
            if is_in_fold_innermost_scope(context):
                unmark_fold_innermost_scope(context)

        if in_topmost_optional_block:
            unmark_optional_scope(context)

        # If we are currently evaluating a @fold vertex,
        # we didn't Traverse into it, so we don't need to backtrack out either.
        # We also don't backtrack if we've reached an @output_source.
        backtracking_required = (not fold_directive) and (
            not has_encountered_output_source(context)
        )
        if backtracking_required:
            if edge_traversal_is_optional:
                basic_blocks.append(blocks.EndOptional())
                basic_blocks.append(blocks.Backtrack(location, optional=True))

                # Exiting optional block!
                # Revisit the location so that there is a marked location right after the optional,
                # so that future Backtrack blocks return after the optional set of blocks, and
                # don't accidentally return to a prior location instead.
                location = query_metadata_table.revisit_location(location)

                basic_blocks.append(_mark_location(location))
            else:
                basic_blocks.append(blocks.Backtrack(location))

    return basic_blocks


def _are_locations_in_same_fold(first_location, second_location):
    """Return True if locations are contained in the same fold scope."""
    return (
        isinstance(first_location, FoldScopeLocation)
        and isinstance(second_location, FoldScopeLocation)
        and first_location.base_location == second_location.base_location
        and first_location.get_first_folded_edge() == second_location.get_first_folded_edge()
    )


def _validate_fold_has_outputs_or_count_filter(
    fold_scope_location, fold_has_count_filter, query_metadata_table
):
    """Ensure the @fold scope has at least one output, or filters on the size of the fold."""
    # This function makes sure that the @fold scope has an effect.
    # Folds either output data, or filter the data enclosing the fold based on the size of the fold.
    if fold_has_count_filter:
        # This fold has a filter on the "_x_count" property, so it is legal and has an effect.
        return True

    # At least one output in the outputs list must point to the fold_scope_location,
    # or the scope corresponding to fold_scope_location had no @outputs and is illegal.
    for _, output_info in query_metadata_table.outputs:
        if _are_locations_in_same_fold(output_info.location, fold_scope_location):
            return True

    raise GraphQLCompilationError(
        "Found a @fold scope that has no effect on the query. "
        "Each @fold scope must either perform filtering, or contain at "
        "least one field marked for output. Fold location: {}".format(fold_scope_location)
    )


def _compile_fragment_ast(schema, current_schema_type, ast, location, context):
    """Return a list of basic blocks corresponding to the inline fragment at this AST node.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library.
        location: Location object representing the current location in the query
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!

    Returns:
        list of basic blocks, the compiled output of the vertex AST node
    """
    query_metadata_table = context["metadata"]

    # step F-2. Emit a type coercion block if appropriate,
    #           then recurse into the fragment's selection.
    coerces_to_type_name = ast.type_condition.name.value
    coerces_to_type_obj = schema.get_type(coerces_to_type_name)

    basic_blocks = []

    # Check if the coercion is necessary.
    # No coercion is necessary if coercing to the current type of the scope,
    # or if the scope is of union type, to the base type of the union as defined by
    # the type_equivalence_hints compilation parameter.
    is_same_type_as_scope = is_same_type(current_schema_type, coerces_to_type_obj)
    equivalent_union_type = context["type_equivalence_hints"].get(coerces_to_type_obj, None)
    is_base_type_of_union = isinstance(current_schema_type, GraphQLUnionType) and is_same_type(
        current_schema_type, equivalent_union_type
    )

    if not (is_same_type_as_scope or is_base_type_of_union):
        # Coercion is required.
        query_metadata_table.record_coercion_at_location(location, coerces_to_type_obj)
        basic_blocks.append(blocks.CoerceType({coerces_to_type_name}))

    inner_basic_blocks = _compile_ast_node_to_ir(
        schema, coerces_to_type_obj, ast, location, context
    )
    basic_blocks.extend(inner_basic_blocks)

    return basic_blocks


def _compile_ast_node_to_ir(schema, current_schema_type, ast, location, context):
    """Compile the given GraphQL AST node into a list of basic blocks.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: the current GraphQL AST node, obtained from the graphql library
        location: Location object representing the current location in the query
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!

    Returns:
        list of basic blocks corresponding to this GraphQL AST node
    """
    basic_blocks = []

    # step 0: preprocessing
    local_unique_directives = get_unique_directives(ast)
    fields = _get_fields(ast)
    vertex_fields, property_fields = fields
    fragment = _get_inline_fragment(ast)
    filter_operations = get_local_filter_directives(ast, current_schema_type, vertex_fields)

    # We don't support type coercion while at the same time selecting fields.
    # Either there are no fields, or there is no fragment, otherwise we raise a compilation error.
    fragment_exists = fragment is not None
    fields_exist = vertex_fields or property_fields
    if fragment_exists and fields_exist:
        raise GraphQLCompilationError(
            "Cannot compile GraphQL that has inline fragment and "
            "selected fields in the same selection. Please move the "
            "selected fields inside the inline fragment."
        )

    if location.field is not None:  # we're at a property field
        # self-consistency check: cannot have an inline fragment at a property field
        if fragment_exists:
            raise AssertionError(
                "Found inline fragment at a property field: {} {}".format(location, fragment)
            )

        # self-consistency check: locations at properties don't have their own property locations
        if len(property_fields) > 0:
            raise AssertionError(
                "Found property fields on a property field: "
                "{} {}".format(location, property_fields)
            )

    # step 1: apply local filter, if any
    for filter_operation_info in filter_operations:
        filter_block = process_filter_directive(filter_operation_info, location, context)
        if isinstance(location, FoldScopeLocation) and location.field == COUNT_META_FIELD_NAME:
            # Filtering on the fold count field is only allowed at the innermost scope of a fold.
            set_fold_innermost_scope(context)

            # This Filter is going in the global operations section of the query, so it cannot
            # use LocalField expressions since there is no "local" location to use.
            # Rewrite it so that all references of data at a location instead use ContextFields.
            expected_field = expressions.LocalField(COUNT_META_FIELD_NAME, GraphQLInt)
            replacement_field = expressions.FoldedContextField(location, GraphQLInt)

            visitor_fn = expressions.make_replacement_visitor(expected_field, replacement_field)
            filter_block = filter_block.visit_and_update_expressions(visitor_fn)

            visitor_fn = expressions.make_type_replacement_visitor(
                expressions.ContextField,
                lambda context_field: expressions.GlobalContextField(
                    context_field.location, context_field.field_type
                ),
            )
            filter_block = filter_block.visit_and_update_expressions(visitor_fn)

            set_fold_count_filter(context)
            context["global_filters"].append(filter_block)
        else:
            basic_blocks.append(filter_block)

    if location.field is not None:
        # The location is at a property, compile the property data following P-steps.
        _compile_property_ast(
            schema, current_schema_type, ast, location, context, local_unique_directives
        )
    else:
        # The location is at a vertex.
        if fragment_exists:
            # Compile the fragment data following F-steps.
            # N.B.: Note that the "fragment" variable is the fragment's AST. Since we've asserted
            #       that the fragment is the only part of the selection set at the current AST node,
            #       we pass the "fragment" in the AST parameter of the _compile_fragment_ast()
            #       function, rather than the current AST node as in the other compilation steps.
            basic_blocks.extend(
                _compile_fragment_ast(schema, current_schema_type, fragment, location, context)
            )
        else:
            # Compile the vertex data following V-steps.
            basic_blocks.extend(
                _compile_vertex_ast(
                    schema,
                    current_schema_type,
                    ast,
                    location,
                    context,
                    local_unique_directives,
                    fields,
                )
            )

    return basic_blocks


def _validate_all_tags_are_used(metadata):
    """Ensure all tags are used in some filter."""
    tag_names = set([tag_name for tag_name, _ in metadata.tags])
    filter_arg_names = set()
    for location, _ in metadata.registered_locations:
        for filter_info in metadata.get_filter_infos(location):
            for filter_arg in filter_info.args:
                if is_tagged_parameter(filter_arg):
                    filter_arg_names.add(get_parameter_name(filter_arg))

    unused_tags = tag_names - filter_arg_names
    if unused_tags:
        raise GraphQLCompilationError(
            "This GraphQL query contains @tag directives whose values "
            "are not used: {}. This is not allowed. Please either use "
            "them in a filter or remove them entirely.".format(unused_tags)
        )


def _validate_and_create_output_metadata(
    output_name: str, output_info: OutputInfo
) -> OutputMetadata:
    """Create a new OutputMetadata object after validating the output type.

    Checks the following before creating a new OutputMetadata object:
        - _x_count output is within a fold scope and has type GraphQLInt
        - all other outputs within a fold scope have type GraphQLList

    Args:
        output_name: name of the output specified in a query
        output_info: information about the output

    Returns:
        OutputMetadata containing metadata about the output

    Raises:
        AssertionError if an invalid output type is found
    """
    # Ensure _x_count is within a fold scope.
    if output_info.location.field == COUNT_META_FIELD_NAME and not isinstance(
        output_info.location, FoldScopeLocation
    ):
        raise AssertionError(
            "Invalid output: {} was not in a fold scope.".format(COUNT_META_FIELD_NAME)
        )
    # Ensure folded outputs have valid type.
    if isinstance(output_info.location, FoldScopeLocation):
        # Ensure _x_count is a GraphQLInt.
        if output_info.location.field == COUNT_META_FIELD_NAME and not is_same_type(
            output_info.type, GraphQLInt
        ):
            raise AssertionError(
                f"Invalid output: received {COUNT_META_FIELD_NAME} with type {output_info.type}, "
                f"but {COUNT_META_FIELD_NAME} must always be of type Int"
            )
        # Ensure all other folded outputs are GraphQLList.
        elif output_info.location.field != COUNT_META_FIELD_NAME and not isinstance(
            output_info.type, GraphQLList
        ):
            raise AssertionError(
                "Invalid output: non-{} folded output must have type "
                "GraphQLList. Received type {} for folded output "
                "{}.".format(COUNT_META_FIELD_NAME, output_info.type, output_name)
            )

    return OutputMetadata(
        type=output_info.type,
        optional=output_info.optional,
        folded=isinstance(output_info.location, FoldScopeLocation),
    )


def _compile_root_ast_to_ir(schema, ast, type_equivalence_hints=None):
    """Compile a full GraphQL abstract syntax tree (AST) to intermediate representation.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        ast: the root GraphQL AST node for the query, obtained from the graphql library,
             and already validated against the schema for type-correctness
        type_equivalence_hints: optional dict of GraphQL type to equivalent GraphQL union

    Returns:
        IrAndMetadata for the given schema and AST
    """
    base_ast = get_only_selection_from_ast(ast, GraphQLCompilationError)
    base_start_type = get_ast_field_name(base_ast)  # This is the type at which querying starts.

    # Validation passed, so the base_start_type must exist as a field of the root query.
    current_schema_type = get_field_type_from_schema(schema.query_type, base_start_type)

    # Allow list types at the query root in the schema.
    if isinstance(current_schema_type, GraphQLList):
        current_schema_type = current_schema_type.of_type

    # Construct the start location of the query and its associated metadata.
    location = Location((base_start_type,))
    base_location_info = LocationInfo(
        parent_location=None,
        type=current_schema_type,
        coerced_from_type=None,
        optional_scopes_depth=0,
        recursive_scopes_depth=0,
        is_within_fold=False,
    )
    query_metadata_table = QueryMetadataTable(location, base_location_info)

    # Default argument value is empty dict
    if not type_equivalence_hints:
        type_equivalence_hints = dict()

    # Construct the starting context object.
    context = {
        # 'metadata' is the QueryMetadataTable describing all the metadata collected during query
        # processing, including location metadata (e.g. which locations are folded or optional).
        "metadata": query_metadata_table,
        # 'global_filters' is a list that may contain Filter blocks that are generated during
        # query processing, but apply to the global query scope and should be appended to the
        # IR blocks only after the GlobalOperationsStart block has been emitted.
        "global_filters": [],
        # 'inputs' is a dict mapping input parameter names to their respective expected GraphQL
        # types, as automatically inferred by inspecting the query structure
        "inputs": dict(),
        # 'type_equivalence_hints' is a dict mapping GraphQL types to equivalent GraphQL unions
        "type_equivalence_hints": type_equivalence_hints,
        # 'type_equivalence_hints_inverse' is the inverse of type_equivalence_hints,
        # which is always invertible.
        "type_equivalence_hints_inverse": invert_dict(type_equivalence_hints),
    }

    # Add the query root basic block to the output.
    basic_blocks = [blocks.QueryRoot({base_start_type})]

    # Ensure the GraphQL query root doesn't immediately have a fragment (type coercion).
    # Instead of starting at one type and coercing to another,
    # users should simply start at the type to which they are coercing.
    immediate_fragment = _get_inline_fragment(base_ast)
    if immediate_fragment is not None:
        msg_args = {
            "coerce_to": immediate_fragment.type_condition.name.value,
            "type_from": base_start_type,
        }
        raise GraphQLCompilationError(
            "Found inline fragment coercing to type {coerce_to}, "
            "immediately inside query root asking for type {type_from}. "
            "This is a contrived pattern -- you should simply start "
            "your query at {coerce_to}.".format(**msg_args)
        )

    # Ensure the GraphQL query root doesn't have any vertex directives
    # that are disallowed on the root node.
    validate_root_vertex_directives(base_ast)

    # Compile and add the basic blocks for the query's base AST vertex.
    new_basic_blocks = _compile_ast_node_to_ir(
        schema, current_schema_type, base_ast, location, context
    )
    basic_blocks.extend(new_basic_blocks)

    _validate_all_tags_are_used(context["metadata"])

    # All operations after this point affect the global query scope, and are not related to
    # the "current" location in the query produced by the sequence of Traverse/Backtrack blocks.
    basic_blocks.append(blocks.GlobalOperationsStart())

    # Add any filters that apply to the global query scope.
    basic_blocks.extend(context["global_filters"])

    # Based on the outputs context data, add an output step.
    basic_blocks.append(_compile_output_step(query_metadata_table))

    # Construct the output metadata, ensuring that all folded outputs have a valid type.
    output_metadata = {
        name: _validate_and_create_output_metadata(name, info)
        for name, info in query_metadata_table.outputs
    }

    return IrAndMetadata(
        ir_blocks=basic_blocks,
        input_metadata=context["inputs"],
        output_metadata=output_metadata,
        query_metadata_table=context["metadata"],
    )


def _compile_output_step(query_metadata_table):
    """Construct the final ConstructResult basic block that defines the output format of the query.

    Args:
        query_metadata_table: QueryMetadataTable object, part of which specifies the location from
                              where to get the output, and whether the output is optional (and
                              therefore may be missing); missing optional data is replaced with
                              'null'

    Returns:
        a ConstructResult basic block that constructs appropriate outputs for the query
    """
    if next(query_metadata_table.outputs, None) is None:
        raise GraphQLCompilationError(
            "No fields were selected for output! Please mark at least "
            "one field with the @output directive."
        )

    output_fields = {}
    for output_name, output_info in query_metadata_table.outputs:
        location = output_info.location
        optional = output_info.optional
        graphql_type = output_info.type

        expression = None
        existence_check = None
        # pylint: disable=redefined-variable-type
        if isinstance(location, FoldScopeLocation):
            if optional:
                raise AssertionError(
                    "Unreachable state reached, optional in fold: {}".format(output_info)
                )

            if location.field == COUNT_META_FIELD_NAME:
                expression = expressions.FoldCountContextField(location)
            else:
                expression = expressions.FoldedContextField(location, graphql_type)
        else:
            expression = expressions.OutputContextField(location, graphql_type)

            if optional:
                existence_check = expressions.ContextFieldExistence(location.at_vertex())

        if existence_check:
            expression = expressions.TernaryConditional(
                existence_check, expression, expressions.NullLiteral
            )
        # pylint: enable=redefined-variable-type

        output_fields[output_name] = expression

    return blocks.ConstructResult(output_fields)


##############
# Public API #
##############


def ast_to_ir(
    schema: GraphQLSchema,
    ast: DocumentNode,
    type_equivalence_hints: Optional[TypeEquivalenceHintsType] = None,
) -> IrAndMetadata:
    """Convert the given GraphQL AST object into compiler IR, using the given schema object.

    Args:
        schema: schema object created using the GraphQL library for which the query must be valid
        ast: query in AST form to transform into compiler IR
        type_equivalence_hints: optional, used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces), as well as a
                                workaround for Gremlin's total lack of inheritance-awareness.
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union.
                                Recursive expansion of type equivalence hints is not performed,
                                and only type-level correctness of this argument is enforced.
                                See README.md for more details on everything this parameter does.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****

    Returns:
        IrAndMetadata for the given schema and AST

    Raises flavors of GraphQLError in the following cases:
        - if the query is invalid GraphQL (GraphQLParsingError);
        - if the query doesn't match the schema (GraphQLValidationError);
        - if the query has more than one definition block (GraphQLValidationError);
        - if the query has more than one selection in the root object (GraphQLCompilationError);
        - if the query does not obey directive usage rules (GraphQLCompilationError);
        - if the query provides invalid / disallowed / wrong number of arguments
          for a directive (GraphQLCompilationError).

    In the case of implementation bugs, could also raise ValueError, TypeError, or AssertionError.
    """
    validation_errors = validate_schema_and_query_ast(schema, ast)
    if validation_errors:
        raise GraphQLValidationError("String does not validate: {}".format(validation_errors))

    base_ast = get_only_query_definition(ast, GraphQLValidationError)
    return _compile_root_ast_to_ir(schema, base_ast, type_equivalence_hints=type_equivalence_hints)


def graphql_to_ir(
    schema: GraphQLSchema,
    graphql_string: str,
    type_equivalence_hints: Optional[TypeEquivalenceHintsType] = None,
) -> IrAndMetadata:
    """Convert the given GraphQL string into compiler IR, using the given schema object.

    Args:
        schema: schema object created using the GraphQL library for which the query must be valid
        graphql_string: GraphQL query to transform into compiler IR
        type_equivalence_hints: optional, used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces), as well as a
                                workaround for Gremlin's total lack of inheritance-awareness.
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union.
                                Recursive expansion of type equivalence hints is not performed,
                                and only type-level correctness of this argument is enforced.
                                See README.md for more details on everything this parameter does.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****

    Returns:
        IrAndMetadata for the given schema and GraphQL query string

    Raises flavors of GraphQLError in the following cases:
        - if the query is invalid GraphQL (GraphQLParsingError);
        - if the query doesn't match the schema (GraphQLValidationError);
        - if the query has more than one definition block (GraphQLValidationError);
        - if the query has more than one selection in the root object (GraphQLCompilationError);
        - if the query does not obey directive usage rules (GraphQLCompilationError);
        - if the query provides invalid / disallowed / wrong number of arguments
          for a directive (GraphQLCompilationError).

    In the case of implementation bugs, could also raise ValueError, TypeError, or AssertionError.
    """
    ast = safe_parse_graphql(graphql_string)
    return ast_to_ir(schema, ast, type_equivalence_hints=type_equivalence_hints)
