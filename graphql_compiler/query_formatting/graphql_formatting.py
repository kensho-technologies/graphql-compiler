# Copyright 2017 Kensho Technologies, Inc.
import graphql
from graphql import parse
from graphql.language.printer import PrintingVisitor, wrap, join
from graphql.language.visitor import visit
from ..schema import DIRECTIVES


def pretty_print_graphql(query, spaces=4):
    """Take a GraphQL query, pretty print it, and return it."""
    # Use four spaces for indentation, to make it easier up to edit in Python
    # source files.
    old_indent = graphql.language.printer.indent
    graphql.language.printer.indent = _indent_override(spaces)

    output = visit(parse(query), CustomPrinter(spaces))

    graphql.language.printer.indent = old_indent

    return output


def _indent_override(spaces):
    def indent(maybe_str):
        if maybe_str:
            return maybe_str.replace('\n', '\n' + ' ' * spaces)
        return maybe_str
    return indent


class CustomPrinter(PrintingVisitor):
    def __init__(self, spaces=2):
        self._spaces = spaces

    # @filter directives are much easier to read if the operation comes before
    # the values. The default AST printer outputs the values
    # before the operation, so the filtering operation ends up written in
    # postfix order.
    def leave_Directive(self, node, *args):
        args = node.arguments

        def _arg_order(arg, directive):
            defined_arg_names = directive.args.keys()
            # Taking [0] is ok here because the graphql parser checks for the
            # existence of ':' in directive arguments
            arg_name = arg.split(':')[0]
            try:
                return defined_arg_names.index(arg_name)
            except ValueError:
                # This argument name isn't defined in our schema but we should
                # still pretty print it
                return -1

        for directive in DIRECTIVES:
            if directive.name == node.name:
                args = list(sorted(args, key=lambda a, d=directive: _arg_order(a, d)))
                break

        return '@' + node.name + wrap('(', join(args, ', '), ')')
