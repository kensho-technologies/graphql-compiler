# Copyright 2017 Kensho Technologies, Inc.
"""Perform optimizations and lowering of the IR that allows the compiler to emit Gremlin queries.

The compiler IR allows blocks and expressions that cannot be directly compiled to Gremlin or MATCH.
For example, ContextFieldExistence is an Expression that returns True iff its given vertex exists,
but the produced Gremlin and MATCH outputs for this purpose are entirely different and not easy
to generate directly from this Expression object. An output-language-aware IR lowering step allows
us to convert this Expression into other Expressions, using data already present in the IR,
to simplify the final code generation step.
"""
from graphql.type import GraphQLInterfaceType, GraphQLObjectType, GraphQLUnionType

from ..exceptions import GraphQLCompilationError
from .blocks import Backtrack, CoerceType, Filter, Traverse
from .expressions import BinaryComposition, Literal, LocalField, NullLiteral
from .ir_lowering_common import (lower_context_field_existence, merge_consecutive_filter_clauses,
                                 optimize_boolean_expression_comparisons,
                                 sanity_check_ir_blocks_from_frontend)


##################################
# Optimization / lowering passes #
##################################

def lower_coerce_type_block_type_data(ir_blocks, type_equivalence_hints):
    """Rewrite CoerceType blocks to explicitly state which types are allowed in the coercion."""
    allowed_key_type_spec = (GraphQLInterfaceType, GraphQLObjectType)
    allowed_value_type_spec = GraphQLUnionType

    # Validate that the type_equivalence_hints parameter has correct types.
    for key, value in type_equivalence_hints.iteritems():
        if (not isinstance(key, allowed_key_type_spec) or
                not isinstance(value, allowed_value_type_spec)):
            msg = (u'Invalid type equivalence hints received! Hint {} ({}) -> {} ({}) '
                   u'was unexpected, expected a hint in the form '
                   u'GraphQLInterfaceType -> GraphQLUnionType or '
                   u'GraphQLObjectType -> GraphQLUnionType'.format(key.name, str(type(key)),
                                                                   value.name, str(type(value))))
            raise GraphQLCompilationError(msg)

    # CoerceType blocks only know the name of the type to which they coerce,
    # and not its corresponding GraphQL type object. Convert the type equivalence hints into
    # a dict of type name -> set of names of equivalent types, which can be used more readily.
    equivalent_type_names = {
        key.name: {x.name for x in value.types}
        for key, value in type_equivalence_hints.iteritems()
    }

    new_ir_blocks = []
    for block in ir_blocks:
        new_block = block
        if isinstance(block, CoerceType):
            if len(block.target_class) != 1:
                raise AssertionError(u'Expected only a single target class for the type coercion, '
                                     u'but received {}'.format(block.target_class))

            # Sets are not indexable, so we have to grab the first element of its iterator.
            target_class = next(x for x in block.target_class)
            if target_class in equivalent_type_names:
                new_block = CoerceType(equivalent_type_names[target_class])

        new_ir_blocks.append(new_block)

    return new_ir_blocks


def lower_coerce_type_blocks(ir_blocks):
    """Lower CoerceType blocks into Filter blocks with a type-check predicate."""
    new_ir_blocks = []

    for block in ir_blocks:
        new_block = block
        if isinstance(block, CoerceType):
            predicate = BinaryComposition(
                u'contains', Literal(list(block.target_class)), LocalField('@class'))
            new_block = Filter(predicate)

        new_ir_blocks.append(new_block)

    return new_ir_blocks


def rewrite_filters_in_optional_blocks(ir_blocks):
    """In optional contexts, add a check for null that allows non-existent optional data through.

    Optional traversals in Gremlin represent missing optional data by setting the current vertex
    to null until the exit from the optional scope. Therefore, filtering and type coercions
    (which should have been lowered into filters by this point) must check for null before
    applying their filtering predicates. Since missing optional data isn't filtered,
    the new filtering predicate should be "(it == null) || existing_predicate".

    Args:
        ir_blocks: list of IR blocks to lower into Gremlin-compatible form

    Returns:
        new list of IR blocks with this lowering step applied
    """
    new_ir_blocks = []
    optional_context_depth = 0

    for block in ir_blocks:
        new_block = block
        if isinstance(block, CoerceType):
            raise AssertionError(u'Found a CoerceType block after all such blocks should have been '
                                 u'lowered to Filter blocks: {}'.format(ir_blocks))
        elif isinstance(block, Traverse) and block.optional:
            optional_context_depth += 1
        elif isinstance(block, Backtrack) and block.optional:
            optional_context_depth -= 1
            if optional_context_depth < 0:
                raise AssertionError(u'Reached negative optional context depth for blocks: '
                                     u'{}'.format(ir_blocks))
        elif isinstance(block, Filter) and optional_context_depth > 0:
            null_check = BinaryComposition(u'=', LocalField('@this'), NullLiteral)
            new_block = Filter(BinaryComposition(u'||', null_check, block.predicate))
        else:
            pass

        new_ir_blocks.append(new_block)

    return new_ir_blocks


##############
# Public API #
##############

def lower_ir(ir_blocks, location_types, type_equivalence_hints=None):
    """Lower the IR into an IR form that can be represented in Gremlin queries.

    Args:
        ir_blocks: list of IR blocks to lower into Gremlin-compatible form
        location_types: a dict of location objects -> GraphQL type objects at that location
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for Gremlin's lack of inheritance-awareness
                                When this parameter is not specified or is empty, type coercion
                                coerces to the *exact* type being coerced to without regard for
                                subclasses of that type. This parameter allows the user to
                                manually specify which GraphQL interfaces and types are
                                superclasses of which other types, and emits Gremlin code
                                that performs type coercion with this information in mind.
                                No recursive expansion of type equivalence hints will be performed,
                                and only type-level correctness of the hints is enforced.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****

    Returns:
        list of IR blocks suitable for outputting as Gremlin
    """
    sanity_check_ir_blocks_from_frontend(ir_blocks)

    ir_blocks = lower_context_field_existence(ir_blocks)
    ir_blocks = optimize_boolean_expression_comparisons(ir_blocks)

    if type_equivalence_hints:
        ir_blocks = lower_coerce_type_block_type_data(ir_blocks, type_equivalence_hints)

    ir_blocks = lower_coerce_type_blocks(ir_blocks)
    ir_blocks = rewrite_filters_in_optional_blocks(ir_blocks)
    ir_blocks = merge_consecutive_filter_clauses(ir_blocks)

    return ir_blocks
