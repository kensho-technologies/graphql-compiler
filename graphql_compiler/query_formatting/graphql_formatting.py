# Copyright 2017 Kensho Technologies, Inc.
import re

from graphql import parse, print_ast


def fix_indentation_depth(query):
    """Make indentation use 4 spaces, rather than the 2 spaces GraphQL normally uses."""
    lines = query.split('\n')
    final_lines = []

    for line in lines:
        consecutive_spaces = 0
        for char in line:
            if char == ' ':
                consecutive_spaces += 1
            else:
                break

        if consecutive_spaces % 2 != 0:
            raise AssertionError(u'Indentation was not a multiple of two: '
                                 u'{}'.format(consecutive_spaces))

        final_lines.append(('  ' * consecutive_spaces) + line[consecutive_spaces:])

    return '\n'.join(final_lines)


def fix_filter_directive_order(query):
    """Reverse the order of filter arguments. GraphQL insists on printing them backwards."""
    filter_directive_pattern = (
        r'@filter\('
        r'value: \['
        r'("[$%][a-zA-Z0-9_]+"'         # start of capture group 1 at start of this line
        r'(?:, "[$%][a-zA-Z0-9_]+")*)'  # end of capture group 1 at end of this line
        r'\], '
        r'op_name: '
        r'("[^"]+")'                    # capture group 2 on this line
        r'\)'
    )

    replacement_pattern = (
        r'@filter(op_name: \2, value: [\1])'
    )

    return re.sub(filter_directive_pattern, replacement_pattern, query)


def pretty_print_graphql(query, use_four_spaces=True):
    """Take a GraphQL query, pretty print it, and return it."""
    # Use the built-in AST printer to get the canonical representation.
    output = print_ast(parse(query))

    # Use four spaces for indentation, to make it easier up to edit in Python source files.
    if use_four_spaces:
        output = fix_indentation_depth(output)

    # @filter directives are much easier to read if the operation comes before the values.
    # The default AST printer seems to like outputting the values before the operation, so
    # the filtering operation ends up written in postfix order. Use regex to correct that.
    output = fix_filter_directive_order(output)

    return output
