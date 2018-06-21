import random
from uuid import UUID

import six


random.seed(0)

CREATE_VERTEX = 'create vertex '
CREATE_EDGE = 'create edge '
SEPARATOR = '__'


def get_uuid():
    """Return a pseudorandom uuid."""
    return str(random.randint(0, 2**128 - 1))


def select_vertex_statement(vertex_type, name):
    """Return a SQL statement to select a vertex of given type by its `name` field."""
    template = '(select from {vertex_type} where name = \'{name}\')'
    args = {'vertex_type': vertex_type, 'name': name}
    return template.format(**args)


def set_statement(field_name, field_value):
    """Return a SQL clause (used in creating a vertex) to set a field to a value."""
    if not isinstance(field_name, six.string_types):
        raise AssertionError(u'Expected string field_name. Received {}'.format(field_name))
    if not isinstance(field_value, six.string_types):
        raise AssertionError(u'Expected string field_value. Received {}'.format(field_value))
    template = '{} = \'{}\''
    return template.format(field_name, field_value)


def create_vertex_statement(vertex_type, field_name_to_value):
    """Return a SQL statement to create a vertex."""
    statement = CREATE_VERTEX + vertex_type
    set_field_clauses = [
        set_statement(field_name, field_name_to_value[field_name])
        for field_name in sorted(six.iterkeys(field_name_to_value))
    ]
    statement += ' set ' + ', '.join(set_field_clauses)
    return statement


def create_edge_statement(edge_name, from_class, from_name, to_class, to_name):
    """Return a SQL statement to create a edge."""
    statement = CREATE_EDGE + edge_name + ' from {} to {}'
    from_select = select_vertex_statement(from_class, from_name)
    to_select = select_vertex_statement(to_class, to_name)
    return statement.format(from_select, to_select)


def create_name(base_name, label):
    """Return a name formed by joining a base name with a label."""
    return base_name + SEPARATOR + label


def strip_index_from_name(name):
    """Extract and return a pair of (base_name, label) from a given name field."""
    if not isinstance(name, six.string_types):
        raise AssertionError(u'Expected string name. Received {}'.format(name))
    split_name = name.split(SEPARATOR)
    if len(split_name) != 2:
        raise AssertionError(u'Expected a sting with a single occurrence of {}. Got {}'
                             .format(SEPARATOR, name))
    return split_name
