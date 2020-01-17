from graphql import lexicographic_sort_schema, print_schema, GraphQLSchema, get_introspection_query
from hashlib import sha256


def compute_schema_fingerprint(schema: GraphQLSchema) -> str:
    """Compute a fingerprint compactly representing all the data in the given schema.

    The fingerprint is not sensitive to things like type or field order. This function is guaranteed
    to be robust enough that if two GraphQLSchema have the same fingerprint, then they also
    represent the same schema.

    Args:
        schema: the schema to use

    Returns:

    """
    schema.to_kwargs()

    sha256(text.encode("utf-8")).hexdigest()
