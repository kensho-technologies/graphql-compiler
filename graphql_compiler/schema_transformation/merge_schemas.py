# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import deepcopy

from graphql import build_ast_schema
from graphql.language import ast as ast_types
from graphql.language.printer import print_ast
import six

from .utils import (
    SchemaNameConflictError, SchemaStructureError, check_ast_schema_is_valid, get_query_type_name
)


MergedSchemaDescriptor = namedtuple(
    'MergedSchemaDescriptor', (
        'schema_ast',  # Document, AST representing the merged schema
        'name_id_map',  # Dict[str, str], type name to id of the schema the type is from
    )
)


def basic_schema_ast(query_type):
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


def merge_schemas(schemas_dict):
    """Check that input schemas do not contain conflicting definitions, then merge.

    Merged schema will contain all type, interface, enum, scalar, and directive definitions
    from input schemas. The fields of its query type will be the union of the fields of the
    query types of each input schema.
    schemas.

    Args:
        schemas_dict: OrderedDict where keys are schema_identifiers, and values are
                      ASTs (Documents) describing schemas. The ASTs will not be modified by
                      this function

    Returns:
        MergedSchemaDescriptor, a namedtuple that contains the AST of the merged schema,
        and the map from names of types/query type fields to the id of the schema that they
        came from

    Raises:
        SchemaStructureError if the schema does not have the expected form; in particular, if
        the AST does not represent a valid schema, if any query type field does not have the
        same name as the type that it queries, if the schema contains type extensions or
        input object definitions, or if the schema contains mutations or subscriptions
        SchemaNameConflictError if there are conflicts between the names of
        types/interfaces/enums/scalars, or conflicts between the definition of directives
        with the same name
    """
    if len(schemas_dict) == 0:
        raise ValueError(u'Expected a nonzero number of schemas to merge.')

    query_type = 'RootSchemaQuery'
    # NOTE: currently, the query type will always be named RootSchemaQuery
    # could be changed so the user has an input, or by changed to always use the query type
    # name in the first schema in the input, if desired
    merged_schema_ast = basic_schema_ast(query_type)  # Document
    merged_definitions = merged_schema_ast.definitions  # List[Node]
    merged_query_type_fields = merged_definitions[1].fields  # List[FieldDefinition]

    name_id_map = {}  # Dict[str, str], name of type/interface/enum/union to schema id
    scalars = {'String', 'Int', 'Float', 'Boolean', 'ID'}  # Set[str], user defined + builtins
    directives = {}  # Dict[str, DirectiveDefinition]

    for cur_schema_id, cur_ast in six.iteritems(schemas_dict):
        cur_ast = deepcopy(cur_ast)

        try:
            cur_schema = build_ast_schema(cur_ast)
        except Exception as e:
            raise SchemaStructureError(u'Input is not a valid schema. Message: {}'.format(e))

        # Check additional structural requirements
        check_ast_schema_is_valid(cur_ast, cur_schema)

        cur_query_type = get_query_type_name(cur_schema)

        # Merge cur_ast into merged_schema_ast
        # Concatenate new scalars, new directive, and all type definitions to merged_definitions
        # Raise errors for conflicting scalars, directives, or types
        new_definitions = cur_ast.definitions  # List[Node]
        new_query_type_fields = None  # List[FieldDefinition]
        for new_definition in new_definitions:
            if isinstance(new_definition, ast_types.SchemaDefinition):
                continue

            new_name = new_definition.name.value

            if (
                isinstance(new_definition, ast_types.ObjectTypeDefinition) and
                new_name == cur_query_type
            ):  # query type definition
                new_query_type_fields = new_definition.fields  # List[FieldDefinition]

            elif isinstance(new_definition, ast_types.ScalarTypeDefinition):
                if new_name in scalars:  # existing scalar
                    continue
                if new_name in name_id_map:  # new scalar clashing with existing type
                    raise SchemaNameConflictError(
                        u'New scalar "{}" clashes with existing type.'.format(new_name)
                    )
                # new, valid scalar
                merged_definitions.append(new_definition)  # Add to AST
                scalars.add(new_name)

            elif isinstance(new_definition, ast_types.DirectiveDefinition):
                if new_name in directives:  # existing directive
                    if new_definition == directives[new_name]:  # definitions agree
                        continue
                    else:  # definitions disagree
                        raise SchemaNameConflictError(
                            u'Directive "{}" with definition "{}" has already been defined with '
                            'definition "{}".'.format(new_name, print_ast(new_definition),
                                                      print_ast(directives[new_name]))
                        )
                # new directive
                merged_definitions.append(new_definition)  # Add to AST
                directives[new_name] = new_definition

            else:  # Generic type definition
                if new_name in scalars:
                    raise SchemaNameConflictError(
                        u'New type "{}" clashes with existing scalar.'.format(new_name)
                    )
                if new_name in name_id_map:
                    raise SchemaNameConflictError(
                        u'New type "{}" clashes with existing type.'.format(new_name)
                    )
                merged_definitions.append(new_definition)
                name_id_map[new_name] = cur_schema_id

        # Concatenate all query type fields
        # Given that names of query type fields agree with their queried types, and that type
        # were merged without conflicts, query type fields will also merge without conflicts
        # and it is not necessary to check for identical names
        if new_query_type_fields is None:
            raise AssertionError(u'Query type field definitions unexpected not found.')

        merged_query_type_fields.extend(new_query_type_fields)

    return MergedSchemaDescriptor(schema_ast=merged_schema_ast, name_id_map=name_id_map)
