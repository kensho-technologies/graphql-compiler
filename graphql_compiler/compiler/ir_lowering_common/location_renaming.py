# Copyright 2019-present Kensho Technologies, LLC.
"""Utilities for rewriting IR to replace one set of locations with another."""
import six

from ..helpers import FoldScopeLocation, Location


def make_revisit_location_translations(query_metadata_table):
    """Return a dict mapping location revisits to the location being revisited, for rewriting."""
    location_translations = dict()

    for location, _ in query_metadata_table.registered_locations:
        location_being_revisited = query_metadata_table.get_revisit_origin(location)
        if location_being_revisited != location:
            location_translations[location] = location_being_revisited

    return location_translations


def translate_potential_location(location_translations, potential_location):
    """If the input is a BaseLocation object, translate it, otherwise return it as-is."""
    if isinstance(potential_location, Location):
        old_location_at_vertex = potential_location.at_vertex()
        field = potential_location.field

        new_location = location_translations.get(old_location_at_vertex, None)
        if new_location is None:
            # No translation needed.
            return potential_location
        else:
            # If necessary, add the field component to the new location before returning it.
            if field is None:
                return new_location
            else:
                return new_location.navigate_to_field(field)
    elif isinstance(potential_location, FoldScopeLocation):
        old_base_location = potential_location.base_location
        new_base_location = location_translations.get(old_base_location, old_base_location)
        fold_path = potential_location.fold_path
        fold_field = potential_location.field
        return FoldScopeLocation(new_base_location, fold_path, field=fold_field)
    else:
        return potential_location


def make_location_rewriter_visitor_fn(location_translations):
    """Return a visitor function that is able to replace locations with equivalent locations."""
    def visitor_fn(expression):
        """Expression visitor function used to rewrite expressions with updated Location data."""
        # All CompilerEntity objects store their exact constructor input args/kwargs.
        # To minimize the chances that we forget to update a location somewhere in an expression,
        # we rewrite all locations that we find as arguments to expression constructors.
        # pylint: disable=protected-access
        new_args = [
            translate_potential_location(location_translations, arg)
            for arg in expression._print_args
        ]
        new_kwargs = {
            kwarg_name: translate_potential_location(location_translations, kwarg_value)
            for kwarg_name, kwarg_value in six.iteritems(expression._print_kwargs)
        }
        # pylint: enable=protected-access

        expression_cls = type(expression)
        return expression_cls(*new_args, **new_kwargs)

    return visitor_fn
