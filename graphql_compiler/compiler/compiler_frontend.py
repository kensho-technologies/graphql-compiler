# Copyright 2017 Kensho Technologies, Inc.
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

    step 1. apply @filter directive, if present on the current AST node
            (see _compile_ast_node_to_ir())

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
        - mark the current location in the query, since all @filter directives on this AST node
          have already been processed;
        - process the output_source directive, if it exists

    step V-4. Recurse into any vertex field children of the current AST node:
              (see _compile_vertex_ast())
        - before recursing into each vertex, process any @optional directive
          present on the child AST node;
        - after returning from each vertex, return to the marked query location using
          the appropriate manner, depending on whether @optional was present on the child or not.
    ***************

    *** F-steps ***
    step F-2. Emit an appropriate type coercion block, then recurse into the fragment's selection.
    ***************
"""
from collections import namedtuple

from graphql.error import GraphQLSyntaxError
from graphql.language.ast import Field, InlineFragment
from graphql.language.parser import parse
from graphql.type.definition import (GraphQLInterfaceType, GraphQLList, GraphQLObjectType,
                                     GraphQLUnionType)
from graphql.validation import validate

from . import blocks, expressions
from ..exceptions import GraphQLCompilationError, GraphQLParsingError, GraphQLValidationError
from .filters import process_filter_directive
from .helpers import (Location, get_ast_field_name, get_field_type_from_schema,
                      get_uniquely_named_objects_by_name, strip_non_null_from_type,
                      validate_safe_string)


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


def _get_directives(ast):
    """Return a dict of directive name to directive object for the given AST node.

    Also verifies that each directive is only present once on any given AST node,
    raising GraphQLCompilationError if that is not the case.

    Args:
        ast: GraphQL AST node, obtained from the graphql library

    Returns:
        dict of basestring to directive object, mapping directive names to their data
    """
    try:
        return get_uniquely_named_objects_by_name(ast.directives)
    except ValueError as e:
        raise GraphQLCompilationError(e)


def _is_vertex_field_name(field_name):
    """Return True if the field name denotes a vertex field, or False if it's a property field."""
    return field_name.startswith('out_') or field_name.startswith('in_')


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
        if _is_vertex_field_name(name):
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
                                     location, context, local_directives):
    """Process the output_source directive, modifying the context as appropriate.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library
        location: Location object representing the current location in the query
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        local_directives: dict, directive name string -> directive object, containing the
                          directives present on the current AST node *only*

    Returns:
        an OutputSource block, if one should be emitted, or None otherwise
    """
    # The 'ast' variable is only for function signature uniformity, and is currently not used.
    output_source_directive = local_directives.get('output_source', None)
    if output_source_directive:
        if 'output_source' in context:
            raise GraphQLCompilationError(u'Cannot have more than one output source!')
        if 'optional' in context:
            raise GraphQLCompilationError(u'Cannot have the output source in an optional block!')
        context['output_source'] = location
        return blocks.OutputSource()
    else:
        return None


vertex_only_directives = {'optional', 'output_source', 'recurse', 'fold'}
property_only_directives = {'tag', 'output'}
vertex_directives_prohibited_on_root = {'optional', 'recurse', 'fold'}

if not (vertex_directives_prohibited_on_root <= vertex_only_directives):
    raise AssertionError(u'The set of directives prohibited on the root vertex is not a subset '
                         u'of the set of vertex directives: {}'
                         u'{}'.format(vertex_directives_prohibited_on_root, vertex_only_directives))


def _validate_property_directives(directives):
    """Validate the directives that appear at a property field."""
    for directive_name in directives.iterkeys():
        if directive_name in vertex_only_directives:
            raise GraphQLCompilationError(
                u'Found vertex-only directive {} set on property.'.format(directive_name))


def _validate_vertex_directives(directives):
    """Validate the directives that appear at a vertex field."""
    for directive_name in directives.iterkeys():
        if directive_name in property_only_directives:
            raise GraphQLCompilationError(
                u'Found property-only directive {} set on vertex.'.format(directive_name))


