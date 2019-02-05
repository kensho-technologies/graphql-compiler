from graphql.language.ast import InlineFragment

from .schema import TYPENAME_META_FIELD_NAME


def get_ast_field_name(ast):
    """Return the normalized field name for the given AST node."""
    replacements = {
        # We always rewrite the following field names into their proper underlying counterparts.
        TYPENAME_META_FIELD_NAME: '@class'
    }
    base_field_name = ast.name.value
    normalized_name = replacements.get(base_field_name, base_field_name)
    return normalized_name


def get_ast_field_name_or_none(ast):
    """Return the field name for the AST node, or None if the AST is an InlineFragment."""
    if isinstance(ast, InlineFragment):
        return None
    return get_ast_field_name(ast)


def get_human_friendly_ast_field_name(ast):
    """Return a human-friendly name for the AST node, suitable for error messages."""
    if isinstance(ast, InlineFragment):
        return 'type coercion to {}'.format(ast.type_condition)
    return get_ast_field_name(ast)
