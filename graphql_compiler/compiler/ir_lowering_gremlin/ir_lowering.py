# Copyright 2017-present Kensho Technologies, LLC.
"""Perform optimizations and lowering of the IR that allows the compiler to emit Gremlin queries.

The compiler IR allows blocks and expressions that cannot be directly compiled to Gremlin or MATCH.
For example, ContextFieldExistence is an Expression that returns True iff its given vertex exists,
but the produced Gremlin and MATCH outputs for this purpose are entirely different and not easy
to generate directly from this Expression object. An output-language-aware IR lowering step allows
us to convert this Expression into other Expressions, using data already present in the IR,
to simplify the final code generation step.
"""
from graphql import GraphQLList
from graphql.type import GraphQLInterfaceType, GraphQLObjectType, GraphQLUnionType
import six

from ...exceptions import GraphQLCompilationError
from ...schema import GraphQLDate, GraphQLDateTime
from ..blocks import Backtrack, CoerceType, ConstructResult, Filter, Traverse
from ..compiler_entities import Expression
from ..expressions import (BinaryComposition, FoldedOutputContextField, Literal, LocalField,
                           NullLiteral)
from ..helpers import (STANDARD_DATE_FORMAT, STANDARD_DATETIME_FORMAT, FoldScopeLocation,
                       get_only_element_from_collection, strip_non_null_from_type,
                       validate_safe_string)
from ..ir_lowering_common import extract_folds_from_ir_blocks


##################################
# Optimization / lowering passes #
##################################

def lower_coerce_type_block_type_data(ir_blocks, type_equivalence_hints):
    """Rewrite CoerceType blocks to explicitly state which types are allowed in the coercion."""
    allowed_key_type_spec = (GraphQLInterfaceType, GraphQLObjectType)
    allowed_value_type_spec = GraphQLUnionType

    # Validate that the type_equivalence_hints parameter has correct types.
    for key, value in six.iteritems(type_equivalence_hints):
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
        for key, value in six.iteritems(type_equivalence_hints)
    }

    new_ir_blocks = []
    for block in ir_blocks:
        new_block = block
        if isinstance(block, CoerceType):
            target_class = get_only_element_from_collection(block.target_class)
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


class GremlinFoldedOutputContextField(Expression):
    """A Gremlin-specific FoldedOutputContextField that knows how to output itself as Gremlin."""

    def __init__(self, fold_scope_location, folded_ir_blocks, field_name, field_type):
        """Create a new GremlinFoldedOutputContextField."""
        super(GremlinFoldedOutputContextField, self).__init__(
            fold_scope_location, folded_ir_blocks, field_name, field_type)
        self.fold_scope_location = fold_scope_location
        self.folded_ir_blocks = folded_ir_blocks
        self.field_name = field_name
        self.field_type = field_type
        self.validate()

    def validate(self):
        """Validate that the GremlinFoldedOutputContextField is correctly representable."""
        if not isinstance(self.fold_scope_location, FoldScopeLocation):
            raise TypeError(u'Expected FoldScopeLocation fold_scope_location, got: {} {}'.format(
                type(self.fold_scope_location), self.fold_scope_location))

        allowed_block_types = (GremlinFoldedFilter, GremlinFoldedTraverse, Backtrack)
        for block in self.folded_ir_blocks:
            if not isinstance(block, allowed_block_types):
                raise AssertionError(
                    u'Found invalid block of type {} in folded_ir_blocks: {} '
                    u'Allowed types are {}.'
                    .format(type(block), self.folded_ir_blocks, allowed_block_types))

        validate_safe_string(self.field_name)

        if not isinstance(self.field_type, GraphQLList):
            raise ValueError(u'Invalid value of "field_type", expected a list type but got: '
                             u'{}'.format(self.field_type))

        inner_type = strip_non_null_from_type(self.field_type.of_type)
        if isinstance(inner_type, GraphQLList):
            raise GraphQLCompilationError(u'Outputting list-valued fields in a @fold context is '
                                          u'currently not supported: {} '
                                          u'{}'.format(self.field_name, self.field_type.of_type))

    def to_match(self):
        """Must never be called."""
        raise NotImplementedError()

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()
        edge_direction, edge_name = self.fold_scope_location.relative_position
        inverse_direction_table = {
            'out': 'in',
            'in': 'out',
        }
        inverse_direction = inverse_direction_table[edge_direction]

        mark_name, _ = self.fold_scope_location.base_location.get_location_name()
        validate_safe_string(mark_name)

        if not self.folded_ir_blocks:
            # There is no filtering nor type coercions applied to this @fold scope.
            #
            # This template generates code like:
            # (
            #     (m.base.in_Animal_ParentOf == null) ?
            #     [] : (
            #         m.base.in_Animal_ParentOf.collect{entry -> entry.outV.next().uuid}
            #     )
            # )
            template = (
                u'((m.{mark_name}.{direction}_{edge_name} == null) ? [] : ('
                u'm.{mark_name}.{direction}_{edge_name}.collect{{'
                u'entry -> entry.{inverse_direction}V.next().{field_name}{maybe_format}'
                u'}}'
                u'))'
            )
            filter_and_traverse_data = ''
        else:
            # There is filtering or type coercions in this @fold scope.
            #
            # This template generates code like:
            # (
            #     (m.base.in_Animal_ParentOf == null) ?
            #     [] : (
            #         m.base.in_Animal_ParentOf
            #          .collect{entry -> entry.outV.next()}
            #          .findAll{it.alias.contains($wanted)}
            #          .collect{it.uuid}
            #     )
            # )
            template = (
                u'((m.{mark_name}.{direction}_{edge_name} == null) ? [] : ('
                u'm.{mark_name}.{direction}_{edge_name}.collect{{'
                u'entry -> entry.{inverse_direction}V.next()'
                u'}}'
                u'.{filters_and_traverses}'
                u'.collect{{entry -> entry.{field_name}{maybe_format}}}'
                u'))'
            )
            filter_and_traverse_data = u'.'.join(block.to_gremlin()
                                                 for block in self.folded_ir_blocks)

        maybe_format = ''
        inner_type = strip_non_null_from_type(self.field_type.of_type)
        if GraphQLDate.is_same_type(inner_type):
            maybe_format = '.format("' + STANDARD_DATE_FORMAT + '")'
        elif GraphQLDateTime.is_same_type(inner_type):
            maybe_format = '.format("' + STANDARD_DATETIME_FORMAT + '")'

        template_data = {
            'mark_name': mark_name,
            'direction': edge_direction,
            'edge_name': edge_name,
            'field_name': self.field_name,
            'inverse_direction': inverse_direction,
            'maybe_format': maybe_format,
            'filters_and_traverses': filter_and_traverse_data,
        }
        return template.format(**template_data)


