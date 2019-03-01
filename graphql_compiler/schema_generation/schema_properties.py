# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
import datetime
import time

import six


EDGE_SOURCE_PROPERTY_NAME = 'out'
EDGE_DESTINATION_PROPERTY_NAME = 'in'

ORIENTDB_BASE_VERTEX_CLASS_NAME = 'V'
ORIENTDB_BASE_EDGE_CLASS_NAME = 'E'

ILLEGAL_PROPERTY_NAME_PREFIXES = (
    # Prefixes that would make the GraphQL schema ambiguous,
    # since this is how it represents adjacent vertices.
    'out_',
    'in_',

    # Prefixes reserved for future extensions to the GraphQL schema,
    # in case we want to, e.g., add edge-based traversals, or "both()"-style traversals.
    'outE',
    'inE',
    'outV',
    'inV',
    'both_',
    'bothE_',
    'bothV_',
)

PROPERTY_TYPE_BOOLEAN_ID = 0
PROPERTY_TYPE_BOOLEAN_NAME = 'Boolean'

PROPERTY_TYPE_INTEGER_ID = 1
PROPERTY_TYPE_INTEGER_NAME = 'Integer'

PROPERTY_TYPE_LONG_ID = 3
PROPERTY_TYPE_LONG_NAME = 'Long'

PROPERTY_TYPE_FLOAT_ID = 4
PROPERTY_TYPE_FLOAT_NAME = 'Float'

PROPERTY_TYPE_DOUBLE_ID = 5
PROPERTY_TYPE_DOUBLE_NAME = 'Double'

PROPERTY_TYPE_DATETIME_ID = 6
PROPERTY_TYPE_DATETIME_NAME = 'DateTime'

PROPERTY_TYPE_STRING_ID = 7
PROPERTY_TYPE_STRING_NAME = 'String'

PROPERTY_TYPE_EMBEDDED_LIST_ID = 10
PROPERTY_TYPE_EMBEDDED_LIST_NAME = 'EmbeddedList'

PROPERTY_TYPE_EMBEDDED_SET_ID = 11
PROPERTY_TYPE_EMBEDDED_SET_NAME = 'EmbeddedSet'

PROPERTY_TYPE_LINK_ID = 13
PROPERTY_TYPE_LINK_NAME = 'Link'

PROPERTY_TYPE_DATE_ID = 19
PROPERTY_TYPE_DATE_NAME = 'Date'

PROPERTY_TYPE_DECIMAL_ID = 21
PROPERTY_TYPE_DECIMAL_NAME = 'Decimal'

PROPERTY_TYPE_ANY_ID = 23
PROPERTY_TYPE_ANY_NAME = 'Any'

COLLECTION_PROPERTY_TYPES = {PROPERTY_TYPE_EMBEDDED_SET_ID, PROPERTY_TYPE_EMBEDDED_LIST_ID}

# Map of numeric type identifier to human-readable type name.
# Also the master list of all property types that the graph supports,
# since the graph doesn't actually support all of OrientDB's types.
PROPERTY_TYPE_ID_TO_NAME = {
    PROPERTY_TYPE_BOOLEAN_ID: PROPERTY_TYPE_BOOLEAN_NAME,
    PROPERTY_TYPE_INTEGER_ID: PROPERTY_TYPE_INTEGER_NAME,
    PROPERTY_TYPE_LONG_ID: PROPERTY_TYPE_LONG_NAME,
    PROPERTY_TYPE_FLOAT_ID: PROPERTY_TYPE_FLOAT_NAME,
    PROPERTY_TYPE_DOUBLE_ID: PROPERTY_TYPE_DOUBLE_NAME,
    PROPERTY_TYPE_DATETIME_ID: PROPERTY_TYPE_DATETIME_NAME,
    PROPERTY_TYPE_STRING_ID: PROPERTY_TYPE_STRING_NAME,
    PROPERTY_TYPE_EMBEDDED_LIST_ID: PROPERTY_TYPE_EMBEDDED_LIST_NAME,
    PROPERTY_TYPE_EMBEDDED_SET_ID: PROPERTY_TYPE_EMBEDDED_SET_NAME,
    PROPERTY_TYPE_LINK_ID: PROPERTY_TYPE_LINK_NAME,
    PROPERTY_TYPE_DATE_ID: PROPERTY_TYPE_DATE_NAME,
    PROPERTY_TYPE_DECIMAL_ID: PROPERTY_TYPE_DECIMAL_NAME,
    PROPERTY_TYPE_ANY_ID: PROPERTY_TYPE_ANY_NAME,
}

