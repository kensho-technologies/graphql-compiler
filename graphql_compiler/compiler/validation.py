# Copyright 2019-present Kensho Technologies, LLC.
from graphql.validation import validate
import six

from ..schema import DIRECTIVES


def validate_schema_and_query_ast(schema, query_ast):
    """Validate the supplied GraphQL schema and query_ast.

    This method wraps around graphql-core's validation to enforce a stricter requirement of the
    schema -- all directives supported by the compiler must be declared by the schema, regardless of
    whether each directive is used in the query or not.

    Args:
        schema: GraphQL schema object, created using the GraphQL library
        query_ast: abstract syntax tree representation of a GraphQL query

    Returns:
        list containing schema and/or query validation errors
    """
    core_graphql_errors = validate(schema, query_ast)

    # The following directives appear in the core-graphql library, but are not supported by the
    # GraphQL compiler.
    unsupported_default_directives = frozenset([
        frozenset([
            'include',
            frozenset(['FIELD', 'FRAGMENT_SPREAD', 'INLINE_FRAGMENT']),
            frozenset(['if'])
        ]),
        frozenset([
            'skip',
            frozenset(['FIELD', 'FRAGMENT_SPREAD', 'INLINE_FRAGMENT']),
            frozenset(['if'])
        ])
    ])

    # This directive is supported and ignored by the compiler, since it is meant as an indication
    # to the user that a field should not be used.
    supported_default_directive = frozenset([
        frozenset([
            'deprecated',
            frozenset(['FIELD_DEFINITION', 'ENUM_VALUE']),
            frozenset(['reason'])
        ])
    ])

    # Directives expected by the graphql compiler.
    expected_directives = {
        frozenset([
            directive.name,
            frozenset(directive.locations),
            frozenset(six.viewkeys(directive.args))
        ])
        for directive in DIRECTIVES
    }

    # Directives provided in the parsed graphql schema.
    actual_directives = {
        frozenset([
            directive.name,
            frozenset(directive.locations),
            frozenset(six.viewkeys(directive.args))
        ])
        for directive in schema.get_directives()
    }

    # Directives missing from the actual directives provided.
    missing_directives = expected_directives - actual_directives
    if missing_directives:
        missing_message = (u'The following directives were missing from the '
                           u'provided schema: {}'.format(missing_directives))
        core_graphql_errors.append(missing_message)

    # Directives that are not specified by the core graphql library. Note that Graphql-core
    # automatically injects default directives into the schema, regardless of whether
    # the schema supports said directives. Hence, while the directives contained in
    # unsupported_default_directives are incompatible with the graphql-compiler, we allow them to
    # be present in the parsed schema string.
    extra_directives = (
        actual_directives -
        expected_directives -
        unsupported_default_directives -
        supported_default_directive
    )
    if extra_directives:
        extra_message = (u'The following directives were supplied in the given schema, but are not '
                         u'not supported by the GraphQL compiler: {}'.format(extra_directives))
        core_graphql_errors.append(extra_message)

    return core_graphql_errors
