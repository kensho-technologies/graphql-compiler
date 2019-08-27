# Copyright 2017-present Kensho Technologies, LLC.
from functools import partial, wraps

from graphql import GraphQLInt, GraphQLList, GraphQLScalarType, GraphQLString, GraphQLUnionType
from graphql.language.ast import InlineFragment, ListValue
from graphql.type.definition import is_leaf_type

from . import blocks, expressions
from ..exceptions import GraphQLCompilationError, GraphQLValidationError
from ..schema import is_vertex_field_name
from .helpers import (
    get_uniquely_named_objects_by_name, is_runtime_parameter, is_tagged_parameter,
    is_vertex_field_type, strip_non_null_from_type, validate_runtime_argument_name,
    validate_tagged_argument_name
)
from .metadata import FilterInfo


def scalar_leaf_only(operator):
    """Ensure the filter function is only applied to scalar leaf types."""
    def decorator(f):
        """Decorate the supplied function with the "scalar_leaf_only" logic."""
        @wraps(f)
        def wrapper(filter_operation_info, context, parameters, *args, **kwargs):
            """Check that the type on which the operator operates is a scalar leaf type."""
            if 'operator' in kwargs:
                current_operator = kwargs['operator']
            else:
                # Because "operator" is from an enclosing scope, it is immutable in Python 2.x.
                current_operator = operator

            if not is_leaf_type(filter_operation_info.field_type):
                raise GraphQLCompilationError(u'Cannot apply "{}" filter to non-leaf type'
                                              u'{}'.format(current_operator, filter_operation_info))
            return f(filter_operation_info, context, parameters, *args, **kwargs)

        return wrapper

    return decorator


def vertex_field_only(operator):
    """Ensure the filter function is only applied to vertex field types."""
    def decorator(f):
        """Decorate the supplied function with the "vertex_field_only" logic."""
        @wraps(f)
        def wrapper(filter_operation_info, context, parameters, *args, **kwargs):
            """Check that the type on which the operator operates is a vertex field type."""
            if 'operator' in kwargs:
                current_operator = kwargs['operator']
            else:
                # Because "operator" is from an enclosing scope, it is immutable in Python 2.x.
                current_operator = operator

            if not is_vertex_field_type(filter_operation_info.field_type):
                raise GraphQLCompilationError(
                    u'Cannot apply "{}" filter to non-vertex field: '
                    u'{}'.format(current_operator, filter_operation_info.field_name))
            return f(filter_operation_info, context, parameters, *args, **kwargs)

        return wrapper

    return decorator


def takes_parameters(count):
    """Ensure the filter function has "count" parameters specified."""
    def decorator(f):
        """Decorate the supplied function with the "takes_parameters" logic."""
        @wraps(f)
        def wrapper(filter_operation_info, location, context, parameters, *args, **kwargs):
            """Check that the supplied number of parameters equals the expected number."""
            if len(parameters) != count:
                raise GraphQLCompilationError(u'Incorrect number of parameters, expected {} got '
                                              u'{}: {}'.format(count, len(parameters), parameters))

            return f(filter_operation_info, location, context, parameters, *args, **kwargs)

        return wrapper

    return decorator


