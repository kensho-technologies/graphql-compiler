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
    step P-2. Process property-only directives, like @tag and @output.
    ***************

    *** V-steps ***
    step V-2. Recurse into any property field children of the current AST node
              (property fields cannot have property fields of their own, see _compile_vertex_ast()).

    step V-3. Property field processing complete:  (see _compile_vertex_ast())
        - mark the current location in the query, since all @filter directives that apply to the
          current field have already been processed;
        - process the output_source directive, if it exists

    step V-4. Recurse into any vertex field children of the current AST node:
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
from collections import namedtuple

from graphql.error import GraphQLSyntaxError
from graphql.language.ast import Field, InlineFragment
from graphql.language.parser import parse
from graphql.type.definition import (GraphQLInterfaceType, GraphQLList, GraphQLObjectType,
                                     GraphQLUnionType)
from graphql.validation import validate
import six

from . import blocks, expressions
from ..exceptions import GraphQLCompilationError, GraphQLParsingError, GraphQLValidationError
from .context_helpers import (has_encountered_output_source, is_in_fold_scope, is_in_optional_scope,
                              validate_context_for_visiting_vertex_field)
from .directive_helpers import (get_local_filter_directives, get_unique_directives,
                                validate_property_directives, validate_root_vertex_directives,
                                validate_vertex_directives,
                                validate_vertex_field_directive_in_context,
                                validate_vertex_field_directive_interactions)
from .filters import process_filter_directive
from .helpers import (FoldScopeLocation, Location, get_ast_field_name, get_field_type_from_schema,
                      get_uniquely_named_objects_by_name, get_vertex_field_type,
                      is_vertex_field_name, strip_non_null_from_type, validate_safe_string)


# LocationStackEntry contains the following:
# - location: Location object correspoding to an inserted MarkLocation block
# - num_traverses: Int counter for the number of traverses intserted after the last MarkLocation
#                  (corresponding Location stored in `location`)
LocationStackEntry = namedtuple('LocationStackEntry', ('location', 'num_traverses'))


def _construct_location_stack_entry(location, num_traverses):
    """Return a LocationStackEntry namedtuple with the specified parameters."""
    if not isinstance(num_traverses, int) or num_traverses < 0:
        raise AssertionError(u'Attempted to create a LocationStackEntry namedtuple with an invalid '
                             u'value for "num_traverses" {}. This is not allowed.'
                             .format(num_traverses))
    if not isinstance(location, Location):
        raise AssertionError(u'Attempted to create a LocationStackEntry namedtuple with an invalid '
                             u'value for "location" {}. This is not allowed.'
                             .format(location))
    return LocationStackEntry(location=location, num_traverses=num_traverses)


# The OutputMetadata will have the following types for its members:
# - type: a GraphQL type object, like String or Integer, describing the type of that output value
# - optional: boolean, whether the output is part of an optional traversal and
#             could therefore have a value of null because it did not exist
class OutputMetadata(namedtuple('OutputMetadata', ('type', 'optional'))):
    def __eq__(self, other):
        """Check another OutputMetadata object for equality against this one."""
        # Unfortunately, GraphQL types don't have an equality operator defined,
        # and instead have this "is_same_type" function. Hence, we have to override equality here.
        return self.type.is_same_type(other.type) and self.optional == other.optional

    def __ne__(self, other):
        """Check another OutputMetadata object for non-equality against this one."""
        return not self.__eq__(other)


IrAndMetadata = namedtuple(
    'IrAndMetadata', (
        'ir_blocks',
        'input_metadata',
        'output_metadata',
        'location_types',
        'coerced_locations',
    )
)


