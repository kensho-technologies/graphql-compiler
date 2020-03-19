# Copyright 2018-present Kensho Technologies, LLC.
from .utils import create_vertex_statement, get_random_date, get_uuid


FEEDING_EVENT_NAMES_LIST = (
    "Breakfast",
    "Brunch",
    "Lunch",
    "Dinner",
)


def _create_feeding_event_statement(event_name):
    """Return a SQL statement to create a FeedingEvent vertex."""
    field_name_to_value = {"name": event_name, "event_date": get_random_date(), "uuid": get_uuid()}
    return create_vertex_statement("FeedingEvent", field_name_to_value)


def get_event_generation_commands():
    """Return a list of SQL statements to create all event vertices."""
    command_list = []

    for event_name in FEEDING_EVENT_NAMES_LIST:
        command_list.append(_create_feeding_event_statement(event_name))

    return command_list
