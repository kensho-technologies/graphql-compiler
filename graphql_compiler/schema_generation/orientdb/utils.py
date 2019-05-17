# Copyright 2019-present Kensho Technologies, LLC.

# Match query used to generate OrientDB records that are themselves used to generate GraphQL schema.
ORIENTDB_SCHEMA_RECORDS_QUERY = (
    'SELECT FROM (SELECT expand(classes) FROM metadata:schema) '
    'WHERE name NOT IN [\'ORole\', \'ORestricted\', \'OTriggered\', '
    '\'ORIDs\', \'OUser\', \'OIdentity\', \'OSchedule\', \'OFunction\']'
)


def toposort_classes(classes):
    """Sort class metadatas so that a superclass is always before the subclass"""
    def get_class_topolist(class_name, name_to_class, processed_classes, current_trace):
        """Return a topologically sorted list of this class's dependencies and class itself

        Args:
            class_name: string, name of the class to process
            name_to_class: dict, class_name -> descriptor
            processed_classes: set of strings, a set of classes that have already been processed
            current_trace: list of strings, list of classes traversed during the recursion

        Returns:
            list of dicts, list of classes sorted in topological order
        """
        # Check if this class has already been handled
        if class_name in processed_classes:
            return []

        if class_name in current_trace:
            raise AssertionError(
                'Encountered self-reference in dependency chain of {}'.format(class_name))

        cls = name_to_class[class_name]
        # Collect the dependency classes
        # These are bases and classes from linked properties
        dependencies = _list_superclasses(cls)
        # Recursively process linked edges
        properties = cls['properties'] if 'properties' in cls else []
        for prop in properties:
            if 'linkedClass' in prop:
                dependencies.append(prop['linkedClass'])

        class_list = []
        # Recursively process superclasses
        current_trace.add(class_name)
        for dependency in dependencies:
            class_list.extend(get_class_topolist(
                dependency, name_to_class, processed_classes, current_trace))
        current_trace.remove(class_name)
        # Do the bookkeeping
        class_list.append(name_to_class[class_name])
        processed_classes.add(class_name)

        return class_list

    # Map names to classes
    class_map = {c['name']: c for c in classes}
    seen_classes = set()

    toposorted = []
    for name in class_map.keys():
        toposorted.extend(get_class_topolist(name, class_map, seen_classes, set()))
    return toposorted


def _list_superclasses(class_def):
    """Return a list of the superclasses of the given class"""
    superclasses = class_def.get('superClasses', [])
    if superclasses:
        # Make sure to duplicate the list
        return list(superclasses)

    sup = class_def.get('superClass', None)
    if sup:
        return [sup]
    else:
        return []