class GremlinFoldedFilter(Filter):
    """A Gremlin-specific Filter block to be used only within @fold scopes."""

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this block."""
        self.validate()
        return u'findAll{{entry -> {}}}'.format(self.predicate.to_gremlin())


class GremlinFoldedTraverse(Traverse):
    """A Gremlin-specific Traverse block to be used only within @fold scopes."""

    @classmethod
    def from_traverse(cls, traverse_block):
        """Create a GremlinFoldedTraverse block as a copy of the given Traverse block."""
        if isinstance(traverse_block, Traverse):
            return cls(traverse_block.direction, traverse_block.edge_name)
        else:
            raise AssertionError(u'Tried to initialize an instance of GremlinFoldedTraverse '
                                 u'with block of type {}'.format(type(traverse_block)))

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this block."""
        self.validate()
        template_data = {
            'direction': self.direction,
            'edge_name': self.edge_name,
            'inverse_direction': 'in' if self.direction == 'out' else 'out'
        }
        return (u'collectMany{{entry -> entry.{direction}_{edge_name}'
                u'.collect{{edge -> edge.{inverse_direction}V.next()}}}}'
                .format(**template_data))


class GremlinFoldedLocalField(LocalField):
    """A Gremlin-specific LocalField expressionto be used only within @fold scopes."""

    def get_local_object_gremlin_name(self):
        """Return the Gremlin name of the local object whose field is being produced."""
        return u'entry'


def _convert_folded_blocks(folded_ir_blocks):
    """Convert Filter/Traverse blocks and LocalField expressions within @fold to Gremlin objects."""
    new_folded_ir_blocks = []

    def folded_context_visitor(expression):
        """Transform LocalField objects into their Gremlin-specific counterpart."""
        if not isinstance(expression, LocalField):
            return expression

        return GremlinFoldedLocalField(expression.field_name)

    for block in folded_ir_blocks:
        new_block = block

        if isinstance(block, Filter):
            new_predicate = block.predicate.visit_and_update(folded_context_visitor)
            new_block = GremlinFoldedFilter(new_predicate)
        elif isinstance(block, Traverse):
            new_block = GremlinFoldedTraverse.from_traverse(block)
        else:
            continue

        new_folded_ir_blocks.append(new_block)

    return new_folded_ir_blocks


def lower_folded_outputs(ir_blocks):
    """Lower standard folded output fields into GremlinFoldedOutputContextField objects."""
    folds, remaining_ir_blocks = extract_folds_from_ir_blocks(ir_blocks)

    if not remaining_ir_blocks:
        raise AssertionError(u'Expected at least one non-folded block to remain: {} {} '
                             u'{}'.format(folds, remaining_ir_blocks, ir_blocks))
    output_block = remaining_ir_blocks[-1]
    if not isinstance(output_block, ConstructResult):
        raise AssertionError(u'Expected the last non-folded block to be ConstructResult, '
                             u'but instead was: {} {} '
                             u'{}'.format(type(output_block), output_block, ir_blocks))

    # Turn folded Filter blocks into GremlinFoldedFilter blocks.
    converted_folds = {
        key: _convert_folded_blocks(folded_ir_blocks)
        for key, folded_ir_blocks in six.iteritems(folds)
    }

    new_output_fields = dict()
    for output_name, output_expression in six.iteritems(output_block.fields):
        new_output_expression = output_expression

        # Turn FoldedOutputContextField expressions into GremlinFoldedOutputContextField ones.
        if isinstance(output_expression, FoldedOutputContextField):
            # Get the matching folded IR blocks and put them in the new context field.
            folded_ir_blocks = converted_folds[output_expression.fold_scope_location]
            new_output_expression = GremlinFoldedOutputContextField(
                output_expression.fold_scope_location, folded_ir_blocks,
                output_expression.field_name, output_expression.field_type)

        new_output_fields[output_name] = new_output_expression

    new_ir_blocks = remaining_ir_blocks[:-1]
    new_ir_blocks.append(ConstructResult(new_output_fields))
    return new_ir_blocks
