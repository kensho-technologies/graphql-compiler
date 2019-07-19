# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql import build_ast_schema
from graphql.language import ast as ast_types
from graphql.language.printer import print_ast
import six

from .utils import (
    SchemaNameConflictError, check_ast_schema_is_valid, check_schema_identifier_is_valid,
    get_query_type_name
)


MergedSchemaDescriptor = namedtuple(
    'MergedSchemaDescriptor', (
        'schema_ast',  # Document, AST representing the merged schema
        'name_to_schema_id',  # Dict[str, str], type name to id of the schema the type is from
    )
)


def merge_schemas(schema_id_to_ast):
    """Check that input schemas do not contain conflicting definitions, then merge.

    The merged schema will contain all type, interface, union, enum, scalar, and directive
    definitions from input schemas. The fields of its query type will be the union of the
    fields of the query types of each input schema.

    Note that the output AST will share mutable objects with input ASTs.

    Args:
        schema_id_to_ast: OrderedDict[str, Document], where keys are names/identifiers of schemas,
                          and values are ASTs describing schemas. The ASTs will not be modified
                          by this funcion

    Returns:
        MergedSchemaDescriptor, a namedtuple that contains the AST of the merged schema,
        and the map from names of types/query type fields to the id of the schema that they
        came from. Scalars and directives will not appear in the map, as the same set of
        scalars and directives are expected to be defined in every schema.

    Raises:
        - ValueError if some schema identifier is not a nonempty string of alphanumeric
          characters and underscores
        - SchemaStructureError if the schema does not have the expected form; in particular, if
          the AST does not represent a valid schema, if any query type field does not have the
          same name as the type that it queries, if the schema contains type extensions or
          input object definitions, or if the schema contains mutations or subscriptions
        - SchemaNameConflictError if there are conflicts between the names of
          types/interfaces/enums/scalars, or conflicts between the definition of directives
          with the same name
    """
    if len(schema_id_to_ast) == 0:
        raise ValueError(u'Expected a nonzero number of schemas to merge.')

    query_type = 'RootSchemaQuery'
    merged_schema_ast = _get_basic_schema_ast(query_type)  # Document

    name_to_schema_id = {}  # Dict[str, str], name of type/interface/enum/union to schema id
    scalars = {'String', 'Int', 'Float', 'Boolean', 'ID'}  # Set[str], user defined + builtins
    directives = {}  # Dict[str, DirectiveDefinition]

    for current_schema_id, current_ast in six.iteritems(schema_id_to_ast):
        # Check input schema identifier is a string of alphanumeric characters and underscores
        check_schema_identifier_is_valid(current_schema_id)
        # Check input schema satisfies various structural requirements
        check_ast_schema_is_valid(current_ast)

        current_schema = build_ast_schema(current_ast)
        current_query_type = get_query_type_name(current_schema)

        # Merge current_ast into merged_schema_ast.
        # Concatenate new scalars, new directives, and type definitions other than the query
        # type to definitions list.
        # Raise errors for conflicting scalars, directives, or types.
        new_definitions = current_ast.definitions  # List[Node]
        new_query_type_fields = None  # List[FieldDefinition]

        for new_definition in new_definitions:
            if isinstance(new_definition, ast_types.SchemaDefinition):
                continue
            elif (
                isinstance(new_definition, ast_types.ObjectTypeDefinition) and
                new_definition.name.value == current_query_type
            ):  # query type definition
                new_query_type_fields = new_definition.fields  # List[FieldDefinition]
            elif isinstance(new_definition, ast_types.DirectiveDefinition):
                _process_directive_definition(
                    new_definition, directives, merged_schema_ast
                )
            elif isinstance(new_definition, ast_types.ScalarTypeDefinition):
                _process_scalar_definition(
                    new_definition, scalars, name_to_schema_id, merged_schema_ast
                )
            elif isinstance(new_definition, (
                ast_types.EnumTypeDefinition,
                ast_types.InterfaceTypeDefinition,
                ast_types.ObjectTypeDefinition,
                ast_types.UnionTypeDefinition,
            )):
                _process_generic_type_definition(
                    new_definition, current_schema_id, scalars, name_to_schema_id, merged_schema_ast
                )
            else:  # All definition types should've been covered
                raise AssertionError(
                    u'Missed definition type: "{}"'.format(type(new_definition).__name__)
                )

        # Concatenate all query type fields.
        # Since query_type was taken from the schema built from the input AST, the query type
        # should never be not found.
        if new_query_type_fields is None:
            raise AssertionError(u'Query type "{}" field definitions unexpected not '
                                 u'found.'.format(current_query_type))
        # Note that as field names and type names have been confirmed to match up, and types
        # were merged without name conflicts, query type fields can also be safely merged.
        query_type_index = 1  # Query type is the second entry in the list of definitions
        merged_schema_ast.definitions[query_type_index].fields.extend(new_query_type_fields)

    return MergedSchemaDescriptor(
        schema_ast=merged_schema_ast,
        name_to_schema_id=name_to_schema_id
    )


