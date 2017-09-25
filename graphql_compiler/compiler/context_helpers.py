# Copyright 2017 Kensho Technologies, Inc.
"""Helper functions for dealing with the frontend "context" object."""

from ..exceptions import GraphQLCompilationError


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
    if is_in_optional_scope(context):
        raise GraphQLCompilationError(u'Traversing inside an optional block is currently not '
                                      u'supported! Location: {}'.format(location))

    if is_in_fold_scope(context):
        raise GraphQLCompilationError(u'Traversing inside a @fold block is not supported! '
                                      u'Location: {}'.format(location))

    if has_encountered_output_source(context):
        raise GraphQLCompilationError(u'Found vertex field after the vertex marked '
                                      u'output source! Location: {}'.format(location))