def _represent_argument(directive_location, context, argument, inferred_type):
    """Return a two-element tuple that represents the argument to the directive being processed.

    Args:
        directive_location: Location where the directive is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        argument: string, the name of the argument to the directive
        inferred_type: GraphQL type object specifying the inferred type of the argument

    Returns:
        (argument_expression, non_existence_expression)
            - argument_expression: an Expression object that captures the semantics of the argument
            - non_existence_expression: None or Expression object;
              If the current block is not optional, this is set to None. Otherwise, it is an
              expression that will evaluate to True if the argument is skipped as optional and
              therefore not present, and False otherwise.
    """
    argument_name = argument[1:]

    if is_runtime_parameter(argument):
        # We want to validate the argument name after we validated that it is not a literal argument
        # in order to possibly raise an error with a better explanation.
        validate_runtime_argument_name(argument_name)
        existing_type = context['inputs'].get(argument_name, inferred_type)
        if not inferred_type.is_same_type(existing_type):
            raise GraphQLCompilationError(u'Incompatible types inferred for argument {}. '
                                          u'The argument cannot simultaneously be '
                                          u'{} and {}.'.format(argument, existing_type,
                                                               inferred_type))
        context['inputs'][argument_name] = inferred_type

        return (expressions.Variable(argument, inferred_type), None)
    elif is_tagged_parameter(argument):
        # We want to validate the argument name after we validated that it is not a literal argument
        # in order to possibly raise an error with a better explanation.
        validate_tagged_argument_name(argument_name)
        tag_info = context['metadata'].get_tag_info(argument_name)
        if tag_info is None:
            raise GraphQLCompilationError(u'Undeclared argument used: {}'.format(argument))

        location = tag_info.location
        optional = tag_info.optional
        tag_inferred_type = tag_info.type

        if location is None:
            raise AssertionError(u'Argument declared without location: {}'.format(argument_name))

        if location.field is None:
            raise AssertionError(u'Argument location is not a property field: {}'.format(location))

        if not inferred_type.is_same_type(tag_inferred_type):
            raise GraphQLCompilationError(u'The inferred type of the matching @tag directive does '
                                          u'not match the inferred required type for this filter: '
                                          u'{} vs {}'.format(tag_inferred_type, inferred_type))

        # Check whether the argument is a field on the vertex on which the directive is applied.
        field_is_local = directive_location.at_vertex() == location.at_vertex()

        non_existence_expression = None
        if optional:
            if field_is_local:
                non_existence_expression = expressions.FalseLiteral
            else:
                non_existence_expression = expressions.BinaryComposition(
                    u'=',
                    expressions.ContextFieldExistence(location.at_vertex()),
                    expressions.FalseLiteral)

        if field_is_local:
            representation = expressions.LocalField(argument_name, inferred_type)
        else:
            representation = expressions.ContextField(location, inferred_type)

        return (representation, non_existence_expression)
    else:
        # If we want to support literal arguments, add them here.
        raise GraphQLCompilationError(u'Invalid argument found: {}. The compiler supports only '
                                      u'runtime arguments, which must begin with the $ character, '
                                      u'and tagged arguments, which must begin with the % '
                                      u'character. Literal arguments, (e.g. 10, \'Kensho '
                                      u'Technologies\', \'2018-01-01\'), are currently not '
                                      u'supported. Please use runtime arguments and pass in the '
                                      u'corresponding literal values as query parameters.'
                                      .format(argument))


