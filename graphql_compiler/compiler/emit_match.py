# Copyright 2017 Kensho Technologies, Inc.
"""Convert lowered IR basic blocks to MATCH query strings."""
from collections import deque

from .blocks import QueryRoot, Recurse, Traverse


def _get_vertex_location_name(location):
    """Get the location name from a location that is expected to point to a vertex."""
    mark_name, field_name = location.get_location_name()
    if field_name is not None:
        raise AssertionError(u'Location unexpectedly pointed to a field: {}'.format(location))

    return mark_name


def _first_step_to_match(match_step):
    """Transform the very first MATCH step into a MATCH query string."""
    if not isinstance(match_step.root_block, QueryRoot):
        raise AssertionError(u'Expected QueryRoot root block, received: '
                             u'{} {}'.format(match_step.root_block, match_step))

    match_step.root_block.validate()

    start_class_set = match_step.root_block.start_class
    if len(start_class_set) != 1:
        raise AssertionError(u'Attempted to emit MATCH but did not have exactly one start class: '
                             u'{} {}'.format(start_class_set, match_step))
    start_class = list(start_class_set)[0]

    # MATCH steps with a QueryRoot root block shouldn't have a 'coerce_type_block'.
    if match_step.coerce_type_block is not None:
        raise AssertionError(u'Invalid MATCH step: {}'.format(match_step))

    parts = [
        u'class: %s' % (start_class,),
    ]

    if match_step.where_block:
        match_step.where_block.validate()
        parts.append(u'where: (%s)' % (match_step.where_block.predicate.to_match(),))

    if match_step.as_block:
        match_step.as_block.validate()
        parts.append(u'as: %s' % (_get_vertex_location_name(match_step.as_block.location),))

    return u'{{ %s }}' % (u', '.join(parts),)


def _subsequent_step_to_match(match_step):
    """Transform any subsequent (non-first) MATCH step into a MATCH query string."""
    if not isinstance(match_step.root_block, (Traverse, Recurse)):
        raise AssertionError(u'Expected Traverse root block, received: '
                             u'{} {}'.format(match_step.root_block, match_step))

    is_recursing = isinstance(match_step.root_block, Recurse)

    match_step.root_block.validate()

    traversal_command = u'.%s(\'%s\')' % (match_step.root_block.direction,
                                          match_step.root_block.edge_name)

    parts = []
    if match_step.coerce_type_block:
        if is_recursing:
            raise AssertionError(u'Found MATCH type coercion block within Recurse step: '
                                 u'{}'.format(match_step))

        coerce_type_set = match_step.coerce_type_block.target_class
        if len(coerce_type_set) != 1:
            raise AssertionError(u'Found MATCH type coercion block with more than one target class:'
                                 u' {} {}'.format(coerce_type_set, match_step))
        coerce_type_target = list(coerce_type_set)[0]
        parts.append(u'class: %s' % (coerce_type_target,))

    if is_recursing:
        # In MATCH, "$depth < 1" means "include the source vertex and its immediate neighbors."
        # Yes, the "<" is intentional -- it's not supposed to be a "<=".
        parts.append(u'while: ($depth < %d)' % (match_step.root_block.depth,))

    if match_step.where_block:
        match_step.where_block.validate()
        parts.append(u'where: (%s)' % (match_step.where_block.predicate.to_match(),))

    if not is_recursing and match_step.root_block.optional:
        parts.append(u'optional: true')

    if match_step.as_block:
        match_step.as_block.validate()
        parts.append(u'as: %s' % (_get_vertex_location_name(match_step.as_block.location),))

    return u'%s {{ %s }}' % (traversal_command, u', '.join(parts))


def _represent_match_traversal(match_traversal):
    """Emit MATCH query code for an entire MATCH traversal sequence."""
    output = []

    output.append(_first_step_to_match(match_traversal[0]))
    for step in match_traversal[1:]:
        output.append(_subsequent_step_to_match(step))

    return u''.join(output)


def _construct_output_to_match(output_block):
    """Transform a ConstructResult block into a MATCH query string."""
    output_block.validate()

    selections = (
        u'%s AS `%s`' % (output_block.fields[key].to_match(), key)
        for key in sorted(output_block.fields.keys())  # Sort keys for deterministic output order.
    )

    return u'SELECT %s FROM' % (u', '.join(selections),)


##############
# Public API #
##############

def emit_code_from_ir(match_query):
    """Return a MATCH query string from a list of IR blocks."""
    query_data = deque([u'MATCH '])

    if not match_query.match_traversals:
        raise AssertionError(u'Unexpected falsy value for match_query.match_traversals received: '
                             u'{} {}'.format(match_query.match_traversals, match_query))

    match_traversal_data = [
        _represent_match_traversal(x)
        for x in match_query.match_traversals
    ]

    query_data.append(match_traversal_data[0])
    for traversal_data in match_traversal_data[1:]:
        query_data.append(u', ')
        query_data.append(traversal_data)

    query_data.appendleft(u' (')            # Prepare to wrap the MATCH in a SELECT.
    query_data.append(u'RETURN $matches)')  # Finish the MATCH query and the wrapping ().
    query_data.appendleft(_construct_output_to_match(match_query.output_block))

    return u' '.join(query_data)