ORIENTDB_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
ORIENTDB_DATE_FORMAT = '%Y-%m-%d'


def validate_supported_property_type_id(property_name, property_type_id):
    """Ensure that the given property type_id is supported by the graph."""
    if property_type_id not in PROPERTY_TYPE_ID_TO_NAME:
        raise AssertionError(u'Property "{}" has unsupported property type id: '
                             u'{}'.format(property_name, property_type_id))


def _parse_bool_default_value(property_name, default_value_string):
    """Parse and return the default value for a boolean property."""
    lowercased_value_string = default_value_string.lower()
    if lowercased_value_string in {'0', 'false'}:
        return False
    elif lowercased_value_string in {'1', 'true'}:
        return True
    else:
        raise AssertionError(u'Unsupported default value for boolean property "{}": '
                             u'{}'.format(property_name, default_value_string))


def _parse_datetime_default_value(property_name, default_value_string):
    """Parse and return the default value for a datetime property."""
    # OrientDB doesn't use ISO-8601 datetime format, so we have to parse it manually
    # and then turn it into a python datetime object. strptime() will raise an exception
    # if the provided value cannot be parsed correctly.
    parsed_value = time.strptime(default_value_string, ORIENTDB_DATETIME_FORMAT)
    return datetime.datetime(
        parsed_value.tm_year, parsed_value.tm_mon, parsed_value.tm_mday,
        parsed_value.tm_hour, parsed_value.tm_min, parsed_value.tm_sec, 0, None)


def _parse_date_default_value(property_name, default_value_string):
    """Parse and return the default value for a date property."""
    # OrientDB doesn't use ISO-8601 datetime format, so we have to parse it manually
    # and then turn it into a python datetime object. strptime() will raise an exception
    # if the provided value cannot be parsed correctly.
    parsed_value = time.strptime(default_value_string, ORIENTDB_DATE_FORMAT)
    return datetime.date(parsed_value.tm_year, parsed_value.tm_mon, parsed_value.tm_mday)


def parse_default_property_value(property_name, property_type_id, default_value_string):
    """Parse the default value string into its proper form given the property type ID.

    Args:
        property_name: string, the name of the property whose default value is being parsed.
                       Used primarily to construct meaningful error messages, should the default
                       value prove invalid.
        property_type_id: int, one of the property type ID constants defined in this file that
                          OrientDB uses to designate the native type of a given property.
        default_value_string: string, the textual representation of the default value for
                              for the property, as returned by OrientDB's schema introspection code.

    Returns:
        an object of type matching the property that can be used as the property's default value.
        For example, if the property is of string type, the return type will be a string, and if
        the property is of list type, the return type will be a list.

    Raises:
        AssertionError, if the default value is not supported or does not match the
        property's declared type (e.g. if a default of "[]" is set on an integer property).
    """
    if property_type_id == PROPERTY_TYPE_EMBEDDED_SET_ID and default_value_string == '{}':
        return set()
    elif property_type_id == PROPERTY_TYPE_EMBEDDED_LIST_ID and default_value_string == '[]':
        return list()
    elif (property_type_id == PROPERTY_TYPE_STRING_ID and
          isinstance(default_value_string, six.string_types)):
        return default_value_string
    elif property_type_id == PROPERTY_TYPE_BOOLEAN_ID:
        return _parse_bool_default_value(property_name, default_value_string)
    elif property_type_id == PROPERTY_TYPE_DATETIME_ID:
        return _parse_datetime_default_value(property_name, default_value_string)
    elif property_type_id == PROPERTY_TYPE_DATE_ID:
        return _parse_date_default_value(property_name, default_value_string)
    else:
        raise AssertionError(u'Unsupported default value for property "{}" with type id {}: '
                             u'{}'.format(property_name, property_type_id, default_value_string))


# A way to describe a property's type and associated information:
#   - type_id: int, the OrientDB property type ID -- can be made human-readable
#              using the above PROPERTY_TYPE_ID_TO_NAME map.
#   - qualifier: dependent on the type_id
#        - For Link properties, string -- the name of the class to which the Link points.
#        - For EmbeddedSet and EmbeddedList, either:
#              - int, the property type ID of the native OrientDB type, if the data in
#                the collection is of a built-in OrientDB type, or
#              - string, the name of the non-graph class representing the data in the collection.
#        - For all other property types, None.
#   - default: the default value for the property, used when a record is inserted without an
#              explicit value for this property. Set to None if no default is given in the schema.
PropertyDescriptor = namedtuple('PropertyDescriptor',
                                ('type_id', 'qualifier', 'default'))