def _compile_property_ast(schema, current_schema_type, ast, location, context, local_directives):
    """Process property directives at this AST node, updating the query context as appropriate.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library. Only for function signature
             uniformity at the moment -- it is currently not used.
        location: Location object representing the current location in the query
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        local_directives: dict, directive name string -> directive object, containing the
                          directives present on the current AST node *only*
    """
    _validate_property_directives(local_directives)
    is_in_fold = context.get('fold', None) is not None

    # step P-2: process property-only directives
    tag_directive = local_directives.get('tag', None)
    if tag_directive:
        if is_in_fold:
            raise GraphQLCompilationError(u'Tagging values within a @fold vertex field is '
                                          u'not allowed! Location: {}'.format(location))

        # Schema validation has ensured that the fields below exist.
        tag_name = tag_directive.arguments[0].value.value
        if tag_name in context['tags']:
            raise GraphQLCompilationError(u'Cannot reuse tag name: {}'.format(tag_name))
        validate_safe_string(tag_name)
        context['tags'][tag_name] = {
            'location': location,
            'optional': 'optional' in context,
            'type': strip_non_null_from_type(current_schema_type),
        }

    output_directive = local_directives.get('output', None)
    if output_directive:
        # Schema validation has ensured that the fields below exist.
        output_name = output_directive.arguments[0].value.value
        if output_name in context['outputs']:
            raise GraphQLCompilationError(u'Cannot reuse output name: '
                                          u'{}, {}'.format(output_name, context))
        validate_safe_string(output_name)

        graphql_type = strip_non_null_from_type(current_schema_type)
        if is_in_fold:
            graphql_type = GraphQLList(graphql_type)

        context['outputs'][output_name] = {
            'location': location,
            'optional': 'optional' in context,
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


def _validate_context_for_visiting_vertex_field(location, context):
    """Ensure that the current context allows for visiting a vertex field."""
    if 'optional' in context:
        raise GraphQLCompilationError(u'Traversing inside an optional block is currently not '
                                      u'supported! Location: {}'.format(location))

    if 'fold' in context:
        raise GraphQLCompilationError(u'Traversing inside a @fold block is not supported! '
                                      u'Location: {}'.format(location))

    if 'output_source' in context:
        raise GraphQLCompilationError(u'Found vertex field after the vertex marked '
                                      u'output source! Location: {}'.format(location))


def _validate_vertex_field_directive_interactions(location, directives):
    """Ensure that the specified vertex field directives are not mutually disallowed."""
    filter_directive = directives.get('filter', None)
    fold_directive = directives.get('fold', None)
    optional_directive = directives.get('optional', None)
    output_source_directive = directives.get('output_source', None)
    recurse_directive = directives.get('recurse', None)

    if filter_directive and fold_directive:
        raise GraphQLCompilationError(u'@filter and @fold may not appear at the same '
                                      u'vertex field! Location: {}'.format(location))

    if fold_directive and optional_directive:
        raise GraphQLCompilationError(u'@fold and @optional may not appear at the same '
                                      u'vertex field! Location: {}'.format(location))

    if fold_directive and output_source_directive:
        raise GraphQLCompilationError(u'@fold and @output_source may not appear at the same '
                                      u'vertex field! Location: {}'.format(location))

    if fold_directive and recurse_directive:
        raise GraphQLCompilationError(u'@fold and @recurse may not appear at the same '
                                      u'vertex field! Location: {}'.format(location))

    if optional_directive and output_source_directive:
        raise GraphQLCompilationError(u'@optional and @output_source may not appear at the same '
                                      u'vertex field! Location: {}'.format(location))

    if optional_directive and recurse_directive:
        raise GraphQLCompilationError(u'@optional and @recurse may not appear at the same '
                                      u'vertex field! Location: {}'.format(location))


def _compile_vertex_ast(schema, current_schema_type, ast,
                        location, context, local_directives, fields):
    """Return a list of basic blocks corresponding to the vertex AST node.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library
        location: Location object representing the current location in the query
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        local_directives: dict, directive name string -> directive object, containing the
                          directives present on the current AST node *only*
        fields: tuple of lists (property_fields, vertex_fields), with lists of field objects
                present on the current vertex AST node

    Returns:
        list of basic blocks, the compiled output of the vertex AST node
    """
    basic_blocks = []
    vertex_fields, property_fields = fields

    _validate_vertex_directives(local_directives)

    # step V-2: step into property fields
    for field_ast in property_fields:
        field_name = get_ast_field_name(field_ast)
        property_schema_type = get_field_type_from_schema(current_schema_type, field_name)

        inner_location = location.navigate_to_field(field_name)
        inner_basic_blocks = _compile_ast_node_to_ir(schema, property_schema_type, field_ast,
                                                     inner_location, context)
        basic_blocks.extend(inner_basic_blocks)

    # step V-3: mark the graph position, and process output_source directive
    if 'fold' not in context:
        # We only mark the position if we aren't in a folded scope.
        # Folded scopes don't actually traverse to the location, so it's never really visited.
        context['location_types'][location] = strip_non_null_from_type(current_schema_type)
        basic_blocks.append(_mark_location(location))

    output_source = _process_output_source_directive(schema, current_schema_type, ast,
                                                     location, context, local_directives)
    if output_source:
        basic_blocks.append(output_source)

    # step V-4: step into vertex fields
    for field_ast in vertex_fields:
        field_name = get_ast_field_name(field_ast)
        inner_location = location.navigate_to_subpath(field_name)
        _validate_context_for_visiting_vertex_field(inner_location, context)

        # The field itself is of type GraphQLList, and this is
        # what get_field_type_from_schema returns.
        # We care about what the type *inside* the list is,
        # i.e., the type on the other side of the edge (hence .of_type).
        # Validation guarantees that the field must exist in the schema.
        edge_schema_type = get_field_type_from_schema(current_schema_type, field_name)
        if not isinstance(strip_non_null_from_type(edge_schema_type), GraphQLList):
            raise AssertionError(u'Found an edge whose schema type was not GraphQLList: '
                                 u'{} {} {}'.format(current_schema_type, field_name,
                                                    edge_schema_type))
        field_schema_type = edge_schema_type.of_type

        inner_directives = _get_directives(field_ast)
        _validate_vertex_field_directive_interactions(inner_location, inner_directives)

        recurse_directive = inner_directives.get('recurse', None)
        optional_directive = inner_directives.get('optional', None)
        fold_directive = inner_directives.get('fold', None)
        in_topmost_optional_block = False

        edge_traversal_is_optional = optional_directive is not None
        if edge_traversal_is_optional:
            # Entering an optional block!
            # Make sure there's a tag right before it for the optional Backtrack to jump back to.
            # Otherwise, the traversal could rewind to an old tag and might ignore
            # entire stretches of applied filtering.
            if not isinstance(basic_blocks[-1], blocks.MarkLocation):
                location = location.revisit()
                context['location_types'][location] = strip_non_null_from_type(current_schema_type)
                basic_blocks.append(_mark_location(location))

            # Remember where the topmost optional context started.
            topmost_optional = context.get('optional', None)
            if topmost_optional is None:
                context['optional'] = inner_location
                in_topmost_optional_block = True

        edge_direction = None
        edge_name = None
        if field_name.startswith('out_'):
            edge_direction = 'out'
            edge_name = field_name[4:]
        elif field_name.startswith('in_'):
            edge_direction = 'in'
            edge_name = field_name[3:]
        else:
            raise AssertionError(u'Unreachable condition reached:', field_name)

        if fold_directive:
            context['fold'] = {
                'root': location,
                # If we allow folds deeper than a single level,
                # the below will need to become a list.
                'relative_position': (edge_direction, edge_name),
            }
        elif recurse_directive:
            recurse_depth = _get_recurse_directive_depth(field_name, inner_directives)
            _validate_recurse_directive_types(current_schema_type, field_schema_type)
            basic_blocks.append(blocks.Recurse(edge_direction, edge_name, recurse_depth))
        else:
            basic_blocks.append(blocks.Traverse(edge_direction, edge_name,
                                                optional=edge_traversal_is_optional))

        inner_basic_blocks = _compile_ast_node_to_ir(schema, field_schema_type, field_ast,
                                                     inner_location, context)
        basic_blocks.extend(inner_basic_blocks)

        if fold_directive:
            del context['fold']

        if in_topmost_optional_block:
            del context['optional']

        # If we are currently evaluating a @fold vertex,
        # we didn't Traverse into it, so we don't need to backtrack out either.
        # Alternatively, we don't backtrack if we've reached an @output_source.
        backtracking_required = (not fold_directive) and ('output_source' not in context)
        if backtracking_required:
            if optional_directive is not None:
                basic_blocks.append(blocks.Backtrack(location, optional=True))

                # Exiting optional block!
                # Add a tag right after the optional, to ensure future Backtrack blocks
                # return to a position after the optional set of blocks.
                location = location.revisit()
                context['location_types'][location] = strip_non_null_from_type(current_schema_type)
                basic_blocks.append(_mark_location(location))
            else:
                basic_blocks.append(blocks.Backtrack(location))

    return basic_blocks


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
    coerces_to_type_name = ast.type_condition.name.value
    coerces_to_type_obj = schema.get_type(coerces_to_type_name)

    # step F-2. Emit an appropriate type coercion block, then recurse into the fragment's selection.
    basic_blocks = [blocks.CoerceType({coerces_to_type_name})]
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
    local_directives = _get_directives(ast)
    fields = _get_fields(ast)
    vertex_fields, property_fields = fields
    fragment = _get_inline_fragment(ast)

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
    filter_directive = local_directives.get('filter', None)
    if filter_directive:
        if 'fold' in context:
            raise GraphQLCompilationError(u'Cannot apply filters inside a @fold vertex field! '
                                          u'Location: {}'.format(location))

        basic_blocks.append(
            process_filter_directive(schema, current_schema_type,
                                     ast, context, filter_directive))

    if location.field is not None:
        # The location is at a property, compile the property data following P-steps.
        _compile_property_ast(schema, current_schema_type, ast,
                              location, context, local_directives)
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
                                    location, context, local_directives, fields))

    return basic_blocks


