# Copyright 2017 Kensho Technologies, Inc.
from functools import partial, wraps

from graphql import GraphQLList, GraphQLObjectType, GraphQLScalarType, GraphQLString
from graphql.language.ast import ListValue

from . import blocks, expressions
from ..exceptions import GraphQLCompilationError, GraphQLValidationError
from .helpers import (get_ast_field_name, get_uniquely_named_objects_by_name, is_real_leaf_type,
                      strip_non_null_from_type, validate_safe_string)


def scalar_leaf_only(operator):
    """Ensure the filter function is only applied to scalar leaf types."""
    def decorator(f):
        """Decorate the supplied function with the "scalar_leaf_only" logic."""
        @wraps(f)
        def wrapper(schema, current_schema_type, ast, context,
                    directive, parameters, *args, **kwargs):
            """Check that the type on which the operator operates is a scalar leaf type."""
            if 'operator' in kwargs:
                current_operator = kwargs['operator']
            else:
                # Because "operator" is from an enclosing scope, it is immutable in Python 2.x.
                current_operator = operator

            if not is_real_leaf_type(current_schema_type):
                raise GraphQLCompilationError(u'Cannot apply "{}" filter to non-leaf type'
                                              u'{}'.format(current_operator, current_schema_type))
            return f(schema, current_schema_type, ast, context,
                     directive, parameters, *args, **kwargs)

        return wrapper

    return decorator


def takes_parameters(count):
    """Ensure the filter function has "count" parameters specified."""
    def decorator(f):
        """Decorate the supplied function with the "takes_parameters" logic."""
        @wraps(f)
        def wrapper(schema, current_schema_type, ast, context,
                    directive, parameters, *args, **kwargs):
            """Check that the supplied number of parameters equals the expected number."""
            if len(parameters) != count:
                raise GraphQLCompilationError(u'Incorrect number of parameters, expected {} got '
                                              u'{}: {}'.format(count, len(parameters), parameters))

            return f(schema, current_schema_type, ast, context,
                     directive, parameters, *args, **kwargs)

        return wrapper

    return decorator


def _represent_argument(schema, ast, context, argument, inferred_type):
    """Return a two-element tuple that represents the argument to the directive being processed.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        ast: GraphQL AST node, obtained from the graphql library. Only for function signature
             uniformity at the moment -- it is currently not used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        argument: basestring, the name of the argument to the directive
        inferred_type: GraphQL type object specifying the inferred type of the argument

    Returns:
        (argument_expression, non_existence_expression)
            - argument_expression: an Expression object that captures the semantics of the argument
            - non_existence_expression: None or Expression object;
              If the current block is not optional, this is set to None. Otherwise, it is an
              expression that will evaluate to True if the argument is skipped as optional and
              therefore not present, and False otherwise.
    """
    # Regardless of what kind of variable we are dealing with,
    # we want to ensure its name is valid.
    argument_name = argument[1:]
    validate_safe_string(argument_name)

    if argument.startswith('$'):
        existing_type = context['inputs'].get(argument_name, inferred_type)
        if not inferred_type.is_same_type(existing_type):
            raise GraphQLCompilationError(u'Incompatible types inferred for argument {}. '
                                          u'The argument cannot simultaneously be '
                                          u'{} and {}.'.format(argument, existing_type,
                                                               inferred_type))
        context['inputs'][argument_name] = inferred_type

        return (expressions.Variable(argument, inferred_type), None)
    elif argument.startswith('%'):
        argument_context = context['tags'].get(argument_name, None)
        if argument_context is None:
            raise GraphQLCompilationError(u'Undeclared argument used: {}'.format(argument))

        location = argument_context['location']
        optional = argument_context['optional']
        tag_inferred_type = argument_context['type']

        if location is None:
            raise AssertionError(u'Argument declared without location: {}'.format(argument_name))

        if location.field is None:
            raise AssertionError(u'Argument location is not a property field: {}'.format(location))

        if not inferred_type.is_same_type(tag_inferred_type):
            raise GraphQLCompilationError(u'The inferred type of the matching @tag directive does '
                                          u'not match the inferred required type for this filter: '
                                          u'{} vs {}'.format(tag_inferred_type, inferred_type))

        non_existence_expression = None
        if optional:
            non_existence_expression = expressions.BinaryComposition(
                u'=',
                expressions.ContextFieldExistence(location.at_vertex()),
                expressions.FalseLiteral)

        representation = expressions.ContextField(location)
        return (representation, non_existence_expression)
    else:
        # If we want to support literal arguments, add them here.
        raise GraphQLCompilationError(u'Non-argument type found: {}'.format(argument))


