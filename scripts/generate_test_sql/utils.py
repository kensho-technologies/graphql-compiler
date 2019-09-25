# Copyright 2018-present Kensho Technologies, LLC.
import datetime
from decimal import Decimal
import random
from uuid import UUID

import six


CREATE_VERTEX = 'create vertex '
CREATE_EDGE = 'create edge '
SEPARATOR = '__'


def get_uuid():
    """Return a pseudorandom uuid."""
    return str(UUID(int=random.randint(0, 2**128 - 1)))  # nosec


def get_random_net_worth():
    """Return a pseudorandom net worth."""
    return str(Decimal(int(1e5 * random.random()) / 100.0))  # nosec


def get_random_limbs():
    """Return a pseudorandom number of limbs."""
    return random.randint(2, 10)  # nosec


def get_random_date():
    """Return a pseudorandom date."""
    random_year = random.randint(2000, 2018)  # nosec
    random_month = random.randint(1, 12)  # nosec
    random_day = random.randint(1, 28)  # nosec
    return str(datetime.date(random_year, random_month, random_day))


def create_vertex_statement(vertex_type, field_name_to_value):
    """Return a SQL statement to create a vertex."""
    return {
        'kind': 'vertex',
        'class': vertex_type,
        'properties': field_name_to_value,
    }


def create_edge_statement(edge_name, from_class, from_name, to_class, to_name):
    """Return a SQL statement to create a edge."""
    return {
        'kind': 'edge',
        'class': edge_name,
        'properties': {
            'from_uuid': from_name,
            'to_uuid': to_name,
        }
    }


def create_name(base_name, label):
    """Return a name formed by joining a base name with a label."""
    return base_name + SEPARATOR + label


def extract_base_name_and_label(name):
    """Extract and return a pair of (base_name, label) from a given name field."""
    if not isinstance(name, six.string_types):
        raise AssertionError(u'Expected string name. Received {}'.format(name))
    split_name = name.split(SEPARATOR)
    if len(split_name) != 2:
        raise AssertionError(u'Expected a sting with a single occurrence of {}. Got {}'
                             .format(SEPARATOR, name))
    return split_name
