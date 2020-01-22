from graphql import lexicographic_sort_schema, print_schema, GraphQLSchema
from hashlib import sha256


def compute_schema_fingerprint(schema: GraphQLSchema) -> str:
    """Compute a fingerprint compactly representing all the data in the given schema.

    The fingerprint is not sensitive to things like type or field order. This function is guaranteed
    to be robust enough that if two GraphQLSchema have the same fingerprint, then they also
    represent the same schema.

    Args:
        schema: the schema to use.

    Returns:
        a fingerprint compactly representing the data in the schema.
    """
    lexicographically_sorted_schema = lexicographic_sort_schema(schema)
    text = print_schema(lexicographically_sorted_schema)
    return sha256(text.encode("utf-8")).hexdigest()