def _get_fields(ast):
    """Return a list of property fields, and a list of vertex fields, for the given AST node.

    Also verifies that all property fields for the AST node appear before all vertex fields,
    raising GraphQLCompilationError if that is not the case.

    Args:
        ast: GraphQL AST node, obtained from the graphql library

    Returns:
        tuple of two lists
            - the first list contains ASTs for property fields
            - the second list contains ASTs for vertex fields
    """
    if not ast.selection_set:
        # There are no child fields.
        return [], []

    property_fields = []
    vertex_fields = []
    seen_field_names = set()
    switched_to_vertices = False  # Ensures that all property fields are before all vertex fields.
    for field_ast in ast.selection_set.selections:
        if not isinstance(field_ast, Field):
            # We are getting Fields only, ignore everything else.
            continue

        name = get_ast_field_name(field_ast)
        if name in seen_field_names:
            # If we ever allow repeated field names,
            # then we have to change the Location naming scheme to reflect the repetitions
            # and disambiguate between Recurse and Traverse visits to a Location.
            raise GraphQLCompilationError(u'Encountered repeated field name: {}'.format(name))
        seen_field_names.add(name)

        # Vertex fields start with 'out_' or 'in_', denoting the edge direction to that vertex.
        if is_vertex_field_name(name):
            switched_to_vertices = True
            vertex_fields.append(field_ast)
        else:
            if switched_to_vertices:
                raise GraphQLCompilationError(u'Encountered property field {} '
                                              u'after vertex fields!'.format(name))
            property_fields.append(field_ast)

    return vertex_fields, property_fields


def _get_inline_fragment(ast):
    """Return the inline fragment at the current AST node, or None if no fragment exists."""
    if not ast.selection_set:
        # There is nothing selected here, so no fragment.
        return None

    fragments = [
        ast_node
        for ast_node in ast.selection_set.selections
        if isinstance(ast_node, InlineFragment)
    ]

    if not fragments:
        return None

    if len(fragments) > 1:
        raise GraphQLCompilationError(u'Cannot compile GraphQL with more than one fragment in '
                                      u'a given selection set.')

    return fragments[0]


def _mark_location(location):
    """Return a MarkLocation basic block that marks the present location in the query."""
    return blocks.MarkLocation(location)


def _process_output_source_directive(schema, current_schema_type, ast,
                                     location, context, local_unique_directives):
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
    output_source_directive = local_unique_directives.get('output_source', None)
    if output_source_directive:
        if has_encountered_output_source(context):
            raise GraphQLCompilationError(u'Cannot have more than one output source!')
        if is_in_optional_scope(context):
            raise GraphQLCompilationError(u'Cannot have the output source in an optional block!')
        context['output_source'] = location
        return blocks.OutputSource()
    else:
        return None


def _compile_property_ast(schema, current_schema_type, ast, location,
                          context, unique_local_directives):
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

    # step P-2: process property-only directives
    tag_directive = unique_local_directives.get('tag', None)
    if tag_directive:
        if is_in_fold_scope(context):
            raise GraphQLCompilationError(u'Tagging values within a @fold vertex field is '
                                          u'not allowed! Location: {}'.format(location))

        # Schema validation has ensured that the fields below exist.
        tag_name = tag_directive.arguments[0].value.value
        if tag_name in context['tags']:
            raise GraphQLCompilationError(u'Cannot reuse tag name: {}'.format(tag_name))
        validate_safe_string(tag_name)
        context['tags'][tag_name] = {
            'location': location,
            'optional': is_in_optional_scope(context),
            'type': strip_non_null_from_type(current_schema_type),
        }

    output_directive = unique_local_directives.get('output', None)
    if output_directive:
        # Schema validation has ensured that the fields below exist.
        output_name = output_directive.arguments[0].value.value
        if output_name in context['outputs']:
            raise GraphQLCompilationError(u'Cannot reuse output name: '
                                          u'{}, {}'.format(output_name, context))
        validate_safe_string(output_name)

        graphql_type = strip_non_null_from_type(current_schema_type)
        if is_in_fold_scope(context):
            graphql_type = GraphQLList(graphql_type)
            # Fold outputs are only allowed at the last level of traversal
            context['fold_innermost_scope'] = None

        context['outputs'][output_name] = {
            'location': location,
            'optional': is_in_optional_scope(context),
            'type': graphql_type,
            'fold': context.get('fold', None),
        }


