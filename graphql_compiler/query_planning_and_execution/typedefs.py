# Copyright 2021-present Kensho Technologies, LLC.
from abc import ABCMeta
import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from dataclasses_json import DataClassJsonMixin, config
from graphql import (
    GraphQLList,
    GraphQLNonNull,
    GraphQLType,
    ListTypeNode,
    NamedTypeNode,
    NonNullTypeNode,
    TypeNode,
    parse_type,
    specified_scalar_types,
)

from .. import GraphQLDate, GraphQLDateTime, GraphQLDecimal
from ..compiler.compiler_frontend import OutputMetadata, ProviderMetadata
from ..global_utils import is_same_type


QueryExecutionFunc = Callable[
    [str, Dict[str, GraphQLType], Dict[str, Any]], Iterable[Mapping[str, Any]]
]

# Custom scalar types.
CUSTOM_SCALAR_TYPES = {
    GraphQLDate.name: GraphQLDate,
    GraphQLDateTime.name: GraphQLDateTime,
    GraphQLDecimal.name: GraphQLDecimal,
}

# Custom scalar types must not have name conflicts with builtin scalar types.
if set(CUSTOM_SCALAR_TYPES).intersection(specified_scalar_types):
    raise AssertionError(
        f"Custom scalar types must have different names than builtin scalar types. Received "
        f"overlapping type(s) {set(CUSTOM_SCALAR_TYPES).intersection(specified_scalar_types)}. "
        f"Custom scalar types: {set(CUSTOM_SCALAR_TYPES)}. Builtin scalar types: "
        f"{set(specified_scalar_types)}."
    )

# Custom scalar types combined with builtin scalar types represent all allowable scalar types.
ALL_SCALAR_TYPES = copy.copy(CUSTOM_SCALAR_TYPES)
ALL_SCALAR_TYPES.update(specified_scalar_types)


def _type_from_scalar_type_dictionary(
    scalar_types: Dict[str, GraphQLType], type_node: TypeNode
) -> GraphQLType:
    """Get the GraphQL type definition from an AST node.

    Given a scalar type dictionary and an AST node describing a type, return a GraphQLType
    definition, which applies to that type. For example, if provided the parsed AST node for
    `[Date]`, a GraphQLList instance will be returned, containing the type called
    "Date" found in the scalar type dictionary. If a type called "Date" is not found in the scalar
    type dictionary, then None will be returned.

    Note: this is very similar to GraphQL's type_from_ast. However, instead of requiring a GraphQL
    schema this function requires a dictionary of the scalar types. This simplifies deserialization
    and allows for custom scalar types without constructing an entire schema.

    Args:
        scalar_types: dictionary mapping type name to GraphQLType
        type_node: AST node describing a type

    Returns:
        GraphQLType that applies to the type specified in type_node.

    Raises:
        AssertionError: if an invalid type node is given.
    """
    if isinstance(type_node, ListTypeNode):
        inner_type = _type_from_scalar_type_dictionary(scalar_types, type_node.type)
        if inner_type:
            return GraphQLList(inner_type)
        else:
            raise AssertionError(
                f"Invalid type node. ListTypeNode contained inner type {inner_type}."
            )
    elif isinstance(type_node, NonNullTypeNode):
        inner_type = _type_from_scalar_type_dictionary(scalar_types, type_node.type)
        if inner_type:
            return GraphQLNonNull(inner_type)
        else:
            raise AssertionError(
                f"Invalid type node. NonNullTypeNone contained inner type {inner_type}."
            )
    elif isinstance(type_node, NamedTypeNode):
        return scalar_types[type_node.name.value]

    # Not reachable. All possible type nodes have been considered.
    raise AssertionError(f"Unexpected type node: {type_node}.")


def _serialize_output_metadata_field(
    output_metadata_dictionary: Optional[Dict[str, "OutputMetadata"]]
) -> Optional[Dict[str, Dict[str, Any]]]:
    """Serialize OutputMetadata into a dictionary."""
    if not output_metadata_dictionary:
        return None
    dictionary_value = {}
    for output_name, output_metadata in output_metadata_dictionary.items():
        dictionary_value[output_name] = {
            "graphql_type": str(output_metadata["graphql_type"]),
            "optional": output_metadata["optional"],
            "folded": output_metadata["folded"],
            "provider_metadata": output_metadata["provider_metadata"],
        }
    return dictionary_value


