# Copyright 2017-present Kensho Technologies, LLC.
"""Helper functions for dealing with the frontend "context" object."""

from ..exceptions import GraphQLCompilationError
from ..schema import COUNT_META_FIELD_NAME


CONTEXT_FOLD_INNERMOST_SCOPE = "fold_innermost_scope"
CONTEXT_FOLD_HAS_COUNT_FILTER = "fold_has_count_filter"
CONTEXT_FOLD = "fold"
CONTEXT_OPTIONAL = "optional"
CONTEXT_OUTPUT_SOURCE = "output_source"


def is_in_fold_innermost_scope(context):
    """Return True if the current context is within a scope marked @fold."""
    return CONTEXT_FOLD_INNERMOST_SCOPE in context


def unmark_fold_innermost_scope(context):
    """Remove the context mark signaling an innermost fold scope."""
    del context[CONTEXT_FOLD_INNERMOST_SCOPE]


def set_fold_innermost_scope(context):
    """Set a mark indicating the innermost scope of a fold scope."""
    context[CONTEXT_FOLD_INNERMOST_SCOPE] = True


def is_in_fold_scope(context):
    """Return True if the current context is within a scope marked @fold."""
    return CONTEXT_FOLD in context


def get_context_fold_info(context):
    """Return the fold info stored in the context."""
    return context[CONTEXT_FOLD]


def unmark_context_fold_scope(context):
    """Return the context mark signaling the presence of a scope marked @fold."""
    del context[CONTEXT_FOLD]


def set_fold_scope_data(context, data):
    """Set fold scope data in the context."""
    context[CONTEXT_FOLD] = data


def has_fold_count_filter(context):
    """Return True if the current context contains a filter on the _x_count field."""
    return CONTEXT_FOLD_HAS_COUNT_FILTER in context


def unmark_fold_count_filter(context):
    """Remove the context mark signaling the existence of a fold count filter."""
    del context[CONTEXT_FOLD_HAS_COUNT_FILTER]


def set_fold_count_filter(context):
    """Set a mark indicating the presence of a filter on a fold _x_count field."""
    context[CONTEXT_FOLD_HAS_COUNT_FILTER] = True


def is_in_optional_scope(context):
    """Return True if the current context is within a scope marked @optional."""
    return CONTEXT_OPTIONAL in context


def get_optional_scope_or_none(context):
    """Return the optional scope data recorded in the context, or None if no such data."""
    return context.get(CONTEXT_OPTIONAL, None)


def set_optional_scope_data(context, data):
    """Set optional scope data in the context."""
    context[CONTEXT_OPTIONAL] = data


def unmark_optional_scope(context):
    """Remove the context mark signaling the existence of an optional scope."""
    del context[CONTEXT_OPTIONAL]


def set_output_source_data(context, data):
    """Set output source data in the context."""
    context[CONTEXT_OUTPUT_SOURCE] = data


def has_encountered_output_source(context):
    """Return True if the current context has already encountered an @output_source directive."""
    return CONTEXT_OUTPUT_SOURCE in context


def validate_context_for_visiting_vertex_field(parent_location, vertex_field_name, context):
    """Ensure that the current context allows for visiting a vertex field."""
    if is_in_fold_innermost_scope(context):
        raise GraphQLCompilationError(
            "Traversing inside a @fold block after filtering on {} or outputting fields "
            "is not supported! Parent location: {}, vertex field name: {}".format(
                COUNT_META_FIELD_NAME, parent_location, vertex_field_name
            )
        )