def _get_recurse_directive_depth(field_name, field_directives):
    """Validate and return the depth parameter of the recurse directive."""
    recurse_directive = field_directives['recurse']
    optional_directive = field_directives.get('optional', None)

    if optional_directive:
        raise GraphQLCompilationError(u'Found both @optional and @recurse on '
                                      u'the same vertex field: {}'.format(field_name))

    recurse_args = get_uniquely_named_objects_by_name(recurse_directive.arguments)
    recurse_depth = int(recurse_args['depth'].value.value)
    if recurse_depth < 1:
        raise GraphQLCompilationError(u'Found recurse directive with disallowed depth: '
                                      u'{}'.format(recurse_depth))

    return recurse_depth


def _validate_recurse_directive_types(current_schema_type, field_schema_type):
    """Perform type checks on the enclosing type and the recursed type for a recurse directive."""
    has_union_type = isinstance(field_schema_type, GraphQLUnionType)
    is_same_type = current_schema_type.is_same_type(field_schema_type)
    is_implemented_interface = (
        isinstance(field_schema_type, GraphQLInterfaceType) and
        isinstance(current_schema_type, GraphQLObjectType) and
        field_schema_type in current_schema_type.interfaces
    )

    if not any((has_union_type, is_same_type, is_implemented_interface)):
        raise GraphQLCompilationError(u'Edges expanded with a @recurse directive must either '
                                      u'be of union type, or be of the same type as their '
                                      u'enclosing scope, or be of an interface type that is '
                                      u'implemented by the type of their enclosing scope. '
                                      u'Enclosing scope type: {}, edge type: '
                                      u'{}'.format(current_schema_type, field_schema_type))


def _get_edge_direction_and_name(vertex_field_name):
    """Get the edge direction and name from a non-root vertex field name."""
    edge_direction = None
    edge_name = None
    if vertex_field_name.startswith('out_'):
        edge_direction = 'out'
        edge_name = vertex_field_name[4:]
    elif vertex_field_name.startswith('in_'):
        edge_direction = 'in'
        edge_name = vertex_field_name[3:]
    else:
        raise AssertionError(u'Unreachable condition reached:', vertex_field_name)
    return edge_direction, edge_name


