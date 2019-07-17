# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import deepcopy

from graphql import build_ast_schema
from graphql.language import ast as ast_types
from graphql.language.printer import print_ast
import six

from .utils import SchemaNameConflictError, check_ast_schema_is_valid, get_query_type_name


MergedSchemaDescriptor = namedtuple(
    'MergedSchemaDescriptor', (
        'schema_ast',  # Document, AST representing the merged schema
        'name_to_schema_id',  # Dict[str, str], type name to id of the schema the type is from
    )
)


def _basic_schema_ast(query_type):
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

    Args:
        schemas_dict: OrderedDict[str, Document], where keys are names/identifiers of schemas,
                      and values are ASTs describing schemas. The ASTs will not be modified
                      by this funcion

    Returns:
        MergedSchemaDescriptor, a namedtuple that contains the AST of the merged schema,
        and the map from names of types/query type fields to the id of the schema that they
        came from. Scalars and directives will not appear in the map, as the same set of
        scalars and directives are expected to be defined in every schema.

    Raises:
        - SchemaStructureError if the schema does not have the expected form; in particular, if
          the AST does not represent a valid schema, if any query type field does not have the
          same name as the type that it queries, if the schema contains type extensions or
          input object definitions, or if the schema contains mutations or subscriptions
        - SchemaNameConflictError if there are conflicts between the names of
          types/interfaces/enums/scalars, or conflicts between the definition of directives
          with the same name
    """
    if len(schemas_dict) == 0:
        raise ValueError(u'Expected a nonzero number of schemas to merge.')

    query_type = 'RootSchemaQuery'
    merged_schema_ast = _basic_schema_ast(query_type)  # Document

    name_to_schema_id = {}  # Dict[str, str], name of type/interface/enum/union to schema id
    scalars = {'String', 'Int', 'Float', 'Boolean', 'ID'}  # Set[str], user defined + builtins
    directives = {}  # Dict[str, DirectiveDefinition]

    for cur_schema_id, cur_ast in six.iteritems(schemas_dict):
        # Prevent aliasing between output and input
        cur_ast = deepcopy(cur_ast)

        # Check input schema satisfies various structural requirements
        check_ast_schema_is_valid(cur_ast)

        cur_schema = build_ast_schema(cur_ast)
        cur_query_type = get_query_type_name(cur_schema)

        # Merge cur_ast into merged_schema_ast
        # Concatenate new scalars, new directives, and type definitions other than the query
        # type to definitions list
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

            elif isinstance(new_definition, ast_types.DirectiveDefinition):
                if new_name in directives:  # existing directive
                    if new_definition == directives[new_name]:  # definitions agree
                        continue
                    else:  # definitions disagree
                        raise SchemaNameConflictError(
                            u'Directive "{}" with definition "{}" has already been defined with '
                            u'definition "{}".'.format(new_name, print_ast(new_definition),
                                                       print_ast(directives[new_name]))
                        )
                # new directive
                merged_schema_ast.definitions.append(new_definition)  # Add to AST
                directives[new_name] = new_definition

            elif isinstance(new_definition, ast_types.ScalarTypeDefinition):
                if new_name in scalars:  # existing scalar
                    continue
                if new_name in name_to_schema_id:  # new scalar clashing with existing type
                    raise SchemaNameConflictError(
                        u'New scalar "{}" clashes with existing type.'.format(new_name)
                    )
                # new, valid scalar
                merged_schema_ast.definitions.append(new_definition)  # Add to AST
                scalars.add(new_name)

            else:  # Generic type definition
                if new_name in scalars:
                    raise SchemaNameConflictError(
                        u'New type "{}" clashes with existing scalar.'.format(new_name)
                    )
                if new_name in name_to_schema_id:
                    raise SchemaNameConflictError(
                        u'New type "{}" clashes with existing type.'.format(new_name)
                    )
                merged_schema_ast.definitions.append(new_definition)
                name_to_schema_id[new_name] = cur_schema_id

        # Concatenate all query type fields
        # Since query_type was taken from the schema built from the input AST, the query type
        # should never be not found
        if new_query_type_fields is None:
            raise AssertionError(u'Query type "{}" field definitions unexpected not '
                                 u'found.'.format(cur_query_type))
        # Note that as field names and type names have been confirmed to match up, and types
        # were merged without name conflicts, query type fields can also be safely merged
        query_type_index = 1  # Query type is the second entry in the list of definitions
        merged_schema_ast.definitions[query_type_index].fields.extend(new_query_type_fields)

    return MergedSchemaDescriptor(
        schema_ast=merged_schema_ast,
        name_to_schema_id=name_to_schema_id
    )
