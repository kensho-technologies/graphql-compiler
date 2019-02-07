from collections import namedtuple

from ...exceptions import GraphQLInvalidMacroError
from .directives import MacroEdgeDirective, MacroEdgeDefinitionDirective, MacroEdgeTargetDirective
from .helpers import get_only_selection_from_ast


MacroEdgeDescriptor = namedtuple(
    'MacroEdgeDescriptor', (
        'expansion_ast',  # GraphQL AST object defining how the macro edge should be expanded
        'macro_args',     # Dict[str, Any] containing any arguments that the macro requires
    )
)


def get_and_validate_macro_edge_info(schema, ast, macro_directives, macro_edge_args,
                                     type_equivalence_hints=None):
    """Return a tuple of ASTs with the three parts of a macro edge given the directive mapping.

    Args:
        schema: GraphQL schema object, created using the GraphQL library
        ast: GraphQL library AST OperationDefinition object, describing the GraphQL that is defining
             the macro edge.
        macro_directives: Dict[str, List[Tuple[AST object, Directive]]], mapping the name of an
                          encountered directive to a list of its appearances, each described by
                          a tuple containing the AST with that directive and the directive object
                          itself.
        macro_edge_args: dict mapping strings to any type, containing any arguments the macro edge
                         requires in order to function.
        type_equivalence_hints: optional dict of GraphQL interface or type -> GraphQL union.
                                Used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces), as well as a
                                workaround for Gremlin's total lack of inheritance-awareness.
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union.
                                Recursive expansion of type equivalence hints is not performed,
                                and only type-level correctness of this argument is enforced.
                                See README.md for more details on everything this parameter does.
                                *****
                                Be very careful with this option, as bad input here will
                                lead to incorrect output queries being generated.
                                *****

    Returns:
        tuple (class name for macro, name of macro edge, MacroEdgeDescriptor),
        where the first two values are strings and the last one is a MacroEdgeDescriptor object
    """
    if ast.directives is not None:
        directive_names = [directive.name.value for directive in ast.directives]
        raise GraphQLInvalidMacroError(
            u'Unexpectedly found directives at the top level of the GraphQL input. '
            u'This is not supported. Directives: {}'.format(directive_names))

    if ast.variable_definitions is not None:
        raise GraphQLInvalidMacroError(
            u'Unexpectedly found variable definitions at the top level of the GraphQL input. '
            u'This is not supported. Variable definitions: {}'.format(ast.variable_definitions))

    unique_and_parameterless_directives_to_check = (
        MacroEdgeDirective,
        MacroEdgeDefinitionDirective,
        MacroEdgeTargetDirective,
    )
    macro_edge_sub_asts = {}

    for directive_definition in unique_and_parameterless_directives_to_check:
        macro_data = macro_directives.get(directive_definition.name, None)
        if not macro_data:
            raise GraphQLInvalidMacroError(
                u'Required macro edge directive "@{}" was not found anywhere within the supplied '
                u'macro edge definition GraphQL.'.format(directive_definition.name))

        if len(macro_data) > 1:
            raise GraphQLInvalidMacroError(
                u'Required macro edge directive "@{}" was unexpectedly present more than once in '
                u'the supplied macro edge definition GraphQL. It was found {} times.'
                .format(directive_definition.name, len(macro_data)))

        macro_ast, macro_directive = macro_data[0]
        if macro_directive.arguments is not None:
            raise GraphQLInvalidMacroError(
                u'Required macro edge directive "@{}" unexpectedly contained arguments even though '
                u'it is not supposed to contain any. Unexpected arguments:'
                .format(directive_definition.name, macro_directive.arguments))

        macro_edge_sub_asts[directive_definition.name] = macro_ast

    # TODO(predrag): Required further validation:
    # - the target directive AST is within the definition directive AST;
    # - the macro edge directive AST is not within the definition directive AST;
    # - the macro edge directive and the definition directive ASTs are directly within the
    #   top-level selection, and that selection contains no ASTs other than these two;
    # - the macro edge directive AST contains no other directives;
    # - the macro definition directive AST contains only @filter/@fold directives together with
    #   the target directive;
    # - the macro edge does not shadow an existing edge;
    # - after adding an output, the macro compiles successfully, the macro args and necessary and
    #   sufficient for the macro, and the macro args' types match the inferred types of the
    #   runtime parameters in the macro.

    class_name = get_only_selection_from_ast(ast).name.value
    macro_edge_name = macro_edge_sub_asts[MacroEdgeDirective.name].name.value

    _make_macro_edge_descriptor()

    return class_name, macro_edge_name


def _make_macro_edge_descriptor():
    """Not implemented yet."""
    raise NotImplementedError()