def _compile_vertex_ast(schema, current_schema_type, ast,
                        location, context, unique_local_directives, fields):
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
    vertex_fields, property_fields = fields

    validate_vertex_directives(unique_local_directives)

    # step V-2: step into property fields
    for field_ast in property_fields:
        field_name = get_ast_field_name(field_ast)
        property_schema_type = get_field_type_from_schema(current_schema_type, field_name)

        inner_location = location.navigate_to_field(field_name)
        inner_basic_blocks = _compile_ast_node_to_ir(schema, property_schema_type, field_ast,
                                                     inner_location, context)
        basic_blocks.extend(inner_basic_blocks)

    # The length of the stack should be the same before exiting this function
    initial_marked_location_stack_size = len(context['marked_location_stack'])

    # step V-3: mark the graph position, and process output_source directive
    if not is_in_fold_scope(context):
        # We only mark the position if we aren't in a folded scope.
        # Folded scopes don't actually traverse to the location, so it's never really visited.
        context['location_types'][location] = strip_non_null_from_type(current_schema_type)
        basic_blocks.append(_mark_location(location))
        # The following append is the Location corresponding to the initial MarkLocation
        # for the current vertex and the `num_traverses` counter set to 0.
        context['marked_location_stack'].append(_construct_location_stack_entry(location, 0))

    output_source = _process_output_source_directive(schema, current_schema_type, ast,
                                                     location, context, unique_local_directives)
    if output_source:
        basic_blocks.append(output_source)

    # step V-4: step into vertex fields
    for field_ast in vertex_fields:
        field_name = get_ast_field_name(field_ast)
        inner_location = location.navigate_to_subpath(field_name)
        validate_context_for_visiting_vertex_field(inner_location, context)

        field_schema_type = get_vertex_field_type(current_schema_type, field_name)

        inner_unique_directives = get_unique_directives(field_ast)
        validate_vertex_field_directive_interactions(inner_location, inner_unique_directives)
        validate_vertex_field_directive_in_context(inner_location, inner_unique_directives, context)

        recurse_directive = inner_unique_directives.get('recurse', None)
        optional_directive = inner_unique_directives.get('optional', None)
        fold_directive = inner_unique_directives.get('fold', None)
        in_topmost_optional_block = False

        edge_traversal_is_optional = optional_directive is not None

        # This is true for any vertex expanded within an @optional scope.
        # Currently @optional is not allowed within @optional.
        # This will need to change if nested @optionals have to be supported.
        within_optional_scope = 'optional' in context and not edge_traversal_is_optional

        if edge_traversal_is_optional:
            # Entering an optional block!
            # Make sure there's a marked location right before it for the optional Backtrack
            # to jump back to. Otherwise, the traversal could rewind to an old marked location
            # and might ignore entire stretches of applied filtering.
            if context['marked_location_stack'][-1].num_traverses > 0:
                location = location.revisit()
                context['location_types'][location] = strip_non_null_from_type(current_schema_type)
                basic_blocks.append(_mark_location(location))
                context['marked_location_stack'].pop()
                new_stack_entry = _construct_location_stack_entry(location, 0)
                context['marked_location_stack'].append(new_stack_entry)

            # Remember where the topmost optional context started.
            topmost_optional = context.get('optional', None)
            if topmost_optional is None:
                context['optional'] = inner_location
                in_topmost_optional_block = True

        edge_direction, edge_name = _get_edge_direction_and_name(field_name)

        if fold_directive:
            current_location = context['marked_location_stack'][-1].location
            fold_scope_location = FoldScopeLocation(current_location, (edge_direction, edge_name))
            fold_block = blocks.Fold(fold_scope_location)
            basic_blocks.append(fold_block)
            context['fold'] = fold_scope_location
        elif recurse_directive:
            recurse_depth = _get_recurse_directive_depth(field_name, inner_unique_directives)
            _validate_recurse_directive_types(current_schema_type, field_schema_type)
            basic_blocks.append(blocks.Recurse(edge_direction,
                                               edge_name,
                                               recurse_depth,
                                               within_optional_scope=within_optional_scope))
        else:
            basic_blocks.append(blocks.Traverse(edge_direction, edge_name,
                                                optional=edge_traversal_is_optional,
                                                within_optional_scope=within_optional_scope))

        if not fold_directive and not is_in_fold_scope(context):
            # Current block is either a Traverse or a Recurse that is not within any fold context.
            # Increment the `num_traverses` counter.
            old_location_stack_entry = context['marked_location_stack'][-1]
            new_location_stack_entry = _construct_location_stack_entry(
                old_location_stack_entry.location, old_location_stack_entry.num_traverses + 1)
            context['marked_location_stack'][-1] = new_location_stack_entry

        inner_basic_blocks = _compile_ast_node_to_ir(schema, field_schema_type, field_ast,
                                                     inner_location, context)
        basic_blocks.extend(inner_basic_blocks)

        if fold_directive:
            _validate_fold_has_outputs(context['fold'], context['outputs'])
            basic_blocks.append(blocks.Unfold())
            del context['fold']
            if 'fold_innermost_scope' in context:
                del context['fold_innermost_scope']
            else:
                raise AssertionError(u'Output inside @fold scope did not add '
                                     u'"fold_innermost_scope" to context! '
                                     u'Location: {}'.format(fold_scope_location))

        if in_topmost_optional_block:
            basic_blocks.append(blocks.EndOptional())
            del context['optional']

        # If we are currently evaluating a @fold vertex,
        # we didn't Traverse into it, so we don't need to backtrack out either.
        # Alternatively, we don't backtrack if we've reached an @output_source.
        backtracking_required = (
            (not fold_directive) and (not has_encountered_output_source(context)))
        if backtracking_required:
            if optional_directive is not None:
                basic_blocks.append(blocks.Backtrack(location, optional=True))

                # Exiting optional block!
                # Add a MarkLocation right after the optional, to ensure future Backtrack blocks
                # return to a position after the optional set of blocks.
                location = location.revisit()
                context['location_types'][location] = strip_non_null_from_type(current_schema_type)
                basic_blocks.append(_mark_location(location))
                context['marked_location_stack'].pop()
                new_stack_entry = _construct_location_stack_entry(location, 0)
                context['marked_location_stack'].append(new_stack_entry)
            else:
                basic_blocks.append(blocks.Backtrack(location))

    # Pop off the initial Location for the current vertex.
    if not is_in_fold_scope(context):
        context['marked_location_stack'].pop()

    # Check that the length of the stack remains the same as when control entered this function.
    final_marked_location_stack_size = len(context['marked_location_stack'])
    if initial_marked_location_stack_size != final_marked_location_stack_size:
        raise AssertionError(u'Size of stack changed from {} to {} after executing this function.'
                             u'This should never happen : {}'
                             .format(initial_marked_location_stack_size,
                                     final_marked_location_stack_size,
                                     context['marked_location_stack']))

    return basic_blocks


