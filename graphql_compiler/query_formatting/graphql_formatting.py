# Copyright 2017-present Kensho Technologies, LLC.
from graphql import parse
from graphql.language.printer import PrintingVisitor, join, wrap
from graphql.language.visitor import visit
import six

from ..schema import DIRECTIVES


def pretty_print_graphql(query, use_four_spaces=True):
    """Take a GraphQL query, pretty print it, and return it."""
    # Use our custom visitor, which fixes directive argument order
    # to get the canonical representation
    output = visit(parse(query), CustomPrintingVisitor())

    # Using four spaces for indentation makes it easier to edit in
    # Python source files.
    if use_four_spaces:
        return fix_indentation_depth(output)
    return output


DIRECTIVES_BY_NAME = {d.name: d for d in DIRECTIVES}


class CustomPrintingVisitor(PrintingVisitor):
    # Directives are easier to read if their arguments appear in the order in
    # which we defined them in the schema. For example, @filter directives are
    # much easier to read if the operation comes before the values. The
    # arguments of the directives specified in the schema are defined as
    # OrderedDicts which allows us to sort the provided arguments to match.
    def leave_Directive(self, node, *args):
        """Call when exiting a directive node in the ast."""
        name_to_arg_value = {
            # Taking [0] is ok here because the GraphQL parser checks for the
            # existence of ':' in directive arguments.
            arg.split(':', 1)[0]: arg
            for arg in node.arguments
        }

        ordered_args = node.arguments
        directive = DIRECTIVES_BY_NAME.get(node.name)
        if directive:
            sorted_args = []
            encountered_argument_names = set()

            # Iterate through all defined arguments in the directive schema.
            for defined_arg_name in six.iterkeys(directive.args):
                if defined_arg_name in name_to_arg_value:
                    # The argument was present in the query, print it in the correct order.
                    encountered_argument_names.add(defined_arg_name)
                    sorted_args.append(name_to_arg_value[defined_arg_name])

            # Get all the arguments that weren't defined in the directive schema.
            # They will be printed after all the arguments that were in the schema.
            unsorted_args = [
                value
                for name, value in six.iteritems(name_to_arg_value)
                if name not in encountered_argument_names
            ]

            ordered_args = sorted_args + unsorted_args

        return '@' + node.name + wrap('(', join(ordered_args, ', '), ')')


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
