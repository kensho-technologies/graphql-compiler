import random

from .species import SPECIES_LIST
from .utils import (create_edge_statement, create_name, create_vertex_statement, get_uuid,
                    strip_index_from_name)


NUM_INITIAL_ANIMALS = 5
NUM_GENERATIONS = 10
NUM_PARENTS = 3


def _create_animal_statement(animal_name):
    """Return a SQL statement to create an animal vertex."""
    fields_dict = {'name': animal_name, 'uuid': get_uuid()}
    return create_vertex_statement('Animal', fields_dict)


def _create_animal_parent_of_statement(from_name, to_name):
    """Return a SQL statement to create an Animal_ParentOf edge."""
    return create_edge_statement('Animal_ParentOf', 'Animal', from_name, 'Animal', to_name)


def _create_animal_of_species_statement(from_name, to_name):
    """Return a SQL statement to create an Animal_OfSpecies edge."""
    return create_edge_statement('Animal_OfSpecies', 'Animal', from_name, 'Species', to_name)


def _get_initial_animal_generators(species_name, current_animal_names):
    """Return a list of SQL statements to create initial animals for a given species."""
    generator_list = []
    for index in range(NUM_INITIAL_ANIMALS):
        animal_name = create_name(species_name, str(index))
        current_animal_names.append(animal_name)
        generator_list.append(_create_animal_statement(animal_name))
    return generator_list


def get_animal_generators():
    """Return a list of SQL statements to create animal vertices and their corresponding edges."""
    generator_list = []
    species_to_names = {}
    previous_parent_sets = set()

    for species_name in SPECIES_LIST:
        current_animal_names = []
        species_to_names[species_name] = current_animal_names
        generator_list.extend(_get_initial_animal_generators(species_name, current_animal_names))

        for _ in range(NUM_GENERATIONS):
            while True:
                parent_names = frozenset(random.sample(current_animal_names, NUM_PARENTS))
                # Duplicating a set of parents could result in Animals with the same names.
                # This would invalidate unique selection of Animals by name.
                if parent_names not in previous_parent_sets:
                    break
            previous_parent_sets.add(parent_names)

            parent_indices = [
                index for _, index in [
                    strip_index_from_name(parent_name) for parent_name in parent_names
                ]
            ]
            new_label = '(' + ''.join(parent_indices) + ')'
            new_animal_name = create_name(species_name, new_label)
            current_animal_names.append(new_animal_name)
            generator_list.append(_create_animal_statement(new_animal_name))
            for parent_name in parent_names:
                new_edge = _create_animal_parent_of_statement(new_animal_name, parent_name)
                generator_list.append(new_edge)

        for animal_name in current_animal_names:
            generator_list.append(_create_animal_of_species_statement(animal_name, species_name))

    return generator_list
