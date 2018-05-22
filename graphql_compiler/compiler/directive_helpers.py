# Copyright 2017-present Kensho Technologies, LLC.
"""Helper functions for dealing with GraphQL directives."""

from graphql.language.ast import InlineFragment
import six

from ..exceptions import GraphQLCompilationError
from .filters import is_filter_with_outer_scope_vertex_field_operator
from .helpers import (FilterOperationInfo, get_ast_field_name, get_ast_field_name_or_none,
                      get_vertex_field_type, is_vertex_field_type)


ALLOWED_DUPLICATED_DIRECTIVES = frozenset({'filter'})
VERTEX_ONLY_DIRECTIVES = frozenset({'optional', 'output_source', 'recurse', 'fold'})
PROPERTY_ONLY_DIRECTIVES = frozenset({'tag', 'output'})
VERTEX_DIRECTIVES_PROHIBITED_ON_ROOT = frozenset({'optional', 'recurse', 'fold'})


if not (VERTEX_DIRECTIVES_PROHIBITED_ON_ROOT <= VERTEX_ONLY_DIRECTIVES):
    raise AssertionError(u'The set of directives prohibited on the root vertex is not a subset '
                         u'of the set of vertex directives: {}'
                         u'{}'.format(VERTEX_DIRECTIVES_PROHIBITED_ON_ROOT, VERTEX_ONLY_DIRECTIVES))


def get_unique_directives(ast):
    """Return a dict of directive name to directive object for the given AST node.

    Any directives that are allowed to exist more than once on any AST node are ignored.
    For any directives that can only exist up to once, we verify that they are not duplicated
    raising GraphQLCompilationError in case we find them more than once on the AST node.

    Args:
        ast: GraphQL AST node, obtained from the graphql library

    Returns:
        dict of string to directive object
    """
    if not ast.directives:
        return dict()

    result = dict()
    for directive_obj in ast.directives:
        directive_name = directive_obj.name.value
        if directive_name in ALLOWED_DUPLICATED_DIRECTIVES:
            pass  # We don't return these.
        elif directive_name in result:
            raise GraphQLCompilationError(u'Directive was unexpectedly applied twice in the same '
                                          u'location: {} {}'.format(directive_name, ast.directives))
        else:
            result[directive_name] = directive_obj

    return result


def get_local_filter_directives(ast, current_schema_type, inner_vertex_fields):
    """Get all filter directives that apply to the current field.

    This helper abstracts away the fact that some vertex field filtering operators apply on the
    inner scope (the scope of the inner vertex field on which they are applied), whereas some apply
    on the outer scope (the scope that contains the inner vertex field).
    See filters.py for more information.

    Args:
        ast: a GraphQL AST object for which to load local filters, from the graphql library
        current_schema_type: GraphQLType, the schema type at the current AST location
        inner_vertex_fields: a list of inner AST objects representing vertex fields that are within
                             the current field. If currently processing a property field (i.e.
                             there are no inner vertex fields), this argument may be set to None.

    Returns:
        list of FilterOperationInfo objects.
        If the field_ast field is of type InlineFragment, the field_name field is set to None.
    """
    result = []
    if ast.directives:  # it'll be None if the AST has no directives at that node
        for directive_obj in ast.directives:
            # Of all filters that appear *on the field itself*, only the ones that apply
            # to the outer scope are not considered "local" and are not to be returned.
            if directive_obj.name.value == 'filter':
                filtered_field_name = get_ast_field_name_or_none(ast)
                if is_filter_with_outer_scope_vertex_field_operator(directive_obj):
                    # We found a filter that affects the outer scope vertex. Let's make sure
                    # we are at a vertex field. If we are actually at a property field,
                    # that is a compilation error.
                    if not is_vertex_field_type(current_schema_type):
                        raise GraphQLCompilationError(
                            u'Found disallowed filter on a property field: {} {} '
                            u'{}'.format(directive_obj, current_schema_type, filtered_field_name))
                    elif isinstance(ast, InlineFragment):
                        raise GraphQLCompilationError(
                            u'Found disallowed filter on a type coercion: {} '
                            u'{}'.format(directive_obj, current_schema_type))
                    else:
                        # The filter is valid and non-local, since it is applied at this AST node
                        # but affects the outer scope vertex field. Skip over it.
                        pass
                else:
                    operation = FilterOperationInfo(
                        directive=directive_obj, field_name=filtered_field_name,
                        field_type=current_schema_type, field_ast=ast)
                    result.append(operation)

    if inner_vertex_fields:  # allow the argument to be None
        for inner_ast in inner_vertex_fields:
            for directive_obj in inner_ast.directives:
                # Of all filters that appear on an inner vertex field, only the ones that apply
                # to the outer scope are "local" to the outer field and therefore to be returned.
                if is_filter_with_outer_scope_vertex_field_operator(directive_obj):
                    # The inner AST must not be an InlineFragment, so it must have a field name.
                    filtered_field_name = get_ast_field_name(inner_ast)
                    filtered_field_type = get_vertex_field_type(
                        current_schema_type, filtered_field_name)

                    operation = FilterOperationInfo(
                        directive=directive_obj, field_name=filtered_field_name,
                        field_type=filtered_field_type, field_ast=inner_ast)
                    result.append(operation)

    return result


