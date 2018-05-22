# Copyright 2017-present Kensho Technologies, LLC.
"""Helper functions for dealing with the frontend "context" object."""

from ..exceptions import GraphQLCompilationError


def is_in_fold_innermost_scope_scope(context):
    """Return True if the current context is within a scope marked @fold."""
    return 'fold_innermost_scope' in context


def is_in_fold_scope(context):
    """Return True if the current context is within a scope marked @fold."""
    return 'fold' in context


def is_in_optional_scope(context):
    """Return True if the current context is within a scope marked @optional."""
    return 'optional' in context


def has_encountered_output_source(context):
    """Return True if the current context has already encountered an @output_source directive."""
    return 'output_source' in context


def validate_context_for_visiting_vertex_field(location, context):
    """Ensure that the current context allows for visiting a vertex field."""
    if is_in_fold_innermost_scope_scope(context):
        raise GraphQLCompilationError(u'Traversing inside a @fold block after output is '
                                      u'not supported! Location: {}'.format(location))