@scalar_leaf_only(u'comparison operator')
@takes_parameters(1)
def _process_comparison_filter_directive(filter_operation_info, location,
                                         context, parameters, operator=None):
    """Return a Filter basic block that performs the given comparison against the property field.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        parameters: list of 1 element, specifying the value to which a
                    matching value must be bound; if the value is optional and missing,
                    the check will return True.
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

    filtered_field_type = filter_operation_info.field_type
    filtered_field_name = filter_operation_info.field_name

    argument_inferred_type = strip_non_null_from_type(filtered_field_type)
    argument_expression, non_existence_expression = _represent_argument(
        location, context, parameters[0], argument_inferred_type)

    comparison_expression = expressions.BinaryComposition(
        operator,
        expressions.LocalField(filtered_field_name, filtered_field_type),
        argument_expression)

    final_expression = None
    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        final_expression = expressions.BinaryComposition(
            u'||', non_existence_expression, comparison_expression)
    else:
        final_expression = comparison_expression

    return blocks.Filter(final_expression)


@vertex_field_only(u'has_edge_degree')
@takes_parameters(1)
def _process_has_edge_degree_filter_directive(filter_operation_info, location, context, parameters):
    """Return a Filter basic block that checks the degree of the edge to the given vertex field.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        parameters: list of 1 element, containing the value to check the edge degree against;
                    if the parameter is optional and missing, the check will return True.

    Returns:
        a Filter basic block that performs the check
    """
    if isinstance(filter_operation_info.field_ast, InlineFragment):
        raise AssertionError(u'Received InlineFragment AST node in "has_edge_degree" filter '
                             u'handler. This should have been caught earlier: '
                             u'{}'.format(filter_operation_info.field_ast))

    filtered_field_name = filter_operation_info.field_name
    if filtered_field_name is None or not is_vertex_field_name(filtered_field_name):
        raise AssertionError(u'Invalid value for "filtered_field_name" in "has_edge_degree" '
                             u'filter: {}'.format(filtered_field_name))

    filtered_field_type = filter_operation_info.field_type
    if not is_vertex_field_type(filtered_field_type):
        raise AssertionError(u'Invalid value for "filter_operation_info.field_type" in '
                             u'"has_edge_degree" filter: {}'.format(filter_operation_info))

    argument = parameters[0]
    if not is_runtime_parameter(argument):
        raise GraphQLCompilationError(u'The "has_edge_degree" filter only supports runtime '
                                      u'variable arguments. Tagged values are not supported.'
                                      u'Argument name: {}'.format(argument))

    argument_inferred_type = GraphQLInt
    argument_expression, non_existence_expression = _represent_argument(
        location, context, argument, argument_inferred_type)

    if non_existence_expression is not None:
        raise AssertionError(u'Since we do not support tagged values, non_existence_expression '
                             u'should have been None. However, it was: '
                             u'{}'.format(non_existence_expression))

    # HACK(predrag): Make the handling of vertex field types consistent. Currently, sometimes we
    #                accept lists, and sometimes we don't. Both `Animal` and `[Animal]` should be
    #                acceptable, since the difference there communicates a cardinality constraint
    #                on the edge in question.
    #                Issue: https://github.com/kensho-technologies/graphql-compiler/issues/329
    hacked_field_type = GraphQLList(filtered_field_type)

    # If no edges to the vertex field exist, the edges' field in the database may be "null".
    # We also don't know ahead of time whether the supplied argument is zero or not.
    # We have to accommodate these facts in our generated comparison code.
    # We construct the following expression to check if the edge degree is zero:
    #   ({argument} == 0) && (edge_field == null)
    argument_is_zero = expressions.BinaryComposition(
        u'=', argument_expression, expressions.ZeroLiteral)
    edge_field_is_null = expressions.BinaryComposition(
        u'=',
        expressions.LocalField(filtered_field_name, hacked_field_type),
        expressions.NullLiteral)
    edge_degree_is_zero = expressions.BinaryComposition(
        u'&&', argument_is_zero, edge_field_is_null)

    # The following expression will check for a non-zero edge degree equal to the argument.
    #  (edge_field != null) && (edge_field.size() == {argument})
    edge_field_is_not_null = expressions.BinaryComposition(
        u'!=',
        expressions.LocalField(filtered_field_name, hacked_field_type),
        expressions.NullLiteral)
    edge_degree = expressions.UnaryTransformation(
        u'size',
        expressions.LocalField(filtered_field_name, hacked_field_type))
    edge_degree_matches_argument = expressions.BinaryComposition(
        u'=', edge_degree, argument_expression)
    edge_degree_is_non_zero = expressions.BinaryComposition(
        u'&&', edge_field_is_not_null, edge_degree_matches_argument)

    # We combine the two cases with a logical-or to handle both situations:
    filter_predicate = expressions.BinaryComposition(
        u'||', edge_degree_is_zero, edge_degree_is_non_zero)
    return blocks.Filter(filter_predicate)


@vertex_field_only(u'name_or_alias')
@takes_parameters(1)
def _process_name_or_alias_filter_directive(filter_operation_info, location, context, parameters):
    """Return a Filter basic block that checks for a match against an Entity's name or alias.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        parameters: list of 1 element, specifying the value to which a
                    matching value must be bound; if the value is optional and missing,
                    the check will return True.

    Returns:
        a Filter basic block that performs the check against the name or alias
    """
    filtered_field_type = filter_operation_info.field_type
    if isinstance(filtered_field_type, GraphQLUnionType):
        raise GraphQLCompilationError(u'Cannot apply "name_or_alias" to union type '
                                      u'{}'.format(filtered_field_type))

    current_type_fields = filtered_field_type.fields
    name_field_name = 'name'
    alias_field_name = 'alias'
    name_field = current_type_fields.get(name_field_name, None)
    alias_field = current_type_fields.get(alias_field_name, None)
    if name_field is None:
        raise GraphQLCompilationError(u'Cannot apply "name_or_alias" to type {} because it lacks a '
                                      u'"{}" field.'.format(filtered_field_type, name_field_name))
    if alias_field is None:
        raise GraphQLCompilationError(u'Cannot apply "name_or_alias" to type {} because it lacks a '
                                      u'"{}" field.'.format(filtered_field_type, alias_field_name))

    name_field_type = strip_non_null_from_type(name_field.type)
    alias_field_type = strip_non_null_from_type(alias_field.type)

    if not isinstance(name_field_type, GraphQLScalarType):
        raise GraphQLCompilationError(u'Cannot apply "name_or_alias" to type {} because its "name" '
                                      u'field is not a scalar.'.format(filtered_field_type))
    if not isinstance(alias_field_type, GraphQLList):
        raise GraphQLCompilationError(u'Cannot apply "name_or_alias" to type {} because its '
                                      u'"alias" field is not a list.'.format(filtered_field_type))

    alias_field_inner_type = strip_non_null_from_type(alias_field_type.of_type)
    if alias_field_inner_type != name_field_type:
        raise GraphQLCompilationError(u'Cannot apply "name_or_alias" to type {} because the '
                                      u'"{}" field and the inner type of the "{}" field '
                                      u'do not match: {} vs {}'
                                      .format(filtered_field_type, name_field_name,
                                              alias_field_name, name_field_type,
                                              alias_field_inner_type))

    argument_inferred_type = name_field_type
    argument_expression, non_existence_expression = _represent_argument(
        location, context, parameters[0], argument_inferred_type)

    check_against_name = expressions.BinaryComposition(
        u'=', expressions.LocalField(name_field_name, name_field.type), argument_expression)
    check_against_alias = expressions.BinaryComposition(
        u'contains',
        expressions.LocalField(alias_field_name, alias_field.type),
        argument_expression)
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
def _process_between_filter_directive(filter_operation_info, location, context, parameters):
    """Return a Filter basic block that checks that a field is between two values, inclusive.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        parameters: list of 2 elements, specifying the time range in which the data must lie;
                    if either of the elements is optional and missing,
                    their side of the check is assumed to be True

    Returns:
        a Filter basic block that performs the range check
    """
    filtered_field_type = filter_operation_info.field_type
    filtered_field_name = filter_operation_info.field_name

    argument_inferred_type = strip_non_null_from_type(filtered_field_type)
    arg1_expression, arg1_non_existence = _represent_argument(
        location, context, parameters[0], argument_inferred_type)
    arg2_expression, arg2_non_existence = _represent_argument(
        location, context, parameters[1], argument_inferred_type)

    lower_bound_clause = expressions.BinaryComposition(
        u'>=', expressions.LocalField(filtered_field_name, filtered_field_type), arg1_expression)
    if arg1_non_existence is not None:
        # The argument is optional, and if it doesn't exist, this side of the check should pass.
        lower_bound_clause = expressions.BinaryComposition(
            u'||', arg1_non_existence, lower_bound_clause)

    upper_bound_clause = expressions.BinaryComposition(
        u'<=', expressions.LocalField(filtered_field_name, filtered_field_type), arg2_expression)
    if arg2_non_existence is not None:
        # The argument is optional, and if it doesn't exist, this side of the check should pass.
        upper_bound_clause = expressions.BinaryComposition(
            u'||', arg2_non_existence, upper_bound_clause)

    filter_predicate = expressions.BinaryComposition(
        u'&&', lower_bound_clause, upper_bound_clause)
    return blocks.Filter(filter_predicate)


@scalar_leaf_only(u'in_collection')
@takes_parameters(1)
def _process_in_collection_filter_directive(filter_operation_info, location, context, parameters):
    """Return a Filter basic block that checks for a value's existence in a collection.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        parameters: list of 1 element, specifying the value to which a
                    matching value must be bound; if the value is optional and missing,
                    the check will return True.

    Returns:
        a Filter basic block that performs the collection existence check
    """
    filtered_field_type = filter_operation_info.field_type
    filtered_field_name = filter_operation_info.field_name

    argument_inferred_type = GraphQLList(strip_non_null_from_type(filtered_field_type))
    argument_expression, non_existence_expression = _represent_argument(
        location, context, parameters[0], argument_inferred_type)

    filter_predicate = expressions.BinaryComposition(
        u'contains',
        argument_expression,
        expressions.LocalField(filtered_field_name, filtered_field_type))
    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        filter_predicate = expressions.BinaryComposition(
            u'||', non_existence_expression, filter_predicate)

    return blocks.Filter(filter_predicate)


@scalar_leaf_only(u'not_in_collection')
@takes_parameters(1)
def _process_not_in_collection_filter_directive(filter_operation_info, location, context,
                                                parameters):
    """Return a Filter basic block that checks for a value's non-existence in a collection.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        parameters: list of 1 element, specifying the value to which a
                    matching value must be bound; if the value is optional and missing,
                    the check will return True.

    Returns:
        a Filter basic block that performs the collection existence check
    """
    filtered_field_type = filter_operation_info.field_type
    filtered_field_name = filter_operation_info.field_name

    argument_inferred_type = GraphQLList(strip_non_null_from_type(filtered_field_type))
    argument_expression, non_existence_expression = _represent_argument(
        location, context, parameters[0], argument_inferred_type)

    filter_predicate = expressions.BinaryComposition(
        u'not_contains',
        argument_expression,
        expressions.LocalField(filtered_field_name, filtered_field_type))
    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        filter_predicate = expressions.BinaryComposition(
            u'||', non_existence_expression, filter_predicate)

    return blocks.Filter(filter_predicate)


@scalar_leaf_only(u'has_substring')
@takes_parameters(1)
def _process_has_substring_filter_directive(filter_operation_info, location, context, parameters):
    """Return a Filter basic block that checks if the directive arg is a substring of the field.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
       parameters: list of 1 element, specifying the value to which a
                    matching value must be bound; if the value is optional and missing,
                    the check will return True.

    Returns:
        a Filter basic block that performs the substring check
    """
    filtered_field_type = filter_operation_info.field_type
    filtered_field_name = filter_operation_info.field_name

    if not strip_non_null_from_type(filtered_field_type).is_same_type(GraphQLString):
        raise GraphQLCompilationError(u'Cannot apply "has_substring" to non-string '
                                      u'type {}'.format(filtered_field_type))
    argument_inferred_type = GraphQLString

    argument_expression, non_existence_expression = _represent_argument(
        location, context, parameters[0], argument_inferred_type)

    filter_predicate = expressions.BinaryComposition(
        u'has_substring',
        expressions.LocalField(filtered_field_name, filtered_field_type),
        argument_expression)
    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        filter_predicate = expressions.BinaryComposition(
            u'||', non_existence_expression, filter_predicate)

    return blocks.Filter(filter_predicate)


@scalar_leaf_only(u'ends_with')
@takes_parameters(1)
def _process_ends_with_filter_directive(filter_operation_info, location, context, parameters):
    """Return a Filter basic block that checks if the directive arg is the string suffix of the field.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        parameters: list of 1 element, specifying the value to which a
                    matching value must be bound; if the value is optional and missing,
                    the check will return True.

    Returns:
        a Filter basic block that performs the substring check
    """
    filtered_field_type = filter_operation_info.field_type
    filtered_field_name = filter_operation_info.field_name

    if not strip_non_null_from_type(filtered_field_type).is_same_type(GraphQLString):
        raise GraphQLCompilationError(u'Cannot apply "ends_with" to non-string '
                                      u'type {}'.format(filtered_field_type))
    argument_inferred_type = GraphQLString

    argument_expression, non_existence_expression = _represent_argument(
        location, context, parameters[0], argument_inferred_type)

    filter_predicate = expressions.BinaryComposition(
        u'ends_with',
        expressions.LocalField(filtered_field_name, filtered_field_type),
        argument_expression)
    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        filter_predicate = expressions.BinaryComposition(
            u'||', non_existence_expression, filter_predicate)

    return blocks.Filter(filter_predicate)


@scalar_leaf_only(u'starts_with')
@takes_parameters(1)
def _process_starts_with_filter_directive(filter_operation_info, location, context, parameters):
    """Return a Filter basic block that checks if the directive arg is the string prefix of the field.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        parameters: list of 1 element, specifying the value to which a
                    matching value must be bound; if the value is optional and missing,
                    the check will return True.

    Returns:
        a Filter basic block that performs the substring check
    """
    filtered_field_type = filter_operation_info.field_type
    filtered_field_name = filter_operation_info.field_name

    if not strip_non_null_from_type(filtered_field_type).is_same_type(GraphQLString):
        raise GraphQLCompilationError(u'Cannot apply "starts_with" to non-string '
                                      u'type {}'.format(filtered_field_type))
    argument_inferred_type = GraphQLString

    argument_expression, non_existence_expression = _represent_argument(
        location, context, parameters[0], argument_inferred_type)

    filter_predicate = expressions.BinaryComposition(
        u'starts_with',
        expressions.LocalField(filtered_field_name, filtered_field_type),
        argument_expression)
    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        filter_predicate = expressions.BinaryComposition(
            u'||', non_existence_expression, filter_predicate)

    return blocks.Filter(filter_predicate)


@takes_parameters(1)
def _process_contains_filter_directive(filter_operation_info, location, context, parameters):
    """Return a Filter basic block that checks if the directive arg is contained in the field.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        parameters: list of 1 element, specifying the value to which a
                    matching value must be bound; if the value is optional and missing,
                    the check will return True.

    Returns:
        a Filter basic block that performs the contains check
    """
    filtered_field_type = filter_operation_info.field_type
    filtered_field_name = filter_operation_info.field_name

    base_field_type = strip_non_null_from_type(filtered_field_type)

    if base_field_type.is_same_type(GraphQLString):
        raise GraphQLCompilationError(u'Cannot apply "contains" to non-list '
                                      u'type String. Consider using the "has_substring" '
                                      u'operator instead.')

    if not isinstance(base_field_type, GraphQLList):
        raise GraphQLCompilationError(u'Cannot apply "contains" to non-list '
                                      u'type {}'.format(filtered_field_type))

    argument_inferred_type = strip_non_null_from_type(base_field_type.of_type)
    argument_expression, non_existence_expression = _represent_argument(
        location, context, parameters[0], argument_inferred_type)

    filter_predicate = expressions.BinaryComposition(
        u'contains',
        expressions.LocalField(filtered_field_name, filtered_field_type),
        argument_expression)
    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        filter_predicate = expressions.BinaryComposition(
            u'||', non_existence_expression, filter_predicate)

    return blocks.Filter(filter_predicate)


@takes_parameters(1)
def _process_not_contains_filter_directive(filter_operation_info, location, context, parameters):
    """Return a Filter basic block that checks if the directive arg is not contained in the field.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        parameters: list of 1 element, specifying the value to which a
                    matching value must be bound; if the value is optional and missing,
                    the check will return True.

    Returns:
        a Filter basic block that performs the contains check
    """
    filtered_field_type = filter_operation_info.field_type
    filtered_field_name = filter_operation_info.field_name

    base_field_type = strip_non_null_from_type(filtered_field_type)
    if not isinstance(base_field_type, GraphQLList):
        raise GraphQLCompilationError(u'Cannot apply "not_contains" to non-list '
                                      u'type {}'.format(filtered_field_type))

    argument_inferred_type = strip_non_null_from_type(base_field_type.of_type)
    argument_expression, non_existence_expression = _represent_argument(
        location, context, parameters[0], argument_inferred_type)

    filter_predicate = expressions.BinaryComposition(
        u'not_contains',
        expressions.LocalField(filtered_field_name, filtered_field_type),
        argument_expression)
    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        filter_predicate = expressions.BinaryComposition(
            u'||', non_existence_expression, filter_predicate)

    return blocks.Filter(filter_predicate)


@takes_parameters(1)
def _process_intersects_filter_directive(filter_operation_info, location, context, parameters):
    """Return a Filter basic block that checks if the directive arg and the field intersect.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        parameters: list of 1 element, specifying the value to which a
                    matching value must be bound; if the value is optional and missing,
                    the check will return True.

    Returns:
        a Filter basic block that performs the intersects check
    """
    filtered_field_type = filter_operation_info.field_type
    filtered_field_name = filter_operation_info.field_name

    argument_inferred_type = strip_non_null_from_type(filtered_field_type)
    if not isinstance(argument_inferred_type, GraphQLList):
        raise GraphQLCompilationError(u'Cannot apply "intersects" to non-list '
                                      u'type {}'.format(filtered_field_type))

    argument_expression, non_existence_expression = _represent_argument(
        location, context, parameters[0], argument_inferred_type)

    filter_predicate = expressions.BinaryComposition(
        u'intersects',
        expressions.LocalField(filtered_field_name, filtered_field_type),
        argument_expression)
    if non_existence_expression is not None:
        # The argument comes from an optional block and might not exist,
        # in which case the filter expression should evaluate to True.
        filter_predicate = expressions.BinaryComposition(
            u'||', non_existence_expression, filter_predicate)

    return blocks.Filter(filter_predicate)


@takes_parameters(0)
def _process_is_null_filter_directive(filter_operation_info, location, context, parameters):
    """Return a Filter basic block that ensures the property field is Null.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        parameters: empty list

    Returns:
        a Filter basic block that performs the null check
    """
    filtered_field_type = filter_operation_info.field_type
    filtered_field_name = filter_operation_info.field_name

    if len(parameters) != 0:
        raise GraphQLCompilationError(u'No parameters should be passed to "is_null" filter. '
                                      u'Received parameter(s) {}'.format(parameters))

    comparison_expression = expressions.BinaryComposition(
        u'=',
        expressions.LocalField(filtered_field_name, filtered_field_type),
        expressions.NullLiteral)

    return blocks.Filter(comparison_expression)


@takes_parameters(0)
def _process_is_not_null_filter_directive(filter_operation_info, location, context, parameters):
    """Return a Filter basic block that ensures the property field is not Null.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!
        parameters: empty list

    Returns:
        a Filter basic block that performs the null check
    """
    filtered_field_type = filter_operation_info.field_type
    filtered_field_name = filter_operation_info.field_name

    if len(parameters) != 0:
        raise GraphQLCompilationError(u'No parameters should be passed to "is_not_null" filter. '
                                      u'Received parameter(s) {}'.format(parameters))

    comparison_expression = expressions.BinaryComposition(
        u'!=',
        expressions.LocalField(filtered_field_name, filtered_field_type),
        expressions.NullLiteral)

    return blocks.Filter(comparison_expression)


def _get_filter_op_name_and_values(directive):
    """Extract the (op_name, operator_params) tuple from a directive object."""
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

    return (op_name, operator_params)


###
# Public API
###

COMPARISON_OPERATORS = frozenset({u'=', u'!=', u'>', u'<', u'>=', u'<='})
PROPERTY_FIELD_OPERATORS = COMPARISON_OPERATORS | frozenset({
    u'between',
    u'in_collection',
    u'not_in_collection',
    u'contains',
    u'not_contains',
    u'intersects',
    u'has_substring',
    u'starts_with',
    u'ends_with',
    u'has_edge_degree',
    u'is_null',
    u'is_not_null',
})

# Vertex field filtering operators can apply to the inner scope or the outer scope.
# Consider:
# {
#     Foo {
#         out_Foo_Bar @filter(op_name: "...", value: [...]) {
#             ...
#         }
#     }
# }
#
# If the filter on out_Foo_Bar filters the Foo, we say that it filters the outer scope.
# Instead, if the filter filters the Bar connected to the Foo, it filters the inner scope.
INNER_SCOPE_VERTEX_FIELD_OPERATORS = frozenset({u'name_or_alias'})
OUTER_SCOPE_VERTEX_FIELD_OPERATORS = frozenset({u'has_edge_degree'})

VERTEX_FIELD_OPERATORS = INNER_SCOPE_VERTEX_FIELD_OPERATORS | OUTER_SCOPE_VERTEX_FIELD_OPERATORS

ALL_OPERATORS = PROPERTY_FIELD_OPERATORS | VERTEX_FIELD_OPERATORS


def is_filter_with_outer_scope_vertex_field_operator(directive):
    """Return True if we have a filter directive whose operator applies to the outer scope."""
    if directive.name.value != 'filter':
        return False

    op_name, _ = _get_filter_op_name_and_values(directive)
    return op_name in OUTER_SCOPE_VERTEX_FIELD_OPERATORS


def process_filter_directive(filter_operation_info, location, context):
    """Return a Filter basic block that corresponds to the filter operation in the directive.

    Args:
        filter_operation_info: FilterOperationInfo object, containing the directive and field info
                               of the field where the filter is to be applied.
        location: Location where this filter is used.
        context: dict, various per-compilation data (e.g. declared tags, whether the current block
                 is optional, etc.). May be mutated in-place in this function!

    Returns:
        a Filter basic block that performs the requested filtering operation
    """
    op_name, operator_params = _get_filter_op_name_and_values(filter_operation_info.directive)

    non_comparison_filters = {
        u'name_or_alias': _process_name_or_alias_filter_directive,
        u'between': _process_between_filter_directive,
        u'in_collection': _process_in_collection_filter_directive,
        u'not_in_collection': _process_not_in_collection_filter_directive,
        u'has_substring': _process_has_substring_filter_directive,
        u'starts_with': _process_starts_with_filter_directive,
        u'ends_with': _process_ends_with_filter_directive,
        u'contains': _process_contains_filter_directive,
        u'not_contains': _process_not_contains_filter_directive,
        u'intersects': _process_intersects_filter_directive,
        u'has_edge_degree': _process_has_edge_degree_filter_directive,
        u'is_null': _process_is_null_filter_directive,
        u'is_not_null': _process_is_not_null_filter_directive,
    }
    all_recognized_filters = frozenset(non_comparison_filters.keys()) | COMPARISON_OPERATORS
    if all_recognized_filters != ALL_OPERATORS:
        unrecognized_filters = ALL_OPERATORS - all_recognized_filters
        raise AssertionError(u'Some filtering operators are defined but do not have an associated '
                             u'processing function. This is a bug: {}'.format(unrecognized_filters))

    if op_name in COMPARISON_OPERATORS:
        process_func = partial(_process_comparison_filter_directive, operator=op_name)
    else:
        process_func = non_comparison_filters.get(op_name, None)

    if process_func is None:
        raise GraphQLCompilationError(u'Unknown op_name for filter directive: {}'.format(op_name))

    # Operators that do not affect the inner scope require a field name to which they apply.
    # There is no field name on InlineFragment ASTs, which is why only operators that affect
    # the inner scope make semantic sense when applied to InlineFragments.
    # Here, we ensure that we either have a field name to which the filter applies,
    # or that the operator affects the inner scope.
    if (filter_operation_info.field_name is None and
            op_name not in INNER_SCOPE_VERTEX_FIELD_OPERATORS):
        raise GraphQLCompilationError(u'The filter with op_name "{}" must be applied on a field. '
                                      u'It may not be applied on a type coercion.'.format(op_name))

    fields = ((filter_operation_info.field_name,) if op_name != 'name_or_alias'
              else ('name', 'alias'))

    context['metadata'].record_filter_info(
        location,
        FilterInfo(fields=fields, op_name=op_name, args=tuple(operator_params))
    )

    return process_func(filter_operation_info, location, context, operator_params)