@scalar_leaf_only(u'comparison operator')
@takes_parameters(1)
def _process_comparison_filter_directive(schema, current_schema_type, ast,
                                         context, directive, parameters, operator=None):
    """Return a Filter basic block that performs the given comparison against the property field.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        directive: GraphQL directive object, obtained from the AST node
        parameters: list of 1 element, containing the value to perform the comparison against;
                    if the parameter is optional and missing, the check is performed against 'null'
        operator: unicode, a comparison operator, like '=', '!=', '>=' etc.
                  This is a kwarg only to preserve the same positional arguments in the
                  function signature, to ease validation.

    Returns:
        a Filter basic block that performs the requested comparison
    """
    comparison_operators = {u'=', u'!=', u'>', u'<', u'>=', u'<='}
    if operator not in comparison_operators:
        raise AssertionError(u'Expected a valid comparison operator ({}), but got '
                             u'{}'.format(comparison_operators, operator))

    argument_inferred_type = strip_non_null_from_type(current_schema_type)
    argument_expression, non_existence_expression = _represent_argument(
        schema, ast, context, parameters[0], argument_inferred_type)

    field_name = get_ast_field_name(ast)
    comparison_expression = expressions.BinaryComposition(
        operator, expressions.LocalField(field_name), argument_expression)

    final_expression = None
    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        final_expression = expressions.BinaryComposition(
            u'||', non_existence_expression, comparison_expression)
    else:
        final_expression = comparison_expression

    return blocks.Filter(final_expression)


@takes_parameters(1)
def _process_name_or_alias_filter_directive(schema, current_schema_type, ast,
                                            context, directive, parameters):
    """Return a Filter basic block that checks for a match against an Entity's name or alias.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        directive: GraphQL directive object, obtained from the AST node
        parameters: list of 1 element, containing the value to check the name or alias against;
                    if the parameter is optional and missing, the check is performed against 'null'

    Returns:
        a Filter basic block that performs the check against the name or alias
    """
    if not isinstance(current_schema_type, GraphQLObjectType):
        raise GraphQLCompilationError(u'Cannot apply "name_or_alias" to non-object '
                                      u'type {}'.format(current_schema_type))

    current_type_fields = current_schema_type.fields
    name_field = current_type_fields.get('name', None)
    alias_field = current_type_fields.get('alias', None)
    if not name_field or not alias_field:
        raise GraphQLCompilationError(u'Cannot apply "name_or_alias" to type {} because it lacks a '
                                      u'"name" or "alias" field.'.format(current_schema_type))

    name_field_type = strip_non_null_from_type(name_field.type)
    alias_field_type = strip_non_null_from_type(alias_field.type)

    if not isinstance(name_field_type, GraphQLScalarType):
        raise GraphQLCompilationError(u'Cannot apply "name_or_alias" to type {} because its "name" '
                                      u'field is not a scalar.'.format(current_schema_type))
    if not isinstance(alias_field_type, GraphQLList):
        raise GraphQLCompilationError(u'Cannot apply "name_or_alias" to type {} because its '
                                      u'"alias" field is not a list.'.format(current_schema_type))

    alias_field_inner_type = strip_non_null_from_type(alias_field_type.of_type)
    if alias_field_inner_type != name_field_type:
        raise GraphQLCompilationError(u'Cannot apply "name_or_alias" to type {} because the '
                                      u'"name" field and the inner type of the "alias" field '
                                      u'do not match: {} vs {}'.format(current_schema_type,
                                                                       name_field_type,
                                                                       alias_field_inner_type))

    argument_inferred_type = name_field_type
    argument_expression, non_existence_expression = _represent_argument(
        schema, ast, context, parameters[0], argument_inferred_type)

    check_against_name = expressions.BinaryComposition(
        u'=', expressions.LocalField('name'), argument_expression)
    check_against_alias = expressions.BinaryComposition(
        u'contains', expressions.LocalField('alias'), argument_expression)
    filter_predicate = expressions.BinaryComposition(
        u'||', check_against_name, check_against_alias)

    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        filter_predicate = expressions.BinaryComposition(
            u'||', non_existence_expression, filter_predicate)

    return blocks.Filter(filter_predicate)


