# Copyright 2017-present Kensho Technologies, LLC.
"""Perform optimizations and lowering of the IR that allows the compiler to emit Gremlin queries.

The compiler IR allows blocks and expressions that cannot be directly compiled to the underlying
database query languages. For example, ContextFieldExistence is an Expression that returns
True iff its given vertex exists, but the produced Gremlin and MATCH outputs for this purpose
are entirely different and not easy to generate directly from this Expression object.
An output-language-aware IR lowering step allows us to convert this Expression into
other Expressions, using data already present in the IR, to simplify the final code generation step.
"""
from graphql import GraphQLInt, GraphQLList, GraphQLString
from graphql.type import GraphQLInterfaceType, GraphQLObjectType, GraphQLUnionType
import six

from ...exceptions import GraphQLCompilationError
from ...global_utils import is_same_type
from ...schema import GraphQLDate, GraphQLDateTime
from ..blocks import Backtrack, CoerceType, Filter, GlobalOperationsStart, MarkLocation, Traverse
from ..compiler_entities import Expression
from ..expressions import (
    BinaryComposition,
    FoldedContextField,
    Literal,
    LocalField,
    NullLiteral,
    make_type_replacement_visitor,
)
from ..helpers import (
    STANDARD_DATE_FORMAT,
    STANDARD_DATETIME_FORMAT,
    FoldScopeLocation,
    get_only_element_from_collection,
    strip_non_null_from_type,
    validate_safe_string,
)
from ..ir_lowering_common.common import extract_folds_from_ir_blocks


##################################
# Optimization / lowering passes #
##################################


def lower_coerce_type_block_type_data(ir_blocks, type_equivalence_hints):
    """Rewrite CoerceType blocks to explicitly state which types are allowed in the coercion."""
    allowed_key_type_spec = (GraphQLInterfaceType, GraphQLObjectType)
    allowed_value_type_spec = GraphQLUnionType

    # Validate that the type_equivalence_hints parameter has correct types.
    for key, value in six.iteritems(type_equivalence_hints):
        if not isinstance(key, allowed_key_type_spec) or not isinstance(
            value, allowed_value_type_spec
        ):
            msg = (
                "Invalid type equivalence hints received! Hint {} ({}) -> {} ({}) "
                "was unexpected, expected a hint in the form "
                "GraphQLInterfaceType -> GraphQLUnionType or "
                "GraphQLObjectType -> GraphQLUnionType".format(
                    key.name, str(type(key)), value.name, str(type(value))
                )
            )
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
                "contains", Literal(list(block.target_class)), LocalField("@class", GraphQLString)
            )
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
            raise AssertionError(
                "Found a CoerceType block after all such blocks should have been "
                "lowered to Filter blocks: {}".format(ir_blocks)
            )
        elif isinstance(block, Traverse) and block.optional:
            optional_context_depth += 1
        elif isinstance(block, Backtrack) and block.optional:
            optional_context_depth -= 1
            if optional_context_depth < 0:
                raise AssertionError(
                    "Reached negative optional context depth for blocks: {}".format(ir_blocks)
                )
        elif isinstance(block, Filter) and optional_context_depth > 0:
            null_check = BinaryComposition("=", LocalField("@this", None), NullLiteral)
            new_block = Filter(BinaryComposition("||", null_check, block.predicate))
        else:
            pass

        new_ir_blocks.append(new_block)

    return new_ir_blocks


