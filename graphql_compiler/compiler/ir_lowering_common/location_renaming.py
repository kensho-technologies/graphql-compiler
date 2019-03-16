# Copyright 2019-present Kensho Technologies, LLC.
"""Utilities for rewriting IR to replace one set of locations with another."""
import six

from ..expressions import (
    ContextField, ContextFieldExistence, FoldedContextField,
    Literal, OutputContextField
)
from ..helpers import FoldScopeLocation, Location


def flatten_location_translations(location_translations):
    """If location A translates to B, and B to C, then make A translate directly to C.

    Args:
        location_translations: dict of Location -> Location, where the key translates to the value.
                               Mutated in place for efficiency and simplicity of implementation.
    """
    sources_to_process = set(six.iterkeys(location_translations))

    def _update_translation(source):
        """Return the proper (fully-flattened) translation for the given location."""
        destination = location_translations[source]
        if destination not in location_translations:
            # "destination" cannot be translated, no further flattening required.
            return destination
        else:
            # "destination" can itself be translated -- do so,
            # and then flatten "source" to the final translation as well.
            sources_to_process.discard(destination)
            final_destination = _update_translation(destination)
            location_translations[source] = final_destination
            return final_destination

    while sources_to_process:
        _update_translation(sources_to_process.pop())


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
        new_args = [
            translate_potential_location(location_translations, arg)
            for arg in expression._print_args
        ]
        new_kwargs = {
            kwarg_name: translate_potential_location(location_translations, kwarg_value)
            for kwarg_name, kwarg_value in six.iteritems(expression._print_kwargs)
        }

        expression_cls = type(expression)
        return expression_cls(*new_args, **new_kwargs)

    return visitor_fn
