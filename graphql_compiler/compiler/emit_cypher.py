# Copyright 2019-present Kensho Technologies, LLC.
"""Convert lowered IR basic blocks to Cypher query strings."""
from itertools import chain

from . import cypher_helpers
from .blocks import Fold, QueryRoot, Recurse, Traverse
from .cypher_query import CypherStep
from .helpers import FoldScopeLocation


def _emit_code_from_cypher_step(cypher_step):
    """Return a Cypher query pattern match expression corresponding to the given CypherStep."""
    no_linked_location = cypher_step.linked_location is None
    step_is_query_root = isinstance(cypher_step.step_block, QueryRoot)

    if no_linked_location ^ step_is_query_root:
        raise AssertionError(
            "Received an illegal CypherStep. Not having a linked location is "
            "allowed if and only if the step is with a QueryRoot object. {}".format(cypher_step)
        )

    has_where_block = cypher_step.where_block is not None
    is_optional_step = isinstance(cypher_step.step_block, Traverse) and (
        cypher_step.step_block.optional or cypher_step.step_block.within_optional_scope
    )
    if has_where_block and is_optional_step:
        raise AssertionError(
            "Received an illegal CypherStep containing an optional step together "
            'with a "where" Filter block. This is a bug in the lowering code, as '
            "it should have moved the filtering to the global operations "
            "section. {}".format(cypher_step)
        )

    step_location = cypher_step.as_block.location  # destination vertex for current step's traversal
    step_location_name = cypher_helpers.get_unique_vertex_name_from_location(step_location)

    is_fold_step = isinstance(step_location, FoldScopeLocation)

    template_data = {
        "step_location": step_location_name,
        "step_vertex_type": ":".join(sorted(cypher_step.step_types)),
        "quantifier": "",
        "left_edge_mark": "",
        "right_edge_mark": "",
    }
    step_vertex_pattern = "(%(step_location)s:%(step_vertex_type)s)"

    if cypher_step.linked_location is None:
        pattern = "MATCH " + step_vertex_pattern
    else:
        pattern = (
            "MATCH (%(linked_location)s)"
            "%(left_edge_mark)s-[:%(edge_type)s%(quantifier)s]-%(right_edge_mark)s"
            + step_vertex_pattern
        )
        linked_location_name = cypher_helpers.get_unique_vertex_name_from_location(
            cypher_step.linked_location
        )
        template_data["linked_location"] = linked_location_name

    if has_where_block:
        pattern += "\n  WHERE %(predicate)s"
        template_data["predicate"] = cypher_step.where_block.predicate.to_cypher()

    if is_optional_step or is_fold_step:
        # OPTIONAL for fold too because if there is no such path for the given fold traversal, we
        # still want to return an empty list. Without OPTIONAL, the entire row would be missing
        # from the output.
        pattern = "OPTIONAL " + pattern

    if isinstance(cypher_step.step_block, (Traverse, Recurse, Fold)):
        if isinstance(cypher_step.step_block, Fold):
            direction, edge_name = cypher_step.step_block.fold_scope_location.fold_path[0]
        else:
            direction = cypher_step.step_block.direction
            edge_name = cypher_step.step_block.edge_name

        template_data["edge_type"] = edge_name

        direction_lookup = {
            "in": ("left_edge_mark", "<"),
            "out": ("right_edge_mark", ">"),
        }
        direction_symbol_name, direction_symbol = direction_lookup[direction]
        template_data[direction_symbol_name] = direction_symbol

    if isinstance(cypher_step.step_block, Recurse):
        template_data["quantifier"] = "*0..%d" % cypher_step.step_block.depth

    # Comply with Cypher style guidebook on whitespace a bit.
    pattern += "\n"

    return pattern % template_data


