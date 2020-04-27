# Copyright 2017-present Kensho Technologies, LLC.
from dataclasses import dataclass
from typing import Any, Dict, NamedTuple, Set, Tuple

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
                'Overlapping key "{}" found in dicts that are supposed '
                "to not overlap. Values: {} {}".format(key, merge_target[key], value)
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


def assert_set_equality(set1: Set[Any], set2: Set[Any]) -> None:
    """Assert that the sets are the same."""
    diff1 = set1.difference(set2)
    diff2 = set2.difference(set1)

    if diff1 or diff2:
        error_message_list = ["Expected sets to have the same keys."]
        if diff1:
            error_message_list.append(f"Keys in the first set but not the second: {diff1}.")
        if diff2:
            error_message_list.append(f"Keys in the second set but not the first: {diff2}.")
        raise AssertionError(" ".join(error_message_list))