def _get_basic_schema_ast(query_type):
    """Create a basic AST Document representing a nearly blank schema.

    The output AST contains a single query type, whose name is the input string. The query type
    is guaranteed to be the second entry of Document definitions, after the schema definition.
    The query type has no fields.

    Args:
        query_type: str, name of the query type for the schema

    Returns:
        Document, representing a nearly blank schema
    """
    blank_ast = ast_types.Document(
        definitions=[
            ast_types.SchemaDefinition(
                operation_types=[
                    ast_types.OperationTypeDefinition(
                        operation='query',
                        type=ast_types.NamedType(
                            name=ast_types.Name(value=query_type)
                        ),
                    )
                ],
                directives=[],
            ),
            ast_types.ObjectTypeDefinition(
                name=ast_types.Name(value=query_type),
                fields=[],
                interfaces=[],
                directives=[],
            ),
        ]
    )
    return blank_ast


def _process_directive_definition(directive, existing_directives, merged_schema_ast):
    """Compare new directive against existing directives, update records and schema.

    Args:
        directive: DirectiveDefinition, an AST node representing the definition of a directive
        existing_directives: Dict[str, DirectiveDefinition], mapping the name of each existing
                             directive to the AST node defining it; modified by this function
        merged_schema_ast: Document, AST representing a schema; modified by this function
    """
    directive_name = directive.name.value
    if directive_name in existing_directives:
        if directive == existing_directives[directive_name]:
            return
        else:
            raise SchemaNameConflictError(
                u'Directive "{}" with definition "{}" has already been defined with '
                u'definition "{}".'.format(
                    directive_name,
                    print_ast(directive),
                    print_ast(existing_directives[directive_name]),
                )
            )
    # new directive
    merged_schema_ast.definitions.append(directive)
    existing_directives[directive_name] = directive


def _process_scalar_definition(scalar, existing_scalars, name_to_schema_id, merged_schema_ast):
    """Compare new scalar against existing scalars and types, update records and schema.

    Args:
        scalar: ScalarDefinition, an AST node representing the definition of a scalar
        existing_scalars: Set[str], set of names of all existing scalars; modified by this
                          function
        name_to_schema_id: Dict[str, str], mapping names of types to the identifier of the schema
                           that they came from
        merged_schema_ast: Document, AST representing a schema; modified by this function
    """
    scalar_name = scalar.name.value
    if scalar_name in existing_scalars:
        return
    if scalar_name in name_to_schema_id:
        raise SchemaNameConflictError(
            u'New scalar "{}" clashes with existing type "{}" in schema "{}". Consider '
            u'renaming type "{}" in schema "{}" using the tool rename_schema before merging '
            u'to avoid conflicts.'.format(
                scalar_name, scalar_name, name_to_schema_id[scalar_name],
                scalar_name, name_to_schema_id[scalar_name]
            )
        )
    # new, valid scalar
    merged_schema_ast.definitions.append(scalar)
    existing_scalars.add(scalar_name)


def _process_generic_type_definition(generic_type, schema_id, existing_scalars, name_to_schema_id,
                                     merged_schema_ast):
    """Compare new type against existing scalars and types, update records and schema.

    Args:
        generic_type: Any of EnumTypeDefinition, InterfaceTypeDefinition, ObjectTypeDefinition,
                      or UnionTypeDefinition, an AST node representing the definition of a type
        schema_id: str, the identifier of the schema that this type came from
        existing_scalars: Set[str], set of names of all existing scalars
        name_to_schema_id: Dict[str, str], mapping names of types to the identifier of the schema
                           that they came from; modified by this function
        merged_schema_ast: Document, AST representing a schema; modified by this function
    """
    type_name = generic_type.name.value
    if type_name in existing_scalars:
        raise SchemaNameConflictError(
            u'New type "{}" in schema "{}" clashes with existing scalar. Consider '
            u'renaming type "{}" in schema "{}" using the tool rename_schema before merging '
            u'to avoid conflicts.'.format(
                type_name, schema_id, type_name, schema_id
            )
        )
    if type_name in name_to_schema_id:
        raise SchemaNameConflictError(
            u'New type "{}" in schema "{}" clashes with existing type "{}" in schema "{}". '
            u'Consider renaming type "{}" in either schema before merging to avoid '
            u'conflicts.'.format(
                type_name, schema_id, type_name, name_to_schema_id[type_name], type_name
            )
        )
    merged_schema_ast.definitions.append(generic_type)
    name_to_schema_id[type_name] = schema_id