def _validate_fold_has_outputs(fold_scope_location, outputs):
    """Ensure the @fold scope has at least one output."""
    # At least one output in the outputs list must point to the fold_scope_location,
    # or the scope corresponding to fold_scope_location had no @outputs and is illegal.
    for output in six.itervalues(outputs):
        if output['fold'] == fold_scope_location:
            return True

    raise GraphQLCompilationError(u'Each @fold scope must contain at least one field '
                                  u'marked @output. Encountered a @fold with no outputs: '
                                  u'{}'.format(fold_scope_location))


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
    # step F-2. Emit a type coercion block if appropriate,
    #           then recurse into the fragment's selection.
    coerces_to_type_name = ast.type_condition.name.value
    coerces_to_type_obj = schema.get_type(coerces_to_type_name)

    basic_blocks = []

    # Check if the coercion is necessary.
    # No coercion is necessary if coercing to the current type of the scope,
    # or if the scope is of union type, to the base type of the union as defined by
    # the type_equivalence_hints compilation parameter.
    is_same_type_as_scope = current_schema_type.is_same_type(coerces_to_type_obj)
    equivalent_union_type = context['type_equivalence_hints'].get(coerces_to_type_obj, None)
    is_base_type_of_union = (
        isinstance(current_schema_type, GraphQLUnionType) and
        current_schema_type.is_same_type(equivalent_union_type)
    )

    if not (is_same_type_as_scope or is_base_type_of_union):
        # Coercion is required.
        context['coerced_locations'].add(location)
        basic_blocks.append(blocks.CoerceType({coerces_to_type_name}))

    inner_basic_blocks = _compile_ast_node_to_ir(
        schema, coerces_to_type_obj, ast, location, context)
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
    filter_operations = get_local_filter_directives(
        ast, current_schema_type, vertex_fields)

    # We don't support type coercion while at the same time selecting fields.
    # Either there are no fields, or there is no fragment, otherwise we raise a compilation error.
    fragment_exists = fragment is not None
    fields_exist = vertex_fields or property_fields
    if fragment_exists and fields_exist:
        raise GraphQLCompilationError(u'Cannot compile GraphQL that has inline fragment and '
                                      u'selected fields in the same selection. Please move the '
                                      u'selected fields inside the inline fragment.')

    if location.field is not None:  # we're at a property field
        # sanity-check: cannot have an inline fragment at a property field
        if fragment_exists:
            raise AssertionError(u'Found inline fragment at a property field: '
                                 u'{} {}'.format(location, fragment))

        # sanity-check: locations at properties don't have their own property locations
        if len(property_fields) > 0:
            raise AssertionError(u'Found property fields on a property field: '
                                 u'{} {}'.format(location, property_fields))

    # step 1: apply local filter, if any
    for filter_operation_info in filter_operations:
        basic_blocks.append(
            process_filter_directive(filter_operation_info, context))

    if location.field is not None:
        # The location is at a property, compile the property data following P-steps.
        _compile_property_ast(schema, current_schema_type, ast,
                              location, context, local_unique_directives)
    else:
        # The location is at a vertex.
        if fragment_exists:
            # Compile the fragment data following F-steps.
            # N.B.: Note that the "fragment" variable is the fragment's AST. Since we've asserted
            #       that the fragment is the only part of the selection set at the current AST node,
            #       we pass the "fragment" in the AST parameter of the _compile_fragment_ast()
            #       function, rather than the current AST node as in the other compilation steps.
            basic_blocks.extend(
                _compile_fragment_ast(schema, current_schema_type, fragment, location, context))
        else:
            # Compile the vertex data following V-steps.
            basic_blocks.extend(
                _compile_vertex_ast(schema, current_schema_type, ast,
                                    location, context, local_unique_directives, fields))

    return basic_blocks


