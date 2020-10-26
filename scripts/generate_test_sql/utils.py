# Copyright 2018-present Kensho Technologies, LLC.
import datetime
from decimal import Decimal
import random
from uuid import UUID

import six


CREATE_VERTEX = "create vertex "
CREATE_EDGE = "create edge "
SEPARATOR = "__"


def get_uuid():
    """Return a pseudorandom uuid."""
    return str(UUID(int=random.randint(0, 2 ** 128 - 1)))  # nosec


def get_random_net_worth():
    """Return a pseudorandom net worth."""
    return Decimal(int(1e5 * random.random()) / 100.0)  # nosec


def get_random_limbs():
    """Return a pseudorandom number of limbs."""
    return random.randint(2, 10)  # nosec


def get_random_date():
    """Return a pseudorandom date."""
    random_year = random.randint(2000, 2018)  # nosec
    random_month = random.randint(1, 12)  # nosec
    random_day = random.randint(1, 28)  # nosec
    return datetime.date(random_year, random_month, random_day)


def select_vertex_statement(vertex_type, name):
    """Return a SQL statement to select a vertex of given type by its `name` field."""
    template = "(select from {vertex_type} where name = '{name}')"
    args = {"vertex_type": vertex_type, "name": name}
    return template.format(**args)


def set_statement(field_name, field_value):
    """Return a SQL clause (used in creating a vertex) to set a field to a value."""
    if not isinstance(field_name, six.string_types):
        raise AssertionError("Expected string field_name. Received {}".format(field_name))
    field_value_representation = repr(field_value)
    if isinstance(field_value, datetime.date):
        field_value_representation = 'DATE("' + field_value.isoformat() + ' 00:00:00")'
    template = "{} = {}"
    return template.format(field_name, field_value_representation)


def create_vertex_statement(vertex_type, field_name_to_value):
    """Return a SQL statement to create a vertex."""
    statement = CREATE_VERTEX + vertex_type
    set_field_clauses = [
        set_statement(field_name, field_name_to_value[field_name])
        for field_name in sorted(six.iterkeys(field_name_to_value))
    ]
    statement += " set " + ", ".join(set_field_clauses)
    return statement


def create_edge_statement(edge_name, from_class, from_name, to_class, to_name):
    """Return a SQL statement to create a edge."""
    statement = CREATE_EDGE + edge_name + " from {} to {}"
    from_select = select_vertex_statement(from_class, from_name)
    to_select = select_vertex_statement(to_class, to_name)
    return statement.format(from_select, to_select)


def create_name(base_name, label):
    """Return a name formed by joining a base name with a label."""
    return base_name + SEPARATOR + label


def extract_base_name_and_label(name):
    """Extract and return a pair of (base_name, label) from a given name field."""
    if not isinstance(name, six.string_types):
        raise AssertionError("Expected string name. Received {}".format(name))
    split_name = name.split(SEPARATOR)
    if len(split_name) != 2:
        raise AssertionError(
            "Expected a sting with a single occurrence of {}. Got {}".format(SEPARATOR, name)
        )
    return split_name
