# Copyright 2017-present Kensho Technologies, LLC.
from .utils import create_edge_statement, create_vertex_statement, get_random_date, get_uuid


EVENT_NAMES_LIST = (
    "Birthday",
    "Bar Mitzvah",
    "Coronation",
    "Re-awakening",
)


def _create_event_statement(event_name):
    """Return a SQL statement to create a Event vertex."""
    field_name_to_value = {'name': event_name, 'event_date': get_random_date(), 'uuid': get_uuid()}
    return create_vertex_statement('Event', field_name_to_value)


def get_event_generation_commands():
    """Return a list of SQL statements to create all event vertices."""
    command_list = []

    for event_name in EVENT_NAMES_LIST:
        command_list.append(_create_event_statement(event_name))

    return command_list