class GremlinFoldedContextField(Expression):
    """A Gremlin-specific FoldedContextField that knows how to output itself as Gremlin."""

    def __init__(self, fold_scope_location, folded_ir_blocks, field_type):
        """Create a new GremlinFoldedContextField."""
        super(GremlinFoldedContextField, self).__init__(
            fold_scope_location, folded_ir_blocks, field_type
        )
        self.fold_scope_location = fold_scope_location
        self.folded_ir_blocks = folded_ir_blocks
        self.field_type = field_type
        self.validate()

    def validate(self):
        """Validate that the GremlinFoldedContextField is correctly representable."""
        if not isinstance(self.fold_scope_location, FoldScopeLocation):
            raise TypeError(
                "Expected FoldScopeLocation fold_scope_location, got: {} {}".format(
                    type(self.fold_scope_location), self.fold_scope_location
                )
            )

        allowed_block_types = (GremlinFoldedFilter, GremlinFoldedTraverse, Backtrack)
        for block in self.folded_ir_blocks:
            if not isinstance(block, allowed_block_types):
                raise AssertionError(
                    "Found invalid block of type {} in folded_ir_blocks: {} "
                    "Allowed types are {}.".format(
                        type(block), self.folded_ir_blocks, allowed_block_types
                    )
                )

        bare_field_type = strip_non_null_from_type(self.field_type)
        if isinstance(bare_field_type, GraphQLList):
            inner_type = strip_non_null_from_type(bare_field_type.of_type)
            if isinstance(inner_type, GraphQLList):
                raise GraphQLCompilationError(
                    "Outputting list-valued fields in a @fold context is currently not supported: "
                    "{} {}".format(self.fold_scope_location, bare_field_type.of_type)
                )
        elif is_same_type(GraphQLInt, bare_field_type):
            # This needs to be implemented for @fold _x_count support.
            raise NotImplementedError()
        else:
            raise ValueError(
                'Invalid value of "field_type", expected a (possibly non-null) '
                "list or int type but got: {}".format(self.field_type)
            )

    def to_match(self):
        """Must never be called."""
        raise NotImplementedError()

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this expression."""
        self.validate()
        edge_direction, edge_name = self.fold_scope_location.get_first_folded_edge()
        validate_safe_string(edge_name)

        inverse_direction_table = {
            "out": "in",
            "in": "out",
        }
        inverse_direction = inverse_direction_table[edge_direction]

        base_location_name, _ = self.fold_scope_location.base_location.get_location_name()
        validate_safe_string(base_location_name)

        _, field_name = self.fold_scope_location.get_location_name()
        validate_safe_string(field_name)

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
                "((m.{base_location_name}.{direction}_{edge_name} == null) ? [] : ("
                "m.{base_location_name}.{direction}_{edge_name}.collect{{"
                "entry -> entry.{inverse_direction}V.next().{field_name}{maybe_format}"
                "}}"
                "))"
            )
            filter_and_traverse_data = ""
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
                "((m.{base_location_name}.{direction}_{edge_name} == null) ? [] : ("
                "m.{base_location_name}.{direction}_{edge_name}.collect{{"
                "entry -> entry.{inverse_direction}V.next()"
                "}}"
                ".{filters_and_traverses}"
                ".collect{{entry -> entry.{field_name}{maybe_format}}}"
                "))"
            )
            filter_and_traverse_data = ".".join(
                block.to_gremlin() for block in self.folded_ir_blocks
            )

        maybe_format = ""
        inner_type = strip_non_null_from_type(self.field_type.of_type)
        if is_same_type(GraphQLDate, inner_type):
            maybe_format = '.format("' + STANDARD_DATE_FORMAT + '")'
        elif is_same_type(GraphQLDateTime, inner_type):
            maybe_format = '.format("' + STANDARD_DATETIME_FORMAT + '")'

        template_data = {
            "base_location_name": base_location_name,
            "direction": edge_direction,
            "edge_name": edge_name,
            "field_name": field_name,
            "inverse_direction": inverse_direction,
            "maybe_format": maybe_format,
            "filters_and_traverses": filter_and_traverse_data,
        }
        return template.format(**template_data)


class GremlinFoldedFilter(Filter):
    """A Gremlin-specific Filter block to be used only within @fold scopes."""

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this block."""
        self.validate()
        return "findAll{{entry -> {}}}".format(self.predicate.to_gremlin())


