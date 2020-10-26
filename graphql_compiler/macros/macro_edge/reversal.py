# Copyright 2019-present Kensho Technologies, LLC.
from ...schema import INBOUND_EDGE_FIELD_PREFIX, OUTBOUND_EDGE_FIELD_PREFIX


# ############
# Public API #
# ############


def make_reverse_macro_edge_name(macro_edge_name):
    """Autogenerate a reverse macro edge name for the given macro edge name."""
    if macro_edge_name.startswith(INBOUND_EDGE_FIELD_PREFIX):
        raw_edge_name = macro_edge_name[len(INBOUND_EDGE_FIELD_PREFIX) :]
        prefix = OUTBOUND_EDGE_FIELD_PREFIX
    elif macro_edge_name.startswith(OUTBOUND_EDGE_FIELD_PREFIX):
        raw_edge_name = macro_edge_name[len(OUTBOUND_EDGE_FIELD_PREFIX) :]
        prefix = INBOUND_EDGE_FIELD_PREFIX
    else:
        raise AssertionError("Unreachable condition reached: {}".format(macro_edge_name))

    reversed_macro_edge_name = prefix + raw_edge_name

    return reversed_macro_edge_name