def validate_property_directives(directives):
    """Validate the directives that appear at a property field."""
    for directive_name in six.iterkeys(directives):
        if directive_name in VERTEX_ONLY_DIRECTIVES:
            raise GraphQLCompilationError(
                u'Found vertex-only directive {} set on property.'.format(directive_name))


def validate_vertex_directives(directives):
    """Validate the directives that appear at a vertex field."""
    for directive_name in six.iterkeys(directives):
        if directive_name in PROPERTY_ONLY_DIRECTIVES:
            raise GraphQLCompilationError(
                u'Found property-only directive {} set on vertex.'.format(directive_name))


def validate_root_vertex_directives(root_ast):
    """Validate the directives that appear at the root vertex field."""
    directives_present_at_root = set()
    for directive_obj in root_ast.directives:
        directive_name = directive_obj.name.value

        if is_filter_with_outer_scope_vertex_field_operator(directive_obj):
            raise GraphQLCompilationError(u'Found a filter directive with an operator that is not'
                                          u'allowed on the root vertex: {}'.format(directive_obj))

        directives_present_at_root.add(directive_name)

    disallowed_directives = directives_present_at_root & VERTEX_DIRECTIVES_PROHIBITED_ON_ROOT
    if disallowed_directives:
        raise GraphQLCompilationError(u'Found prohibited directives on root vertex: '
                                      u'{}'.format(disallowed_directives))


def validate_vertex_field_directive_interactions(location, directives):
    """Ensure that the specified vertex field directives are not mutually disallowed."""
    fold_directive = directives.get('fold', None)
    optional_directive = directives.get('optional', None)
    output_source_directive = directives.get('output_source', None)
    recurse_directive = directives.get('recurse', None)

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


def validate_vertex_field_directive_in_context(location, directives, context):
    """Ensure that the specified vertex field directives are allowed in the current context."""
    fold_directive = directives.get('fold', None)
    optional_directive = directives.get('optional', None)
    recurse_directive = directives.get('recurse', None)
    output_source_directive = directives.get('output_source', None)

    fold_context = 'fold' in context
    optional_context = 'optional' in context
    output_source_context = 'output_source' in context

    if fold_directive and fold_context:
        raise GraphQLCompilationError(u'@fold is not allowed within a @fold traversal! '
                                      u'Location: {}'.format(location))
    if optional_directive and fold_context:
        raise GraphQLCompilationError(u'@optional is not allowed within a @fold traversal! '
                                      u'Location: {}'.format(location))
    if output_source_directive and fold_context:
        raise GraphQLCompilationError(u'@output_source is not allowed within a @fold traversal! '
                                      u'Location: {}'.format(location))
    if recurse_directive and fold_context:
        raise GraphQLCompilationError(u'@recurse is not allowed within a @fold traversal! '
                                      u'Location: {}'.format(location))

    if output_source_context and not fold_directive:
        raise GraphQLCompilationError(u'Found non-fold vertex field after the vertex marked '
                                      u'output source! Location: {}'.format(location))
    if optional_context and optional_directive:
        raise GraphQLCompilationError(u'@optional is not allowed within a @optional traversal! '
                                      u'Location: {}'.format(location))
    if optional_context and fold_directive:
        raise GraphQLCompilationError(u'@fold is not allowed within a @optional traversal! '
                                      u'Location: {}'.format(location))
    if optional_context and output_source_directive:
        raise GraphQLCompilationError(u'@output_source is not allowed within a @optional '
                                      u'traversal! Location: {}'.format(location))
