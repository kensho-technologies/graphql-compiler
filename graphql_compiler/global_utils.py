# Copyright 2017-present Kensho Technologies, LLC.
from dataclasses import dataclass
from typing import Any, Dict, NamedTuple, Tuple, TypeVar

from graphql import DocumentNode, GraphQLList, GraphQLNamedType, GraphQLNonNull
import six


# A path starting with a vertex and continuing with edges from that vertex
VertexPath = Tuple[str, ...]


class PropertyPath(NamedTuple):
    """A VertexPath with a property on the final vertex of the path."""

    vertex_path: VertexPath
    field_name: str


@dataclass
class QueryStringWithParameters:
    """A query string and parameters that validate against the query."""

    query_string: str
    parameters: Dict[str, Any]


@dataclass
class ASTWithParameters:
    """A query AST and parameters that validate against the query."""

    query_ast: DocumentNode
    parameters: Dict[str, Any]


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


_KeyType = TypeVar("_KeyType")


def validate_that_dicts_have_the_same_keys(
    dict1: Dict[_KeyType, Any],
    dict2: Dict[_KeyType, Any]
) -> None:
    """Validate that the dictionaries have the same keys."""
    dict1_keys = set(dict1.keys())
    dict2_keys = set(dict2.keys())

    difference1 = dict1_keys.difference(dict2_keys)
    difference2 = dict2_keys.difference(dict1_keys)

    if difference1 or difference2:
        error_message_list = ["Expected dictionaries to have the same keys."]
        if difference1:
            error_message_list.append(f" Keys in the first dict but not the second: {difference1}.")
        if difference2:
            error_message_list.append(f" Keys in the second dict but not the first: {difference2}.")
        raise AssertionError("\n".join(error_message_list))
