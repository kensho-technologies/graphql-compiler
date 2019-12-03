# Copyright 2019-present Kensho Technologies, LLC.


def generate_disambiguations(existing_names, new_names):
    """Return a dict mapping the new names to similar names not conflicting with existing names.

    We always try to keep names the same if possible, and only generate name changes if the desired
    name is already taken.

    Args:
        existing_names: set of strings, the names that are already taken
        new_names: set of strings, the names that might coincide with exisitng names

    Returns:
        dict mapping the new names to other unique names not present in existing_names
    """
    name_mapping = dict()
    for name in new_names:
        # We try adding different suffixes to disambiguate from the existing names.
        disambiguation = name
        index = 0
        while disambiguation in existing_names or disambiguation in name_mapping:
            disambiguation = "{}_macro_edge_{}".format(name, index)
            index += 1
        name_mapping[name] = disambiguation
    return name_mapping