def _compile_root_ast_to_ir(schema, ast):
    """Compile a full GraphQL abstract syntax tree (AST) to intermediate representation.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        ast: the root GraphQL AST node for the query, obtained from the graphql library,
             and already validated against the schema for type-correctness

    Returns:
        tuple of:
        - a list of IR basic block objects
        - a dict of output name (basestring) -> OutputMetadata object
        - a dict of expected input parameters (basestring) -> inferred GraphQL type, based on use
        - a dict of location objects -> GraphQL type objects at that location
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
        'tags': dict(),
        'outputs': dict(),
        'inputs': dict(),
        'location_types': dict(),
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
    directives_present_at_root = set(_get_directives(base_ast).iterkeys())
    disallowed_directives = directives_present_at_root & vertex_directives_prohibited_on_root
    if disallowed_directives:
        raise GraphQLCompilationError(u'Found prohibited directives on root vertex: '
                                      u'{}'.format(disallowed_directives))

    # Compile and add the basic blocks for the query's base AST vertex.
    new_basic_blocks = _compile_ast_node_to_ir(
        schema, current_schema_type, base_ast, location, context)
    basic_blocks.extend(new_basic_blocks)

    # Based on the outputs context data, add an output step and construct the output metadata.
    outputs_context = context['outputs']
    basic_blocks.append(_compile_output_step(outputs_context))
    output_metadata = {
        name: OutputMetadata(type=value['type'], optional=value['optional'])
        for name, value in outputs_context.iteritems()
    }

    return basic_blocks, output_metadata, context['inputs'], context['location_types']


def _compile_output_step(outputs):
    """Construct the final ConstructResult basic block that defines the output format of the query.

    Args:
        outputs: dict, output name (basestring) -> output data dict, specifying the location
                 from where to get the data, and whether the data is optional (and therefore
                 may be missing); missing optional data is replaced with 'null'

    Returns:
        a ConstructResult basic block that constructs appropriate outputs for the query
    """
    if not outputs:
        raise GraphQLCompilationError(u'No fields were selected for output! Please mark at least '
                                      u'one field with the @output directive.')

    output_fields = {}
    for output_name, output_context in outputs.iteritems():
        location = output_context['location']
        optional = output_context['optional']
        graphql_type = output_context['type']
        fold_data = output_context['fold']

        expression = None
        if fold_data:
            if optional:
                raise AssertionError(u'Unreachable state reached, optional in fold: '
                                     u'{}'.format(output_context))

            _, field_name = location.get_location_name()
            expression = expressions.FoldedOutputContextField(
                fold_data['root'], fold_data['relative_position'], field_name, graphql_type)
        else:
            expression = expressions.OutputContextField(location, graphql_type)

            if optional:
                existence_check = expressions.ContextFieldExistence(location.at_vertex())
                expression = expressions.TernaryConditional(
                    existence_check, expression, expressions.NullLiteral)

        output_fields[output_name] = expression

    return blocks.ConstructResult(output_fields)


##############
# Public API #
##############

def graphql_to_ir(schema, graphql_string):
    """Convert the given GraphQL string into compiler IR, using the given schema object.

    Args:
        schema: GraphQL schema object, created using the GraphQL library
        graphql_string: basestring containing the GraphQL to compile to compiler IR

    Returns:
        tuple of:
        - a list of IR basic block objects
        - a dict of output name (basestring) -> OutputMetadata object
        - a dict of expected input parameters (basestring) -> inferred GraphQL type, based on use
        - a dict of location objects -> GraphQL type objects at that location

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

    return _compile_root_ast_to_ir(schema, base_ast)
