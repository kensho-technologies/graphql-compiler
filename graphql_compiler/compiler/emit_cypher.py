# Copyright 2019-present Kensho Technologies, LLC.
"""Convert lowered IR basic blocks to Cypher query strings."""
from .blocks import QueryRoot, Recurse, Traverse
from .helpers import get_only_element_from_collection


def _emit_code_from_cypher_step(cypher_step):
    """Return a Cypher query pattern match expression corresponding to the given CypherStep."""
    no_linked_location = cypher_step.linked_location is None
    step_is_query_root = isinstance(cypher_step.step_block, QueryRoot)

    if no_linked_location ^ step_is_query_root:
        raise AssertionError(u'Received an illegal CypherStep. Not having a linked location is '
                             u'allowed if and only if the step is with a QueryRoot object. {}'
                             .format(cypher_step))

    has_where_block = cypher_step.where_block is not None
    is_optional_step = (
        isinstance(cypher_step.step_block, Traverse) and
        cypher_step.step_block.optional
    )
    if has_where_block and is_optional_step:
        raise AssertionError(u'Received an illegal CypherStep containing an optional step together '
                             u'with a "where" Filter block. This is a bug in the lowering code, as '
                             u'it should have moved the filtering to the global operations section.'
                             u'{}'.format(cypher_step))

    step_location = cypher_step.as_block.location
    step_location_name, _ = step_location.get_location_name()

    template_data = {
        'step_location': step_location_name,
        'step_vertex_type': u':'.join(sorted(cypher_step.step_types)),
        'quantifier': u'',
        'left_edge_mark': u'',
        'right_edge_mark': u'',
    }
    step_vertex_pattern = u'(%(step_location)s:%(step_vertex_type)s)'

    if cypher_step.linked_location is None:
        pattern = u'MATCH ' + step_vertex_pattern
    else:
        pattern = (
            u'MATCH (%(linked_location)s)'
            u'%(left_edge_mark)s-[%(quantifier)s:%(edge_type)s]-%(right_edge_mark)s' +
            step_vertex_pattern
        )

    if has_where_block:
        pattern += u'\n  WHERE %(predicate)s'
        template_data['predicate'] = cypher_step.where_block.predicate.to_cypher()

    if is_optional_step:
        pattern = u'OPTIONAL ' + pattern

    if isinstance(cypher_step.step_block, (Traverse, Recurse, Fold)):
        if isinstance(cypher_step.step_block, Fold):
            direction, edge_name = cypher_step.step_block.fold_scope_location.fold_path[0]
        else:
            direction = cypher_step.step_block.direction
            edge_name = cypher_step.step_block.edge_name

        template_data['edge_type'] = edge_name

        direction_lookup = {
            'in': ('left_edge_mark', u'<'),
            'out': ('right_edge_mark', u'>'),
        }
        key, value = direction_lookup[direction]
        template_data[key] = value

    if isinstance(cypher_step.step_block, Recurse):
        template_data['quantifier'] = u'*0..%d' % cypher_step.step_block.depth

    # Try to obey the Cypher style guidebook at least a little bit.
    pattern += u'\n'

    return pattern % template_data


##############
# Public API #
##############

def emit_code_from_ir(cypher_query, compiler_metadata):
    """Return a Cypher query string from a CypherQuery object."""
    query_data = [u'CYPHER 9\n']

    for cypher_step in cypher_query.steps:
        query_data.append(_emit_code_from_cypher_step(cypher_step))

    if cypher_query.folds:
        raise NotImplementedError()

    if cypher_query.global_where_block is not None:
        query_data.append(_emit_with_clause(cypher_query.steps))

        query_data.append(u'WHERE ')
        query_data.append(cypher_query.global_where_block.predicate.to_cypher())
        query_data.append(u'\n')

    query_data.append(u'RETURN')
    output_fields = cypher_query.output_block.fields
    sorted_output_keys = sorted(output_fields.keys())
    break_and_indent = u'\n  '
    for output_name in sorted_output_keys:
        output_expression = output_fields[output_name]
        query_data.append(break_and_indent)
        query_data.append(u'%s AS `%s' % (output_expression.to_cypher(), output_name))

    return u''.join(query_data)
