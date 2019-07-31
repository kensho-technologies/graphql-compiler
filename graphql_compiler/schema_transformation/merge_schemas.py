# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import deepcopy

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
        'type_name_to_schema_id',  # Dict[str, str], mapping type name to the id of its schema
    )
)


CrossSchemaEdgeDescriptor = namedtuple(
    'CrossSchemaEdgeDescriptor', (
        'edge_name',  # str, name used for the corresponding in and out fields
        'outbound_field_reference',  # FieldReference namedtuple for the outbound field
        'inbound_field_reference',  # FieldReference namedtuple for the inbound field
        'out_edge_only',  # bool, whether or not the edge is bidirectional
    )
)


FieldReference = namedtuple(
    'FieldReference', (
        'schema_id',  # str, identifier for the schema of the field
        'type_name',  # str, name of the object or interface that the field belongs to
        'field_name',  # str, name of the field, used in the stich directive
    )
)


def merge_schemas(schema_id_to_ast, cross_schema_edges, type_equivalence_hints=None):
    """Merge all input schemas and add all cross schema edges.

    The merged schema will contain all object, interface, union, enum, scalar, and directive
    definitions from input schemas. The fields of its query type will be the union of the
    fields of the query types of each input schema.

    Cross schema edges will be incorporated by adding vertex fields with a @stitch directive
    to appropriate vertex types. New fields will be named out_ or in_ concatenated
    with the edge name. New vertex fields will be added to the specified outbound and inbound
    vertices and to all of their subclass vertices.

    Args:
        schema_id_to_ast: OrderedDict[str, Document], where keys are names/identifiers of
                          schemas, and values are ASTs describing schemas. The ASTs will not
                          be modified by this function
        cross_schema_edges: List[CrossSchemaEdgeDescriptor], containing all edges connecting
                            fields in multiple schemas to be added to the merged schema
        type_equivalence_hints: Dict[GraphQLObjectType, GraphQLUnionType].
                                Used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces).
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union

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
          types/interfaces/enums/scalars, conflicts between the names of fields (including
          fields created by cross schema edges), or conflicts between the definition of
          directives with the same name
        - InvalidCrossSchemaEdgeError if some cross schema edge provided lies within one schema,
          refers nonexistent schemas, types, fields, or connects non-scalar or non-matching
          fields
    """
    if len(schema_id_to_ast) == 0:
        raise ValueError(u'Expected a nonzero number of schemas to merge.')

    query_type = 'RootSchemaQuery'
    merged_schema_ast = _get_basic_schema_ast(query_type)  # Document

    type_name_to_schema_id = {}  # Dict[str, str], name of object/interface/enum/union to schema id
    scalars = {'String', 'Int', 'Float', 'Boolean', 'ID'}  # Set[str], user defined + builtins
    directives = {}  # Dict[str, DirectiveDefinition]

    for current_schema_id, current_ast in six.iteritems(schema_id_to_ast):
        current_ast = deepcopy(current_ast)
        _accumulate_types(merged_schema_ast, type_name_to_schema_id, scalars, directives,
                          current_schema_id, current_ast)

    return MergedSchemaDescriptor(
        schema_ast=merged_schema_ast,
        type_name_to_schema_id=type_name_to_schema_id
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


def _accumulate_types(merged_schema_ast, type_name_to_schema_id, scalars, directives,
                      current_schema_id, current_ast):
    """Add all types and query type fields of current_ast into merged_schema_ast.

    Args:
        merged_schema_ast: Document. It is modified by this function as current_ast is
                           incorporated
        type_name_to_schema_id: Dict[str, str], mapping type name to the id of the schema that
                                the type is from. It is modified by this function
        scalars: Set[str], names of all scalars in the merged_schema so far. It is potentially
                 modified by this function
        directives: Dict[str, DirectiveDefinition], mapping directive name to definition.
                    It is potentially modified by this function
        current_schema_id: str, identifier of the schema being merged
        current_ast: Document, representing the schema being merged into merged_schema_ast

    Raises:
        - ValueError if the schema identifier is not a nonempty string of alphanumeric
          characters and underscores
        - SchemaStructureError if the schema does not have the expected form; in particular, if
          the AST does not represent a valid schema, if any query type field does not have the
          same name as the type that it queries, if the schema contains type extensions or
          input object definitions, or if the schema contains mutations or subscriptions
        - SchemaNameConflictError if there are conflicts between the names of
          types/interfaces/enums/scalars, or conflicts between the definition of directives
          with the same name
    """
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
                new_definition, scalars, type_name_to_schema_id, merged_schema_ast
            )
        elif isinstance(new_definition, (
            ast_types.EnumTypeDefinition,
            ast_types.InterfaceTypeDefinition,
            ast_types.ObjectTypeDefinition,
            ast_types.UnionTypeDefinition,
        )):
            _process_generic_type_definition(
                new_definition, current_schema_id, scalars, type_name_to_schema_id,
                merged_schema_ast
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

    # Query type is the second entry in the list of definitions of the merged_schema_ast,
    # as guaranteed by _get_basic_schema_ast
    query_type_index = 1
    merged_schema_ast.definitions[query_type_index].fields.extend(new_query_type_fields)


def _process_directive_definition(directive, existing_directives, merged_schema_ast):
    """Compare new directive against existing directives, update records and schema.

    Args:
        directive: DirectiveDefinition, an AST node representing the definition of a directive
        existing_directives: Dict[str, DirectiveDefinition], mapping the name of each existing
                             directive to the AST node defining it. It is modified by this
                             function
        merged_schema_ast: Document, AST representing a schema. It is modified by this function
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


def _process_scalar_definition(scalar, existing_scalars, type_name_to_schema_id,
                               merged_schema_ast):
    """Compare new scalar against existing scalars and types, update records and schema.

    Args:
        scalar: ScalarDefinition, an AST node representing the definition of a scalar
        existing_scalars: Set[str], set of names of all existing scalars. It is modified by this
                          function
        type_name_to_schema_id: Dict[str, str], mapping names of types to the identifier of the
                                schema that they came from
        merged_schema_ast: Document, AST representing a schema. It is modified by this function
    """
    scalar_name = scalar.name.value
    if scalar_name in existing_scalars:
        return
    if scalar_name in type_name_to_schema_id:
        raise SchemaNameConflictError(
            u'New scalar "{}" clashes with existing type "{}" in schema "{}". Consider '
            u'renaming type "{}" in schema "{}" using the tool rename_schema before merging '
            u'to avoid conflicts.'.format(
                scalar_name, scalar_name, type_name_to_schema_id[scalar_name],
                scalar_name, type_name_to_schema_id[scalar_name]
            )
        )
    # new, valid scalar
    merged_schema_ast.definitions.append(scalar)
    existing_scalars.add(scalar_name)


def _process_generic_type_definition(generic_type, schema_id, existing_scalars,
                                     type_name_to_schema_id, merged_schema_ast):
    """Compare new type against existing scalars and types, update records and schema.

    Args:
        generic_type: Any of EnumTypeDefinition, InterfaceTypeDefinition, ObjectTypeDefinition,
                      or UnionTypeDefinition, an AST node representing the definition of a type
        schema_id: str, the identifier of the schema that this type came from
        existing_scalars: Set[str], set of names of all existing scalars
        type_name_to_schema_id: Dict[str, str], mapping names of types to the identifier of the
                                schema that they came from. It is modified by this function
        merged_schema_ast: Document, AST representing a schema. It is modified by this function
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
    if type_name in type_name_to_schema_id:
        raise SchemaNameConflictError(
            u'New type "{}" in schema "{}" clashes with existing type "{}" in schema "{}". '
            u'Consider renaming type "{}" in either schema before merging to avoid '
            u'conflicts.'.format(
                type_name, schema_id, type_name, type_name_to_schema_id[type_name], type_name
            )
        )
    merged_schema_ast.definitions.append(generic_type)
    type_name_to_schema_id[type_name] = schema_id