@scalar_leaf_only(u'between')
@takes_parameters(2)
def _process_between_filter_directive(schema, current_schema_type, ast,
                                      context, directive, parameters):
    """Return a Filter basic block that checks that a field is between two values, inclusive.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        directive: GraphQL directive object, obtained from the AST node
        parameters: list of 2 elements, specifying the time range in which the data must lie;
                    if either of the elements is optional and missing,
                    their side of the check is assumed to be True

    Returns:
        a Filter basic block that performs the range check
    """
    field_name = get_ast_field_name(ast)

    argument_inferred_type = strip_non_null_from_type(current_schema_type)
    arg1_expression, arg1_non_existence = _represent_argument(
        schema, ast, context, parameters[0], argument_inferred_type)
    arg2_expression, arg2_non_existence = _represent_argument(
        schema, ast, context, parameters[1], argument_inferred_type)

    lower_bound_clause = expressions.BinaryComposition(
        u'>=', expressions.LocalField(field_name), arg1_expression)
    if arg1_non_existence is not None:
        # The argument is optional, and if it doesn't exist, this side of the check should pass.
        lower_bound_clause = expressions.BinaryComposition(
            u'||', arg1_non_existence, lower_bound_clause)

    upper_bound_clause = expressions.BinaryComposition(
        u'<=', expressions.LocalField(field_name), arg2_expression)
    if arg2_non_existence is not None:
        # The argument is optional, and if it doesn't exist, this side of the check should pass.
        upper_bound_clause = expressions.BinaryComposition(
            u'||', arg2_non_existence, upper_bound_clause)

    filter_predicate = expressions.BinaryComposition(
        u'&&', lower_bound_clause, upper_bound_clause)
    return blocks.Filter(filter_predicate)


@scalar_leaf_only(u'in_collection')
@takes_parameters(1)
def _process_in_collection_filter_directive(schema, current_schema_type, ast,
                                            context, directive, parameters):
    """Return a Filter basic block that checks for a value's existence in a collection.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        directive: GraphQL directive object, obtained from the AST node
        parameters: list of 1 element, specifying the collection in which the value must exist;
                    if the collection is optional and missing, the check is assumed to be False

    Returns:
        a Filter basic block that performs the collection existence check
    """
    field_name = get_ast_field_name(ast)

    argument_inferred_type = GraphQLList(strip_non_null_from_type(current_schema_type))
    argument_expression, non_existence_expression = _represent_argument(
        schema, ast, context, parameters[0], argument_inferred_type)

    filter_predicate = expressions.BinaryComposition(
        u'contains', argument_expression, expressions.LocalField(field_name))
    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        filter_predicate = expressions.BinaryComposition(
            u'||', non_existence_expression, filter_predicate)

    return blocks.Filter(filter_predicate)