def _compile_root_ast_to_ir(schema, ast, type_equivalence_hints=None):
    """Compile a full GraphQL abstract syntax tree (AST) to intermediate representation.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        ast: the root GraphQL AST node for the query, obtained from the graphql library,
             and already validated against the schema for type-correctness
        type_equivalence_hints: optional dict of GraphQL type to equivalent GraphQL union

    Returns:
        IrAndMetadata named tuple, containing fields:
        - ir_blocks: a list of IR basic block objects
        - input_metadata: a dict of expected input parameters (string) -> inferred GraphQL type
        - output_metadata: a dict of output name (string) -> OutputMetadata object
        - location_types: a dict of location objects -> GraphQL type objects at that location
        - coerced_locations: a set of location objects indicating where type coercions have happened
    """
    if len(ast.selection_set.selections) != 1:
        raise GraphQLCompilationError(u'Cannot process AST with more than one root selection!')

    base_ast = ast.selection_set.selections[0]
    base_start_type = get_ast_field_name(base_ast)  # This is the type at which querying starts.

    # Validation passed, so the base_start_type must exist as a field of the root query.
    current_schema_type = get_field_type_from_schema(schema.get_query_type(), base_start_type)

    # Construct the start location of the query, and the starting context object.
    location = Location((base_start_type,))
    context = {
        # 'tags' is a dict containing
        #  - location: Location where the tag was defined
        #  - optional: boolean representing whether the tag was defined within an @optional scope
        #  - type: GraphQLType of the tagged value
        'tags': dict(),
        # 'outputs' is a dict mapping each output name to another dict which contains
        #  - location: Location where to output from
        #  - optional: boolean representing whether the output was defined within an @optional scope
        #  - type: GraphQLType of the output
        #  - fold: FoldScopeLocation object if the current output was defined within a fold scope,
        #          and None otherwise
        'outputs': dict(),
        # 'inputs' is a dict mapping input parameter names to their respective expected GraphQL
        # types, as automatically inferred by inspecting the query structure
        'inputs': dict(),
        # 'location_types' is a dict mapping each Location to its GraphQLType
        # (schema type of the location)
        'location_types': dict(),
        # 'coerced_locations' is the set of all locations whose type was coerced to a subtype
        # of the type already implied by the GraphQL schema for that vertex field.
        'coerced_locations': set(),
        # 'type_equivalence_hints' is a dict mapping GraphQL types to equivalent GraphQL unions
        'type_equivalence_hints': type_equivalence_hints or dict(),
        # The marked_location_stack explicitly maintains a stack (implemented as list)
        # of namedtuples (each corresponding to a MarkLocation) containing:
        #  - location: the location within the corresponding MarkLocation object
        #  - num_traverses: the number of Recurse and Traverse blocks created
        #                   after the corresponding MarkLocation
        'marked_location_stack': []
    }

    # Add the query root basic block to the output.
    basic_blocks = [
        blocks.QueryRoot({base_start_type})
    ]

    # Ensure the GraphQL query root doesn't immediately have a fragment (type coercion).
    # Instead of starting at one type and coercing to another,
    # users should simply start at the type to which they are coercing.
    immediate_fragment = _get_inline_fragment(base_ast)
    if immediate_fragment is not None:
        msg_args = {
            'coerce_to': immediate_fragment.type_condition.name.value,
            'type_from': base_start_type,
        }
        raise GraphQLCompilationError(u'Found inline fragment coercing to type {coerce_to}, '
                                      u'immediately inside query root asking for type {type_from}. '
                                      u'This is a contrived pattern -- you should simply start '
                                      u'your query at {coerce_to}.'.format(**msg_args))

    # Ensure the GraphQL query root doesn't have any vertex directives
    # that are disallowed on the root node.
    validate_root_vertex_directives(base_ast)

    # Compile and add the basic blocks for the query's base AST vertex.
    new_basic_blocks = _compile_ast_node_to_ir(
        schema, current_schema_type, base_ast, location, context)
    basic_blocks.extend(new_basic_blocks)

    # Based on the outputs context data, add an output step and construct the output metadata.
    outputs_context = context['outputs']
    basic_blocks.append(_compile_output_step(outputs_context))
    output_metadata = {
        name: OutputMetadata(type=value['type'], optional=value['optional'])
        for name, value in six.iteritems(outputs_context)
    }

    return IrAndMetadata(
        ir_blocks=basic_blocks,
        input_metadata=context['inputs'],
        output_metadata=output_metadata,
        location_types=context['location_types'],
        coerced_locations=context['coerced_locations'])


