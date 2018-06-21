import random

from .utils import create_vertex_statement, get_uuid


random.seed(0)

SPECIES_LIST = (
    'Nazgul',
    'Pteranodon',
    'Dragon',
    'Hippogriff',
)


def _create_species_statement(species_name):
    """Return a SQL statement to create a species vertex."""
    fields_dict = {'name': species_name, 'uuid': get_uuid()}
    return create_vertex_statement('Species', fields_dict)


def get_species_generators():
    """Return a list of SQL statements to create all species vertices."""
    generator_list = []
    for species_name in SPECIES_LIST:
        generator_list.append(_create_species_statement(species_name))

    return generator_list
