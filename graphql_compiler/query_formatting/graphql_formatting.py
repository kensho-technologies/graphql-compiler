# Copyright 2017 Kensho Technologies, Inc.
from graphql import parse
from graphql.language.printer import PrintingVisitor, wrap, join
from graphql.language.visitor import visit
from ..schema import DIRECTIVES


def pretty_print_graphql(query, spaces=4):
    """Take a GraphQL query, pretty print it, and return it."""
    # The graphql-core printer module has an indent function outside of the
    # PrintingVisitor class which has two spaces hard coded. Ideally, it would
    # be a member of the class and we could simply override it in our custom
    # printer. To work around this we can set the function inside the module
    # forcefully. This is undesireable as it has a global effect and relies on
    # the implementation details of the print_ast() function, but has the
    # advantage of only modifying the leave_Directive() method on the class as
    # opposed to copying the entire class.
    import graphql

    def indent_override(maybe_str):
        if maybe_str:
            return maybe_str.replace('\n', '\n' + ' ' * spaces)
        return maybe_str
    graphql.language.printer.indent = indent_override

    return visit(parse(query), CustomPrintingVisitor())


class CustomPrintingVisitor(PrintingVisitor):
    # Directives are easier to read if their arguments appear in the order in
    # which we defined them in the schema. For example, @filter directives are
    # much easier to read if the operation comes before the values. The
    # arguments of the directives specified in the schema are defined as
    # OrderedDicts which allows us to sort the provided arguments to match.
    def leave_Directive(self, node, *args):
        args = node.arguments

        def _arg_index(arg, directive):
            defined_arg_names = directive.args.keys()
            # Taking [0] is ok here because the graphql parser checks for the
            # existence of ':' in directive arguments
            arg_name = arg.split(':', 1)[0]
            try:
                return defined_arg_names.index(arg_name)
            except ValueError:
                # This argument name isn't defined in our schema but we should
                # still pretty print it anyway
                return -1

        try:
            directive = next(d for d in DIRECTIVES if d.name == node.name)
            args = list(sorted(args, key=lambda a: _arg_index(a, directive)))
        except StopIteration:
            # The directive wasn't defined in our schema, use whatever order
            # the args appeared in within the query
            pass

        return '@' + node.name + wrap('(', join(args, ', '), ')')
