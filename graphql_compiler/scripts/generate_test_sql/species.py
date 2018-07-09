from .utils import create_vertex_statement, get_random_limbs, get_uuid


SPECIES_LIST = (
    'Nazgul',
    'Pteranodon',
    'Dragon',
    'Hippogriff',
)


def _create_species_statement(species_name):
    """Return a SQL statement to create a species vertex."""
    field_name_to_value = {'name': species_name, 'limbs': get_random_limbs(), 'uuid': get_uuid()}
    return create_vertex_statement('Species', field_name_to_value)


def get_species_generation_commands():
    """Return a list of SQL statements to create all species vertices."""
    command_list = []
    for species_name in SPECIES_LIST:
        command_list.append(_create_species_statement(species_name))

    return command_list
