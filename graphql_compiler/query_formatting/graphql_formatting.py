# Copyright 2017 Kensho Technologies, Inc.
from graphql import parse
from graphql.language.printer import PrintingVisitor, join, wrap
from graphql.language.visitor import visit

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
        # Make a copy of the arguemnts so that we can safely pop
        args = list(node.arguments)
        # Taking [0] is ok here because the graphql parser checks for the
        # existence of ':' in directive arguments
        arg_names = [a.split(':', 1)[0] for a in args]

        directive = DIRECTIVES_BY_NAME.get(node.name)
        if directive:
            sorted_args = []
            for defined_arg in directive.args.keys():
                if defined_arg in arg_names:
                    arg = args.pop(arg_names.index(defined_arg))
                    sorted_args.append(arg)
            args = sorted_args + args

        return '@' + node.name + wrap('(', join(args, ', '), ')')


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
