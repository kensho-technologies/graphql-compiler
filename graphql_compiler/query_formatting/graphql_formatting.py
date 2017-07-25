# Copyright 2017 Kensho Technologies, Inc.
from graphql import parse
from graphql.language.printer import PrintingVisitor, wrap, join
from graphql.language.visitor import visit


def pretty_print_graphql(query, spaces=4):
    """Take a GraphQL query, pretty print it, and return it."""
    # Use four spaces for indentation, to make it easier up to edit in Python
    # source files.
    output = visit(parse(query), CustomPrinter(spaces))

    return output


class CustomPrinter(PrintingVisitor):
    def __init__(self, spaces=2):
        self._spaces = spaces

    # @filter directives are much easier to read if the operation comes before
    # the values. The default AST printer seems to like outputting the values
    # before the operation, so the filtering operation ends up written in
    # postfix order. Use regex to correct that.
    def leave_Directive(self, node, *args):
        args = node.arguments
        if node.name == 'filter':
            args = list(reversed(args))
        return '@' + node.name + wrap('(', join(args, ', '), ')')

    def leave_SelectionSet(self, node, *args):
        return block(node.selections, self._spaces)

    def leave_SchemaDefinition(self, node, *args):
        return join([
            'schema',
            join(node.directives, ' '),
            block(node.operation_types, self._spaces),
            ], ' ')

    def leave_ObjectTypeDefinition(self, node, *args):
        return join([
            'type',
            node.name,
            wrap('implements ', join(node.interfaces, ', ')),
            join(node.directives, ' '),
            block(node.fields, self._spaces)
        ], ' ')

    def leave_InterfaceTypeDefinition(self, node, *args):
        return 'interface ' + node.name + wrap(' ', join(node.directives, ' ')) + ' ' + block(node.fields, self._spaces)

    def leave_EnumTypeDefinition(self, node, *args):
        return 'enum ' + node.name + wrap(' ', join(node.directives, ' ')) + ' ' + block(node.values, self._spaces)

    def leave_InputObjectTypeDefinition(self, node, *args):
        return 'input ' + node.name + wrap(' ', join(node.directives, ' ')) + ' ' + block(node.fields, self._spaces)


def block(_list, spaces):
    '''Given a list, print each item on its own line, wrapped in an indented "{ }" block.'''
    if _list:
        return indent('{\n' + join(_list, '\n'), spaces) + '\n}'
    return '{}'


def indent(maybe_str, spaces):
    if maybe_str:
        return maybe_str.replace('\n', '\n' + ' ' * spaces)
    return maybe_str
