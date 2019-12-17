# Copyright 2018-present Kensho Technologies, LLC.
import random

from .events import FEEDING_EVENT_NAMES_LIST
from .species import FOOD_LIST, SPECIES_LIST
from .utils import (
    create_edge_statement,
    create_name,
    create_vertex_statement,
    extract_base_name_and_label,
    get_random_date,
    get_random_net_worth,
    get_uuid,
)


NUM_INITIAL_ANIMALS = 20
NUM_GENERATIONS = 30
NUM_PARENTS = 4
ANIMAL_COLOR_LIST = (
    "red",
    "blue",
    "green",
    "yellow",
    "magenta",
    "black",
    "orange",
    "indigo",
)
NUM_ENTITY_RELATED_COMMANDS_MULTIPLIER = 0.2
NUM_ALIASES = 3
ANIMAL_FED_AT_EXISTENCE_THRESHOLD = 0.5


def _create_animal_fed_at_random_event_statement(from_name):
    """Return a SQL statement to create an Animal_FedAt edge connected to a random Event."""
    event_name = random.choice(FEEDING_EVENT_NAMES_LIST)  # nosec
    return create_edge_statement("Animal_FedAt", "Animal", from_name, "FeedingEvent", event_name)


def _get_animal_aliases(animal_name, parent_names):
    """Return list of animal aliases."""
    base_name, _ = extract_base_name_and_label(animal_name)
    random_aliases = [  # nosec
        base_name + "_" + str(random.randint(0, 9)) for _ in range(NUM_ALIASES)
    ]

    # Some tests check for equality between names and aliases of different animals.
    # If the animal has several parents, we add a parent name to the alias list.
    if len(parent_names) > 2:
        return random_aliases + random.sample(parent_names, 2)  # nosec
    else:
        return random_aliases


def _create_animal_statement(animal_name, parent_names):
    """Return a SQL statement to create an Animal vertex."""
    field_name_to_value = {
        "name": animal_name,
        "uuid": get_uuid(),
        "color": random.choice(ANIMAL_COLOR_LIST),  # nosec
        "birthday": get_random_date(),
        "net_worth": get_random_net_worth(),
        "alias": _get_animal_aliases(animal_name, parent_names),
    }
    return create_vertex_statement("Animal", field_name_to_value)


def _create_animal_parent_of_statement(from_name, to_name):
    """Return a SQL statement to create an Animal_ParentOf edge."""
    return create_edge_statement("Animal_ParentOf", "Animal", from_name, "Animal", to_name)


def _detect_subtype(entity_name):
    """Detect and return the type of Entity from its name."""
    if entity_name in SPECIES_LIST:
        return "Species"
    elif entity_name in FOOD_LIST:
        return "Food"
    elif extract_base_name_and_label(entity_name)[0] in SPECIES_LIST:
        return "Animal"
    else:
        raise AssertionError(
            u"Found invalid entity name. Must be either a species, food, "
            u"or animal name: {}".format(entity_name)
        )


def _create_entity_related_statement(from_name, to_name):
    """Return a SQL statement to create an Entity_Related edge."""
    from_class = _detect_subtype(from_name)
    to_class = _detect_subtype(to_name)
    return create_edge_statement("Entity_Related", from_class, from_name, to_class, to_name)


def _create_animal_of_species_statement(from_name, to_name):
    """Return a SQL statement to create an Animal_OfSpecies edge."""
    return create_edge_statement("Animal_OfSpecies", "Animal", from_name, "Species", to_name)


def _get_initial_animal_generators(species_name, current_animal_names):
    """Return a list of SQL statements to create initial animals for a given species."""
    command_list = []
    for index in range(NUM_INITIAL_ANIMALS):
        animal_name = create_name(species_name, str(index))
        current_animal_names.append(animal_name)
        command_list.append(_create_animal_statement(animal_name, []))
    return command_list


def _get_new_parents(current_animal_names, previous_parent_sets, num_parents):
    """Return a set of `num_parents` parent names that is not present in `previous_parent_sets`."""
    while True:
        new_parent_names = frozenset(random.sample(current_animal_names, num_parents))  # nosec
        # Duplicating a set of parents could result in Animals with the same names.
        # This would invalidate unique selection of Animals by name.
        if new_parent_names not in previous_parent_sets:
            return new_parent_names


def _get_animal_entity_related_commands(all_animal_names):
    """Return a list of commands to create EntityRelated edges between random Animals and Foods."""
    command_list = []
    num_samples = int(NUM_ENTITY_RELATED_COMMANDS_MULTIPLIER * len(all_animal_names))
    in_neighbor_samples = random.sample(all_animal_names, num_samples)  # nosec
    out_neighbor_samples = random.sample(all_animal_names, num_samples)  # nosec

    for from_name, to_name in zip(in_neighbor_samples, out_neighbor_samples):
        # Related Animal Entities
        command_list.append(_create_entity_related_statement(from_name, to_name))

        # Related_Entity between Animals and Food
        food_name = random.choice(FOOD_LIST)  # nosec
        command_list.append(_create_entity_related_statement(from_name, food_name))
        command_list.append(_create_entity_related_statement(food_name, to_name))

    return command_list


def get_animal_generation_commands():
    """Return a list of SQL statements to create animal vertices and their corresponding edges."""
    command_list = []
    species_to_names = {}
    previous_parent_sets = set()
    all_animal_names = []

    for species_name in SPECIES_LIST:
        current_animal_names = []
        species_to_names[species_name] = current_animal_names
        command_list.extend(_get_initial_animal_generators(species_name, current_animal_names))

        for _ in range(NUM_GENERATIONS):
            new_parent_names = _get_new_parents(
                current_animal_names, previous_parent_sets, NUM_PARENTS
            )
            previous_parent_sets.add(new_parent_names)

            parent_indices = sorted(
                [
                    index
                    for _, index in [
                        extract_base_name_and_label(parent_name) for parent_name in new_parent_names
                    ]
                ]
            )
            new_label = "(" + "_".join(parent_indices) + ")"
            new_animal_name = create_name(species_name, new_label)
            current_animal_names.append(new_animal_name)
            command_list.append(_create_animal_statement(new_animal_name, sorted(new_parent_names)))
            for parent_name in sorted(new_parent_names):
                new_edge = _create_animal_parent_of_statement(new_animal_name, parent_name)
                command_list.append(new_edge)

        for animal_name in current_animal_names:
            command_list.append(_create_animal_of_species_statement(animal_name, species_name))
            if random.random() > ANIMAL_FED_AT_EXISTENCE_THRESHOLD:  # nosec
                command_list.append(_create_animal_fed_at_random_event_statement(animal_name))

            # Entity_Related edges connecting each animal to their parents, children, and themselves
            command_list.append(_create_entity_related_statement(animal_name, animal_name))
            command_list.append(_create_entity_related_statement(animal_name, species_name))
            command_list.append(_create_entity_related_statement(species_name, animal_name))

        all_animal_names.extend(current_animal_names)

    return command_list + _get_animal_entity_related_commands(all_animal_names)
