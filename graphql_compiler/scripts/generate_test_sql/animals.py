# Copyright 2017-present Kensho Technologies, LLC.
import random

from .species import SPECIES_LIST
from .utils import (create_edge_statement, create_name, create_vertex_statement, get_random_date,
                    get_random_net_worth, get_uuid, strip_index_from_name)


NUM_INITIAL_ANIMALS = 5
NUM_GENERATIONS = 10
NUM_PARENTS = 3
ANIMAL_COLOR_LIST = (
    'red',
    'blue',
    'green',
    'yellow',
    'magenta',
    'black',
    'orange',
    'indigo',
)


def _create_animal_statement(animal_name):
    """Return a SQL statement to create an animal vertex."""
    field_name_to_value = {
        'name': animal_name,
        'uuid': get_uuid(),
        'color': random.choice(ANIMAL_COLOR_LIST),  # nosec
        'birthday': get_random_date(),
        'net_worth': get_random_net_worth(),
    }
    return create_vertex_statement('Animal', field_name_to_value)


def _create_animal_parent_of_statement(from_name, to_name):
    """Return a SQL statement to create an Animal_ParentOf edge."""
    return create_edge_statement('Animal_ParentOf', 'Animal', from_name, 'Animal', to_name)


def _create_animal_of_species_statement(from_name, to_name):
    """Return a SQL statement to create an Animal_OfSpecies edge."""
    return create_edge_statement('Animal_OfSpecies', 'Animal', from_name, 'Species', to_name)


def _get_initial_animal_generators(species_name, current_animal_names):
    """Return a list of SQL statements to create initial animals for a given species."""
    command_list = []
    for index in range(NUM_INITIAL_ANIMALS):
        animal_name = create_name(species_name, str(index))
        current_animal_names.append(animal_name)
        command_list.append(_create_animal_statement(animal_name))
    return command_list


def _get_new_parents(current_animal_names, previous_parent_sets, num_parents):
    """Return a set of `num_parents` parent names that is not present in `previous_parent_sets`."""
    while True:
        new_parent_names = frozenset(random.sample(current_animal_names, num_parents))
        # Duplicating a set of parents could result in Animals with the same names.
        # This would invalidate unique selection of Animals by name.
        if new_parent_names not in previous_parent_sets:
            return new_parent_names


def get_animal_generation_commands():
    """Return a list of SQL statements to create animal vertices and their corresponding edges."""
    command_list = []
    species_to_names = {}
    previous_parent_sets = set()

    for species_name in SPECIES_LIST:
        current_animal_names = []
        species_to_names[species_name] = current_animal_names
        command_list.extend(_get_initial_animal_generators(species_name, current_animal_names))

        for _ in range(NUM_GENERATIONS):
            new_parent_names = _get_new_parents(
                current_animal_names, previous_parent_sets, NUM_PARENTS)
            previous_parent_sets.add(new_parent_names)

            parent_indices = sorted([
                index
                for _, index in [
                    strip_index_from_name(parent_name)
                    for parent_name in new_parent_names
                ]
            ])
            new_label = '(' + ''.join(parent_indices) + ')'
            new_animal_name = create_name(species_name, new_label)
            current_animal_names.append(new_animal_name)
            command_list.append(_create_animal_statement(new_animal_name))
            for parent_name in sorted(new_parent_names):
                new_edge = _create_animal_parent_of_statement(new_animal_name, parent_name)
                command_list.append(new_edge)

        for animal_name in current_animal_names:
            command_list.append(_create_animal_of_species_statement(animal_name, species_name))

    return command_list