def _deserialize_output_metadata_field(
    dict_value: Optional[Dict[str, Dict[str, Any]]]
) -> Optional[Dict[str, "OutputMetadata"]]:
    """Deserialize the dictionary representation of OutputMetadata."""
    if not dict_value:
        return None
    output_metadata_dictionary = {}
    for output_name, output_metadata in dict_value.items():
        output_metadata_dictionary[output_name] = OutputMetadata(
            type=_type_from_scalar_type_dictionary(
                ALL_SCALAR_TYPES, parse_type(output_metadata["graphql_type"])
            ),
            optional=output_metadata["optional"],
            folded=output_metadata["folded"],
            provider_metadata=ProviderMetadata(
                backend_type=output_metadata["provider_metadata"]["backend_type"],
                requires_fold_postprocessing=output_metadata["provider_metadata"][
                    "requires_fold_postprocessing"
                ],
            ),
        )
    return output_metadata_dictionary


def _serialize_input_metadata_field(
    input_metadata_dictionary: Optional[Dict[str, Any]]
) -> Optional[Dict[str, str]]:
    """Serialize input metadata, converting GraphQLTypes to strings."""
    # It is possible to have an empty input metadata dictionary (i.e. no inputs for the query).
    # Note that this is different than "None", which means no metadata was provided.
    if input_metadata_dictionary == {}:
        return {}
    if not input_metadata_dictionary:
        return None
    dictionary_value = {}
    for input_name, input_type in input_metadata_dictionary.items():
        dictionary_value[input_name] = str(input_type)
    return dictionary_value


def _deserialize_input_metadata_field(
    dict_value: Optional[Dict[str, str]]
) -> Optional[Dict[str, GraphQLType]]:
    """Deserialize input metadata, converting strings to GraphQLTypes."""
    # It is possible to have an empty input metadata dictionary (i.e. no inputs for the query).
    # Note that this is different than "None", which means no metadata was provided.
    if dict_value == {}:
        return {}
    if not dict_value:
        return None
    input_metadata_dictionary = {}
    for input_name, input_type in dict_value.items():
        input_metadata_dictionary[input_name] = _type_from_scalar_type_dictionary(
            ALL_SCALAR_TYPES, parse_type(input_type)
        )
    return input_metadata_dictionary


def _compare_input_metadata_field(
    left_input_metadata: Optional[Dict[str, GraphQLType]],
    right_input_metadata: Optional[Dict[str, GraphQLType]],
) -> bool:
    """Check input_metadata SimpleExecute field equality, comparing GraphQLTypes appropriately."""
    if left_input_metadata is None:
        # Since left_input_metadata is None, checking for equality requires determining whether or
        # not right_metadata is also None. If right_metadata is None, left and right metadata
        # are equal and True is returned.
        return right_input_metadata is None

    # right_input_metadata is None, but left_input_metadata is not.
    if right_input_metadata is None:
        return False

    # Neither left_input_metadata nor right_input_metadata is None.
    input_metadata_keys = left_input_metadata.keys()

    # Check if input_metadata keys match.
    if input_metadata_keys != right_input_metadata.keys():
        return False
    # Check if input_metadata values match for all keys.
    for key in input_metadata_keys:
        if not is_same_type(left_input_metadata[key], right_input_metadata[key]):
            return False

    # All keys and values match so return True.
    return True


# ############
# Public API #
# ############


@dataclass(init=True, repr=True, eq=True, frozen=True)
class QueryPlanNode(DataClassJsonMixin, metaclass=ABCMeta):
    """Abstract query plan node. May or may not contain other nodes, depending on its type."""

    # Unique ID of the plan node.
    # Note: do not compare "uuid" values to determine whether query plan nodes are equal, since two
    # plans with different identifiers might still be semantically equivalent and therefore equal.
    uuid: str = field(compare=False)


@dataclass(init=True, repr=True, eq=False, frozen=True)
class SimpleExecute(QueryPlanNode):
    """Just give the specified query and args to the provider, it'll execute it for you as-is."""

    provider_id: str
    query: str  # in whatever query language the provider will accept (not necessarily GraphQL)
    arguments: Dict[str, Any]

    # Input and output metadata of the query.
    output_metadata: Dict[str, OutputMetadata] = field(
        metadata=config(
            encoder=_serialize_output_metadata_field, decoder=_deserialize_output_metadata_field
        )
    )
    input_metadata: Dict[str, GraphQLType] = field(
        metadata=config(
            encoder=_serialize_input_metadata_field, decoder=_deserialize_input_metadata_field
        )
    )

    def __eq__(self, other: Any) -> bool:
        """Check equality between an object and this SimpleExecute."""
        if not isinstance(other, SimpleExecute):
            return False

        # Perform special check for input_metadata since GraphQLTypes don't have equality, and
        # check all other fields in a straight forward manner.
        return (
            self.provider_id == other.provider_id
            and self.query == other.query
            and self.arguments == other.arguments
            and self.output_metadata == other.output_metadata
            and _compare_input_metadata_field(self.input_metadata, other.input_metadata)
        )
