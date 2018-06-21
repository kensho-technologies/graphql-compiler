from .utils import create_vertex_statement, get_uuid


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


def get_species_generation_commands():
    """Return a list of SQL statements to create all species vertices."""
    command_list = []
    for species_name in SPECIES_LIST:
        command_list.append(_create_species_statement(species_name))

    return command_list