def _compile_output_step(outputs):
    """Construct the final ConstructResult basic block that defines the output format of the query.

    Args:
        outputs: dict, output name (string) -> output data dict, specifying the location
                 from where to get the data, and whether the data is optional (and therefore
                 may be missing); missing optional data is replaced with 'null'

    Returns:
        a ConstructResult basic block that constructs appropriate outputs for the query
    """
    if not outputs:
        raise GraphQLCompilationError(u'No fields were selected for output! Please mark at least '
                                      u'one field with the @output directive.')

    output_fields = {}
    for output_name, output_context in six.iteritems(outputs):
        location = output_context['location']
        optional = output_context['optional']
        graphql_type = output_context['type']
        fold_scope_location = output_context['fold']

        expression = None
        existence_check = None
        if fold_scope_location:
            if optional:
                raise AssertionError(u'Unreachable state reached, optional in fold: '
                                     u'{}'.format(output_context))

            _, field_name = location.get_location_name()
            expression = expressions.FoldedOutputContextField(
                fold_scope_location, field_name, graphql_type)
        else:
            expression = expressions.OutputContextField(location, graphql_type)

            if optional:
                existence_check = expressions.ContextFieldExistence(location.at_vertex())

        # pylint: disable=redefined-variable-type
        if existence_check:
            expression = expressions.TernaryConditional(
                existence_check, expression, expressions.NullLiteral)
        # pylint: enable=redefined-variable-type

        output_fields[output_name] = expression

    return blocks.ConstructResult(output_fields)


def _preprocess_graphql_string(graphql_string):
    """Apply any necessary preprocessing to the input GraphQL string, returning the new version."""
    # HACK(predrag): Workaround for graphql-core issue, to avoid needless errors:
    #                https://github.com/graphql-python/graphql-core/issues/98
    return graphql_string + '\n'


##############
# Public API #
##############

def graphql_to_ir(schema, graphql_string, type_equivalence_hints=None):
    """Convert the given GraphQL string into compiler IR, using the given schema object.

    Args:
        schema: GraphQL schema object, created using the GraphQL library
        graphql_string: string containing the GraphQL to compile to compiler IR
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for GraphQL's lack of support for
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
        IrAndMetadata named tuple, containing fields:
        - ir_blocks: a list of IR basic block objects
        - input_metadata: a dict of expected input parameters (string) -> inferred GraphQL type
        - output_metadata: a dict of output name (string) -> OutputMetadata object
        - location_types: a dict of location objects -> GraphQL type objects at that location

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
    graphql_string = _preprocess_graphql_string(graphql_string)
    try:
        ast = parse(graphql_string)
    except GraphQLSyntaxError as e:
        raise GraphQLParsingError(e)

    validation_errors = validate(schema, ast)

    if validation_errors:
        raise GraphQLValidationError(u'String does not validate: {}'.format(validation_errors))

    if len(ast.definitions) != 1:
        raise AssertionError(u'Unsupported graphql string with multiple definitions, should have '
                             u'been caught in validation: \n{}\n{}'.format(graphql_string, ast))
    base_ast = ast.definitions[0]

    return _compile_root_ast_to_ir(schema, base_ast, type_equivalence_hints=type_equivalence_hints)
