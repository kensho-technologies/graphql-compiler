# Copyright 2019-present Kensho Technologies, LLC.
"""Convert lowered IR basic blocks to Cypher query strings."""
from graphql_compiler.compiler.helpers import FoldScopeLocation, Location
from .blocks import Fold, QueryRoot, Recurse, Traverse
from .cypher_query import _make_cypher_step


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
                             u'it should have moved the filtering to the global operations '
                             u'section. {}'.format(cypher_step))

    is_fold_step = isinstance(cypher_step.as_block.location, FoldScopeLocation)  # CypherStep generated from within a fold scope.

    step_location = cypher_step.as_block.location
    if is_fold_step:
        # Then step_location is a FoldScopeLocation and we want the full path in the location name.
        step_location_name = step_location.get_full_path_location_name()
    else:
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
            u'%(left_edge_mark)s-[:%(edge_type)s%(quantifier)s]-%(right_edge_mark)s' +
            step_vertex_pattern
        )
        if isinstance(cypher_step.linked_location, FoldScopeLocation):
            # If this is the first CypherStep object in a fold scope, then linked_location will
            # be a Location and not a FoldScopeLocation. Therefore we need to check the type for
            # linked_location and not if this is within a fold scope.
            linked_location_name = cypher_step.linked_location.get_full_path_location_name()
        else:
            linked_location_name, _ = cypher_step.linked_location.get_location_name()
        template_data['linked_location'] = linked_location_name

    if has_where_block:
        pattern += u'\n  WHERE %(predicate)s'
        template_data['predicate'] = cypher_step.where_block.predicate.to_cypher()

    if is_optional_step or is_fold_step:
        # OPTIONAL for fold too because if there is no such path for the given fold traversal, we still want to return an empty list. Without OPTIONAL, the entire row would be missing from the output
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
        direction_symbol_name, direction_symbol = direction_lookup[direction]
        template_data[direction_symbol_name] = direction_symbol

    if isinstance(cypher_step.step_block, Recurse):
        template_data['quantifier'] = u'*0..%d' % cypher_step.step_block.depth

    # Comply with Cypher style guidebook on whitespace a bit.
    pattern += u'\n'

    return pattern % template_data


def _emit_with_clause_components(cypher_steps):
    """Emit the component strings of the Cypher WITH clause with the provided Cypher steps."""
    if not cypher_steps:
        return []

    result = [u'WITH']
    location_names = set()
    for cypher_step in cypher_steps:
        location = cypher_step.as_block.location
        if isinstance(location, Location):
            location_name = location.get_location_name()[0]
        else:
            # must be a FoldScopeLocation because as_block is a MarkLocation block.
            location_name = u'collected_' + location.get_full_path_location_name()
        location_names.add(location_name)

    # Sort the locations, to ensure a deterministic order.
    for index, location_name in enumerate(sorted(location_names)):
        if index > 0:
            result.append(u',')

        # We intentionally "rename" each location to its own name, to work around a limitation
        # in RedisGraph where un-aliased "WITH" clauses are not supported:
        # https://oss.redislabs.com/redisgraph/known_limitations/#unaliased-with-entities
        result.append(u'\n  %(name)s AS %(name)s' % {'name': location_name})

    return result


def _emit_with_clause_components_for_current_fold_scope(current_fold_scope_cyphersteps):
    """Emit the component strings for Cypher WITH clause for current fold."""
    # At this point we should already have emitted all component strings from previous CypherSteps,
    # whether or not they were in fold scopes or not.
    result = []

    vertex_names = {}
    for cypher_step in current_fold_scope_cyphersteps:
        fold_scope_location = cypher_step.as_block.location
        full_vertex_name = fold_scope_location.get_full_path_location_name()
        vertex_names[u'collect(' + full_vertex_name + ')'] = u'collected_' + full_vertex_name

    # Sort the locations, to ensure a deterministic order.
    for index, collect_call in enumerate(sorted(vertex_names)):
        # haha get it? collect_call because we're calling the function collect()?
        if index > 0:
            result.append(u',')
        result.append(u'\n  %(collect_call)s AS %(collected_name)s' %
                      {'collect_call': collect_call, 'collected_name': vertex_names[collect_call]})
    return result


def _emit_fold_scope(cypher_query):
    """Return a Cypher query pattern match expression for each fold scope in cypher_query."""
    query_data = []
    previous_fold_scope_cypher_steps = []
    for fold_scope_location in cypher_query.folds:
        current_fold_scope_cyphersteps = cypher_query.folds[fold_scope_location]
        for cypher_step in current_fold_scope_cyphersteps:
            query_data.append(_emit_code_from_cypher_step(cypher_step))
        # Now create the WITH clause, first for all non-fold-scope CypherSteps
        query_data.extend(_emit_with_clause_components(cypher_query.steps))

        # And then for all fold scope CypherSteps not in this particular fold scope
        if previous_fold_scope_cypher_steps:
            query_data.append(u',')
        query_data.extend(_emit_with_clause_components(previous_fold_scope_cypher_steps))

        # And finally for all current fold scope CypherSteps
        if current_fold_scope_cyphersteps:
            query_data.append(u',')
        query_data.extend(_emit_with_clause_components_for_current_fold_scope(current_fold_scope_cyphersteps))

        query_data.append(u'\n')

        # Now that we've finished out this fold scope, we need to ensure these vertices get
        # passed on through all later WITH clauses as well.
        previous_fold_scope_cypher_steps.extend(current_fold_scope_cyphersteps)
    return query_data

##############
# Public API #
##############


def emit_code_from_ir(cypher_query, compiler_metadata):
    """Return a Cypher query string from a CypherQuery object."""
    # According to the Cypher Query Language Reference [0], the standard Cypher version is
    # Cypher 9 (page 196) and we should be able to specify the Cypher version in the query.
    # Unfortunately, this turns out to be invalid in both Neo4j and RedisGraph-- Neo4j supports
    # Cypher version 2.3, 3.4, and 3.5 [1] while Redisgraph doesn't support the syntax at all [2].
    # When this does eventually get resolved, we can change `query_data` back to `[u'CYPHER 9']`
    # [0] https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf
    # [1] https://github.com/neo4j/neo4j/issues/12239
    # [2] https://github.com/RedisGraph/RedisGraph/issues/552
    query_data = [u'']

    for cypher_step in cypher_query.steps:
        query_data.append(_emit_code_from_cypher_step(cypher_step))

    if cypher_query.folds:
        query_data.extend(_emit_fold_scope(cypher_query))

    if cypher_query.global_where_block is not None:
        query_data.extend(_emit_with_clause_components(cypher_query.steps))

        query_data.append(u'WHERE ')
        query_data.append(cypher_query.global_where_block.predicate.to_cypher())
        query_data.append(u'\n')

    query_data.append(u'RETURN')
    output_fields = cypher_query.output_block.fields
    sorted_output_keys = sorted(output_fields.keys())
    break_and_indent = u'\n  '
    for output_index, output_name in enumerate(sorted_output_keys):
        if output_index > 0:
            query_data.append(u',')

        output_expression = output_fields[output_name]
        query_data.append(break_and_indent)
        query_data.append(u'%s AS `%s`' % (output_expression.to_cypher(), output_name))

    return u''.join(query_data)
