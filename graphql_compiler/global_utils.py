# Copyright 2017-present Kensho Technologies, LLC.
from dataclasses import dataclass
import datetime
from typing import Any, Dict

import pytz

from graphql import DocumentNode, GraphQLList, GraphQLNamedType, GraphQLNonNull
import six


@dataclass
class QueryStringWithParameters:
    """A query string and parameters that validate against the query."""

    query_string: str

    # parameters are expected to be canonicalized:
    # - all datetime objects should have a time zone
    parameters: Dict[str, Any]


@dataclass
class ASTWithParameters:
    """A query AST and parameters that validate against the query."""

    query_ast: DocumentNode

    # parameters are expected to be canonicalized:
    # - all datetime objects should have a time zone
    parameters: Dict[str, Any]


def canonicalize_datetime(value):
    if value.tzinfo is None:
        # TODO astimezone, or replace?
        return value.astimezone(pytz.utc)
    return value


def canonicalize_value(value):
    if isinstance(value, datetime.datetime):
        return canonicalize_datetime(value)
    return value


def merge_non_overlapping_dicts(merge_target, new_data):
    """Produce the merged result of two dicts that are supposed to not overlap."""
    result = dict(merge_target)

    for key, value in six.iteritems(new_data):
        if key in merge_target:
            raise AssertionError(
                u'Overlapping key "{}" found in dicts that are supposed '
                u"to not overlap. Values: {} {}".format(key, merge_target[key], value)
            )

        result[key] = value

    return result


def is_same_type(left, right):
    """Determine if two GraphQL types are the same type."""
    if isinstance(left, GraphQLNamedType) and isinstance(right, GraphQLNamedType):
        return left.__class__ is right.__class__ and left.name == right.name
    elif isinstance(left, GraphQLList) and isinstance(right, GraphQLList):
        return is_same_type(left.of_type, right.of_type)
    elif isinstance(left, GraphQLNonNull) and isinstance(right, GraphQLNonNull):
        return is_same_type(left.of_type, right.of_type)
    else:
        return False