class GremlinFoldedTraverse(Traverse):
    """A Gremlin-specific Traverse block to be used only within @fold scopes."""

    @classmethod
    def from_traverse(cls, traverse_block):
        """Create a GremlinFoldedTraverse block as a copy of the given Traverse block."""
        if isinstance(traverse_block, Traverse):
            return cls(traverse_block.direction, traverse_block.edge_name)
        else:
            raise AssertionError(
                "Tried to initialize an instance of GremlinFoldedTraverse "
                "with block of type {}".format(type(traverse_block))
            )

    def to_gremlin(self):
        """Return a unicode object with the Gremlin representation of this block."""
        self.validate()
        template_data = {
            "direction": self.direction,
            "edge_name": self.edge_name,
            "inverse_direction": "in" if self.direction == "out" else "out",
        }
        return (
            "collectMany{{entry -> entry.{direction}_{edge_name}"
            ".collect{{edge -> edge.{inverse_direction}V.next()}}}}".format(**template_data)
        )


class GremlinFoldedLocalField(LocalField):
    """A Gremlin-specific LocalField expressionto be used only within @fold scopes."""

    def get_local_object_gremlin_name(self):
        """Return the Gremlin name of the local object whose field is being produced."""
        return "entry"


def _convert_folded_blocks(folded_ir_blocks):
    """Convert Filter/Traverse blocks and LocalField expressions within @fold to Gremlin objects."""
    new_folded_ir_blocks = []

    def folded_context_visitor(expression):
        """Transform LocalField objects into their Gremlin-specific counterpart."""
        if not isinstance(expression, LocalField):
            return expression

        return GremlinFoldedLocalField(expression.field_name, expression.field_type)

    for block in folded_ir_blocks:
        new_block = block

        if isinstance(block, Filter):
            new_predicate = block.predicate.visit_and_update(folded_context_visitor)
            new_block = GremlinFoldedFilter(new_predicate)
        elif isinstance(block, Traverse):
            new_block = GremlinFoldedTraverse.from_traverse(block)
        elif isinstance(block, (MarkLocation, Backtrack)):
            # We remove MarkLocation and Backtrack blocks from the folded blocks output,
            # since they do not produce any Gremlin output code inside folds.
            continue
        else:
            raise AssertionError(
                "Found an unexpected IR block in the folded IR blocks: "
                "{} {} {}".format(type(block), block, folded_ir_blocks)
            )

        new_folded_ir_blocks.append(new_block)

    return new_folded_ir_blocks


def lower_folded_outputs_and_context_fields(ir_blocks):
    """Lower standard folded output / context fields into GremlinFoldedContextField objects."""
    folds, remaining_ir_blocks = extract_folds_from_ir_blocks(ir_blocks)

    if not remaining_ir_blocks:
        raise AssertionError(
            "Expected at least one non-folded block to remain: {} {} "
            "{}".format(folds, remaining_ir_blocks, ir_blocks)
        )

    # Turn folded Filter blocks into GremlinFoldedFilter blocks.
    converted_folds = {
        base_fold_location.get_location_name()[0]: _convert_folded_blocks(folded_ir_blocks)
        for base_fold_location, folded_ir_blocks in six.iteritems(folds)
    }

    def rewriter_fn(folded_context_field):
        """Rewrite FoldedContextField objects into GremlinFoldedContextField ones."""
        # Get the matching folded IR blocks and put them in the new context field.
        base_fold_location_name = folded_context_field.fold_scope_location.get_location_name()[0]
        folded_ir_blocks = converted_folds[base_fold_location_name]
        return GremlinFoldedContextField(
            folded_context_field.fold_scope_location,
            folded_ir_blocks,
            folded_context_field.field_type,
        )

    visitor_fn = make_type_replacement_visitor(FoldedContextField, rewriter_fn)

    # Start by just appending blocks to the output list.
    new_ir_blocks = []
    block_collection = new_ir_blocks
    for block in remaining_ir_blocks:
        block_collection.append(block)

        if isinstance(block, GlobalOperationsStart):
            # Once we see the GlobalOperationsStart, start accumulating the blocks for rewriting.
            block_collection = []

    for block in block_collection:
        new_ir_blocks.append(block.visit_and_update_expressions(visitor_fn))

    return new_ir_blocks
