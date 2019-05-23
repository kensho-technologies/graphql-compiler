# Copyright 2019-present Kensho Technologies, LLC.
from collections import OrderedDict

# Match query used to generate OrientDB records that are themselves used to generate GraphQL schema.
ORIENTDB_SCHEMA_RECORDS_QUERY = (
    'SELECT FROM (SELECT expand(classes) FROM metadata:schema) '
    'WHERE name NOT IN [\'ORole\', \'ORestricted\', \'OTriggered\', '
    '\'ORIDs\', \'OUser\', \'OIdentity\', \'OSchedule\', \'OFunction\']'
)


def toposort_classes(name_to_superclasses):
    """Return OrderedDict of class to superclasses where each class is before its subclasses."""
    def get_class_topolist(class_name, processed_classes, current_trace):
        """Return a topologically sorted list of this class's dependencies and class itself

        Args:
            class_name: string, name of the class to process
            name_to_class: dict, class_name -> descriptor
            current_trace: list of strings, list of classes traversed during the recursion

        Returns:
            list of dicts, list of class names sorted in topological order
        """
        # Check if this class has already been handled
        if class_name in processed_classes:
            return []

        if class_name in current_trace:
            raise AssertionError(
                'Encountered self-reference in dependency chain of {}'.format(class_name))

        class_list = []
        # Recursively process superclasses
        current_trace.add(class_name)
        for superclass_name in name_to_superclasses[class_name]:
            class_list.extend(get_class_topolist(superclass_name, processed_classes, current_trace))
        current_trace.remove(class_name)
        # Do the bookkeeping
        class_list.append(class_name)
        processed_classes.add(class_name)

        return class_list

    toposorted = []
    for name in name_to_superclasses.keys():
        toposorted.extend(get_class_topolist(name, set(), set()))
    return OrderedDict((class_name, name_to_superclasses[class_name])
                       for class_name in toposorted)
