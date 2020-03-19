# Copyright 2018-present Kensho Technologies, LLC.
import random

from .utils import create_edge_statement, create_vertex_statement, get_random_limbs, get_uuid


SPECIES_LIST = (
    "Nazgul",
    "Pteranodon",
    "Dragon",
    "Hippogriff",
)
FOOD_LIST = (
    "Bacon",
    "Lembas",
    "Blood pie",
)
NUM_FOODS = 2


def _create_food_statement(food_name):
    """Return a SQL statement to create a Food vertex."""
    field_name_to_value = {"name": food_name, "uuid": get_uuid()}
    return create_vertex_statement("Food", field_name_to_value)


def _create_species_statement(species_name):
    """Return a SQL statement to create a Species vertex."""
    field_name_to_value = {"name": species_name, "limbs": get_random_limbs(), "uuid": get_uuid()}
    return create_vertex_statement("Species", field_name_to_value)


def _create_species_eats_statement(from_name, to_name):
    """Return a SQL statement to create a Species_Eats edge."""
    if to_name in SPECIES_LIST:
        to_class = "Species"
    elif to_name in FOOD_LIST:
        to_class = "Food"
    else:
        raise AssertionError(u"Invalid name for Species_Eats endpoint: {}".format(to_name))
    return create_edge_statement("Species_Eats", "Species", from_name, to_class, to_name)


def get_species_generation_commands():
    """Return a list of SQL statements to create all species vertices."""
    command_list = []

    for food_name in FOOD_LIST:
        command_list.append(_create_food_statement(food_name))
    for species_name in SPECIES_LIST:
        command_list.append(_create_species_statement(species_name))

    for species_name in SPECIES_LIST:
        for food_or_species_name in random.sample(SPECIES_LIST + FOOD_LIST, NUM_FOODS):  # nosec
            command_list.append(_create_species_eats_statement(species_name, food_or_species_name))

    return command_list