def _emit_with_clause_components(cypher_steps):
    """Emit a list of strings, one for each vertex or list that passes through a WITH clause."""
    if not cypher_steps:
        return []

    result = []
    location_names = set()
    for cypher_step in cypher_steps:
        location = cypher_step.as_block.location
        location_name = cypher_helpers.get_unique_vertex_name_from_location(location)
        if isinstance(location, FoldScopeLocation):
            location_name = cypher_helpers.get_collected_vertex_list_name(location_name)
        location_names.add(location_name)

    # Sort the locations, to ensure a deterministic order.
    for index, location_name in enumerate(sorted(location_names)):
        if index > 0:
            result.append(",")

        # We intentionally "rename" each location to its own name, to work around a limitation
        # in RedisGraph where un-aliased "WITH" clauses are not supported:
        # https://oss.redislabs.com/redisgraph/known_limitations/#unaliased-with-entities
        result.append("\n  %(name)s AS %(name)s" % {"name": location_name})

    return result


def _emit_with_clause_components_for_current_fold_scope(current_fold_scope_cypher_steps):
    """Emit a list of strings, one for each vertex or list passing through a WITH clause."""
    result = []

    vertex_names = {}
    for cypher_step in current_fold_scope_cypher_steps:
        if not isinstance(cypher_step, CypherStep):
            raise TypeError(
                "Expected current_fold_scope_cypher_steps to contain only CypherStep "
                "objects. Instead, got object {} of type {}. "
                "current_fold_scope_cypher_steps: {}".format(
                    cypher_step, type(cypher_step), current_fold_scope_cypher_steps
                )
            )
        fold_scope_location = cypher_step.as_block.location
        full_vertex_name = cypher_helpers.get_fold_scope_location_full_path_name(
            fold_scope_location
        )
        collected_name = cypher_helpers.get_collected_vertex_list_name(full_vertex_name)
        vertex_names["collect(" + full_vertex_name + ")"] = collected_name

    # Sort the locations, to ensure a deterministic order.
    for index, collect_call in enumerate(sorted(vertex_names)):
        if index > 0:
            result.append(",")
        result.append(
            "\n  {collect_call} AS {collected_name}".format(
                collect_call=collect_call, collected_name=vertex_names[collect_call]
            )
        )
    return result


def _emit_fold_scope(cypher_query):
    """Return a Cypher query pattern match expression for each fold scope in cypher_query.

    Consider the following CYPHER query, corresponding to test_input_data.multiple_folds()

    MATCH (Animal___1:Animal)
    OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)
    WITH
      Animal___1 AS Animal___1,
      collect(Animal__out_Animal_ParentOf___1) AS collected_Animal__out_Animal_ParentOf___1
    OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
    WITH
      Animal___1 AS Animal___1,
      collected_Animal__out_Animal_ParentOf___1 AS
        collected_Animal__out_Animal_ParentOf___1,
      collect(Animal__in_Animal_ParentOf___1) AS
        collected_Animal__in_Animal_ParentOf___1
    RETURN
      Animal___1.name AS `animal_name`,
      [x IN collected_Animal__out_Animal_ParentOf___1 | x.name] AS `child_names_list`,
      [x IN collected_Animal__out_Animal_ParentOf___1 | x.uuid] AS `child_uuids_list`,
      [x IN collected_Animal__in_Animal_ParentOf___1 | x.name] AS `parent_names_list`,
      [x IN collected_Animal__in_Animal_ParentOf___1 | x.uuid] AS `parent_uuids_list`

    For each fold scope, the structure generally works as follows:

    step 1. First, traverse to the vertex just outside the fold scope. Each traversal is mandatory
    here, so each traversal here is represented by a MATCH clause. Corresponds to:
        MATCH (Animal___1:Animal)

    step 2. Then, for each vertex at/ inside the fold scope, add a corresponding OPTIONAL MATCH
    clause. This traversal is marked OPTIONAL MATCH and not MATCH since we want the result to be an
    empty list and still show up in the final result even if nothing matches the traversal.
    Corresponds to:
        OPTIONAL MATCH (Animal___1)-[:Animal_ParentOf]->(Animal__out_Animal_ParentOf___1:Animal)

    step 3. After traversing to the innermost scope (at which point all the OPTIONAL MATCH clauses
    are generated, create a WITH clause. For each previously-expanded vertex V not in a fold scope,
    pass it through the WITH clause as itself (i.e. `V AS V`). For each vertex at or inside a
    previously-seen fold scope, return the name given to the list. For vertices at or inside the
    current fold scope, collect the vertices in the WITH clause as well, which materializes the list
    and guarantees that the order of elements within the output of a @fold is stable within each
    result set. Corresponds to:
        WITH
          Animal___1 AS Animal___1,
          collect(Animal__out_Animal_ParentOf___1) AS collected_Animal__out_Animal_ParentOf___1

    step 4. This process is repeated for other fold scopes in the query. Corresponds to:
        OPTIONAL MATCH (Animal___1)<-[:Animal_ParentOf]-(Animal__in_Animal_ParentOf___1:Animal)
        WITH
          Animal___1 AS Animal___1,
          collected_Animal__out_Animal_ParentOf___1 AS
            collected_Animal__out_Animal_ParentOf___1,
          collect(Animal__in_Animal_ParentOf___1) AS
            collected_Animal__in_Animal_ParentOf___1

    Args:
        cypher_query: CypherQuery object compiled from the given GraphQL query.

    Returns:
        list of strings that, when concatenated in order, form the part of the query that
        corresponds to each fold in the GraphQL query.
    """
    query_data = []
    previous_fold_scope_cypher_steps = []
    for fold_scope_location in sorted(cypher_query.folds.keys()):
        # step 2
        current_fold_scope_cypher_steps = cypher_query.folds[fold_scope_location]
        for cypher_step in current_fold_scope_cypher_steps:
            query_data.append(_emit_code_from_cypher_step(cypher_step))

        # step 3
        query_data.append("WITH")

        # First for all non-fold-scope CypherSteps, then all previous fold scope CypherSteps
        with_clause_steps = chain(cypher_query.steps, previous_fold_scope_cypher_steps)
        query_data.extend(_emit_with_clause_components(with_clause_steps))

        # Then for all current fold scope CypherSteps
        if current_fold_scope_cypher_steps:
            query_data.append(",")
        query_data.extend(
            _emit_with_clause_components_for_current_fold_scope(current_fold_scope_cypher_steps)
        )

        query_data.append("\n")

        # step 4 preparation:
        # Now that we've finished out this fold scope, we need to ensure these vertices get
        # passed on through all later WITH clauses as well.
        previous_fold_scope_cypher_steps.extend(current_fold_scope_cypher_steps)
    return query_data