@scalar_leaf_only(u'has_substring')
@takes_parameters(1)
def _process_has_substring_filter_directive(schema, current_schema_type, ast,
                                            context, directive, parameters):
    """Return a Filter basic block that checks if the directive arg is a substring of the field.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        directive: GraphQL directive object, obtained from the AST node
        parameters: list of 1 element, specifying the collection in which the value must exist;
                    if the collection is optional and missing, the check is assumed to be False

    Returns:
        a Filter basic block that performs the substring check
    """
    if not strip_non_null_from_type(current_schema_type).is_same_type(GraphQLString):
        raise GraphQLCompilationError(u'Cannot apply "has_substring" to non-string '
                                      u'type {}'.format(current_schema_type))
    argument_inferred_type = GraphQLString

    field_name = get_ast_field_name(ast)

    argument_expression, non_existence_expression = _represent_argument(
        schema, ast, context, parameters[0], argument_inferred_type)

    filter_predicate = expressions.BinaryComposition(
        u'has_substring', expressions.LocalField(field_name), argument_expression)
    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        filter_predicate = expressions.BinaryComposition(
            u'||', non_existence_expression, filter_predicate)

    return blocks.Filter(filter_predicate)


@takes_parameters(1)
def _process_contains_filter_directive(schema, current_schema_type, ast,
                                       context, directive, parameters):
    """Return a Filter basic block that checks if the directive arg is contained in the field.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        directive: GraphQL directive object, obtained from the AST node
        parameters: list of 1 element, specifying the collection in which the value must exist;
                    if the collection is optional and missing, the check is assumed to be False

    Returns:
        a Filter basic block that performs the substring check
    """
    base_field_type = strip_non_null_from_type(current_schema_type)
    if not isinstance(base_field_type, GraphQLList):
        raise GraphQLCompilationError(u'Cannot apply "contains" to non-list '
                                      u'type {}'.format(current_schema_type))

    field_name = get_ast_field_name(ast)

    argument_inferred_type = strip_non_null_from_type(base_field_type.of_type)
    argument_expression, non_existence_expression = _represent_argument(
        schema, ast, context, parameters[0], argument_inferred_type)

    filter_predicate = expressions.BinaryComposition(
        u'contains', expressions.LocalField(field_name), argument_expression)
    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        filter_predicate = expressions.BinaryComposition(
            u'||', non_existence_expression, filter_predicate)

    return blocks.Filter(filter_predicate)


###
# Public API
###

def process_filter_directive(schema, current_schema_type, ast, context, directive):
    """Return a Filter basic block that corresponds to the filter operation in the directive.

    Args:
        schema: GraphQL schema object, obtained from the graphql library
        current_schema_type: GraphQLType, the schema type at the current location
        ast: GraphQL AST node, obtained from the graphql library
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        directive: GraphQL @filter directive object, obtained from the AST node

    Returns:
        a Filter basic block that performs the requested filtering operation
    """
    args = get_uniquely_named_objects_by_name(directive.arguments)
    if 'op_name' not in args:
        raise AssertionError(u'op_name not found in filter directive arguments!'
                             u'Validation should have caught this: {}'.format(directive))

    # HACK(predrag): Workaround for graphql-core validation issue
    #                https://github.com/graphql-python/graphql-core/issues/97
    if not isinstance(args['value'].value, ListValue):
        raise GraphQLValidationError(u'Filter directive value was not a list: {}'.format(directive))

    op_name = args['op_name'].value.value
    operator_params = [x.value for x in args['value'].value.values]

    comparison_operators = {u'=', u'!=', u'>', u'<', u'>=', u'<='}

    if op_name in comparison_operators:
        process_func = partial(_process_comparison_filter_directive, operator=op_name)
    else:
        known_filter_types = {
            u'name_or_alias': _process_name_or_alias_filter_directive,
            u'between': _process_between_filter_directive,
            u'in_collection': _process_in_collection_filter_directive,
            u'has_substring': _process_has_substring_filter_directive,
            u'contains': _process_contains_filter_directive,
        }
        process_func = known_filter_types.get(op_name, None)

    if process_func is None:
        raise GraphQLCompilationError(u'Unknown op_name for filter directive: {}'.format(op_name))

    return process_func(schema, current_schema_type, ast, context, directive, operator_params)
