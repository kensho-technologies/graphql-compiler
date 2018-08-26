from graphql_compiler.compiler.expressions import ContextField
from .. import blocks as compiler_blocks
from .. import expressions as compiler_expr
from .sql_blocks import SqlBlocks as sql_blocks


class SqlBlockLowering(object):
    @staticmethod
    def lower_block(block, state_manager):
        if isinstance(block, compiler_blocks.QueryRoot):
            return SqlBlockLowering._lower_query_root(block, state_manager)
        elif isinstance(block, compiler_blocks.Filter):
            return SqlBlockLowering._lower_filter(block, state_manager)
        elif isinstance(block, compiler_blocks.MarkLocation):
            return SqlBlockLowering._lower_noop(block, state_manager)
        elif isinstance(block, compiler_blocks.EndOptional):
            return SqlBlockLowering._lower_end_optional(block, state_manager)
        elif isinstance(block, compiler_blocks.Traverse):
            return SqlBlockLowering._lower_traverse(block, state_manager)
        elif isinstance(block, compiler_blocks.Recurse):
            return SqlBlockLowering._lower_recurse(block, state_manager)
        elif isinstance(block, compiler_blocks.Backtrack):
            return SqlBlockLowering._lower_backtrack(block, state_manager)
        elif isinstance(block, compiler_blocks.ConstructResult):
            return SqlBlockLowering._lower_noop(block, state_manager)
        elif isinstance(block, compiler_blocks.Fold):
            return SqlBlockLowering._lower_fold(block, state_manager)
        elif isinstance(block, compiler_blocks.Unfold):
            return SqlBlockLowering._lower_unfold(block, state_manager)
        elif isinstance(block, compiler_blocks.CoerceType):
            # type coercion is free, the type at location dictionary will have the needed info
            return SqlBlockLowering._lower_noop(block, state_manager)
        else:
            raise AssertionError('Unable to lower block "{}" to SQL block.'.format(block))

    @staticmethod
    def _lower_query_root(block, state_manager):
        start_class = block.start_class
        if len(start_class) != 1:
            raise AssertionError('SQL backend should only have one root selection.')
        type_name = next(iter(start_class))
        state_manager.enter_location(type_name)
        yield block

    @staticmethod
    def _lower_filter(block, state_manager):
        predicate = block.predicate
        if isinstance(predicate, compiler_expr.BinaryComposition):
            operator = predicate.operator
            left = predicate.left
            right = predicate.right
            # todo: Between comes in as x >= lower and x <= upper, which are each
            # themselves BinaryComposition objects
            variable, field = left, right
            if isinstance(variable, compiler_expr.LocalField):
                variable, field = right, left
            if isinstance(variable, ContextField):
                tag_field = variable.location.field
                tag_location = variable.location.query_path
                yield sql_blocks.Predicate(
                    field_name=field.field_name,
                    # todo remove need for surrounding list
                    param_names=None,
                    operator_name=operator,
                    is_tag=True,
                    tag_field=tag_field,
                    tag_location=tag_location,
                    query_state=state_manager.get_state(),
                    block=block,
                )
            else:
                field_name = field.field_name
                yield sql_blocks.Predicate(
                    field_name=field_name,
                    # todo remove need for surrounding list
                    param_names=[variable.variable_name],
                    operator_name=operator,
                    is_tag=False,
                    tag_field=None,
                    tag_location=None,
                    query_state=state_manager.get_state(),
                    block=block
                )
        else:
            raise AssertionError('This should be unreachable.')

    @staticmethod
    def _lower_traverse(block, state_manager):
        if block.direction not in ('out', 'in'):
            raise AssertionError('Unknown direction "{}"'.format(block.direction))
        type_name = block.direction + '_' + block.edge_name
        if block.optional:
            state_manager.enter_optional()
        state_manager.enter_location(type_name)
        yield block

    @staticmethod
    def _lower_recurse(block, state_manager):
        if block.direction not in ('out', 'in'):
            raise AssertionError('Unknown direction "{}"'.format(block.direction))
        type_name = (block.direction + '_' + block.edge_name)
        state_manager.enter_recursive()
        state_manager.enter_location(type_name)
        yield block
        state_manager.exit_recursive()

    @staticmethod
    def _lower_construct_result(block, state_manager):
        for field_alias, field in block.fields.items():
            for sql_block in SqlBlockLowering._lower_output_field(block, field, field_alias, state_manager):
                yield sql_block

    @staticmethod
    def _lower_output_field(block, field, field_alias, state_manager):
        if isinstance(field, compiler_expr.TernaryConditional):
            # todo: This probably isn't the way to go in the general case
            field = field.if_true
        if isinstance(field, compiler_expr.OutputContextField):
            path = field.location.query_path
            field_name = field.location.field
            selection = sql_blocks.Selection(
                field_name=field_name,
                alias=field_alias,
                query_state=state_manager.state_for_path(path),
                block=block,
                field=field,
            )
            yield selection
        elif isinstance(field, compiler_expr.FoldedOutputContextField):
            path = field.fold_scope_location.base_location.query_path
            path += ('_'.join(field.fold_scope_location.relative_position),)
            field_name = field.field_name
            yield sql_blocks.Selection(
                field_name=field_name,
                alias=field_alias,
                query_state=state_manager.state_for_path(path),
                block=block,
                field=field,
            )
        else:
            raise AssertionError('This should be unreachable.')

    @staticmethod
    def _lower_fold(block, state_manager):
        direction, position = block.fold_scope_location.relative_position
        type_name = '{direction}_{position}'.format(direction=direction, position=position)
        state_manager.enter_fold()
        state_manager.enter_location(type_name)
        yield block

    @staticmethod
    def _lower_noop(block, state_manager):
        return iter([])

    @staticmethod
    def _lower_end_optional(block, state_manager):
        state_manager.exit_optional()
        return SqlBlockLowering._lower_noop(block, state_manager)

    @staticmethod
    def _lower_backtrack(block, state_manager):
        state_manager.exit_location()
        return SqlBlockLowering._lower_noop(block, state_manager)

    @staticmethod
    def _lower_unfold(block, state_manager):
        state_manager.exit_fold()
        state_manager.exit_location()
        return SqlBlockLowering._lower_noop(block, state_manager)

    @staticmethod
    def _lower_coerce_type(block, state_manager):
        return SqlBlockLowering._lower_noop(block, state_manager)