##############
# Public API #
##############


def emit_code_from_ir(schema_info, cypher_query):
    """Return a Cypher query string from a CypherQuery object."""
    # According to the Cypher Query Language Reference [0], the standard Cypher version is
    # Cypher 9 (page 196) and we should be able to specify the Cypher version in the query.
    # Unfortunately, this turns out to be invalid in both Neo4j and RedisGraph-- Neo4j supports
    # Cypher version 2.3, 3.4, and 3.5 [1] while RedisGraph doesn't support the syntax at all [2].
    # When this does eventually get resolved, we can change `query_data` back to `['CYPHER 9']`
    # [0] https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf
    # [1] https://github.com/neo4j/neo4j/issues/12239
    # [2] https://github.com/RedisGraph/RedisGraph/issues/552
    query_data = [""]

    # if we have any fold directives in the query, this loop corresponds to step 1 described in
    # the comment in the function _emit_fold_scope().
    for cypher_step in cypher_query.steps:
        query_data.append(_emit_code_from_cypher_step(cypher_step))

    if cypher_query.folds:
        query_data.extend(_emit_fold_scope(cypher_query))

    if cypher_query.global_where_block is not None:
        query_data.append("WITH")
        query_data.extend(_emit_with_clause_components(cypher_query.steps))

        query_data.append("WHERE ")
        query_data.append(cypher_query.global_where_block.predicate.to_cypher())
        query_data.append("\n")

    query_data.append("RETURN")
    output_fields = cypher_query.output_block.fields
    sorted_output_keys = sorted(output_fields.keys())
    break_and_indent = "\n  "
    for output_index, output_name in enumerate(sorted_output_keys):
        if output_index > 0:
            query_data.append(",")

        output_expression = output_fields[output_name]
        query_data.append(break_and_indent)
        query_data.append("%s AS `%s`" % (output_expression.to_cypher(), output_name))

    return "".join(query_data)
