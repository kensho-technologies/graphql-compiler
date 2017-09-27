# Copyright 2017 Kensho Technologies, Inc.
"""Helper functions for dealing with GraphQL directives."""

import six

from ..exceptions import GraphQLCompilationError


ALLOWED_DUPLICATED_DIRECTIVES = frozenset({'filter'})
VERTEX_ONLY_DIRECTIVES = frozenset({'optional', 'output_source', 'recurse', 'fold'})
PROPERTY_ONLY_DIRECTIVES = frozenset({'tag', 'output'})
VERTEX_DIRECTIVES_PROHIBITED_ON_ROOT = frozenset({'optional', 'recurse', 'fold'})


if not (VERTEX_DIRECTIVES_PROHIBITED_ON_ROOT <= VERTEX_ONLY_DIRECTIVES):
    raise AssertionError(u'The set of directives prohibited on the root vertex is not a subset '
                         u'of the set of vertex directives: {}'
                         u'{}'.format(VERTEX_DIRECTIVES_PROHIBITED_ON_ROOT, VERTEX_ONLY_DIRECTIVES))


def get_directives(ast):
    """Return a dict of directive name to directive object for the given AST node.

    Also verifies that each directive is only present once on any given AST node,
    raising GraphQLCompilationError if that is not the case.

    Args:
        ast: GraphQL AST node, obtained from the graphql library

    Returns:
        dict of string to:
        - directive object, if the directive is only allowed to appear at most once, or
        - list of directive objects, if the directive is allowed to appear multiple times
    """
    if not ast.directives:
        return dict()

    result = dict()
    for directive_obj in ast.directives:
        directive_name = directive_obj.name.value
        if directive_name in ALLOWED_DUPLICATED_DIRECTIVES:
            result.setdefault(directive_name, []).append(directive_obj)
        elif directive_name in result:
            raise GraphQLCompilationError(u'Directive was unexpectedly applied twice in the same '
                                          u'location: {} {}'.format(directive_name, ast.directives))
        else:
            result[directive_name] = directive_obj

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


def validate_root_vertex_directives(directives):
    """Validate the directives that appear at the root vertex field."""
    directives_present_at_root = set(six.iterkeys(directives))
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
