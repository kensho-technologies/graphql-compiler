# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple
from copy import deepcopy

from graphql import build_ast_schema
from graphql.language import ast as ast_types
from graphql.language.printer import print_ast
import six

from .subclass import compute_subclass_sets
from .utils import (
    SchemaNameConflictError, InvalidCrossSchemaEdgeError, check_ast_schema_is_valid,
    check_schema_identifier_is_valid, get_query_type_name
)


MergedSchemaDescriptor = namedtuple(
    'MergedSchemaDescriptor', (
        'schema_ast',  # Document, AST representing the merged schema
        'type_name_to_schema_id',
        # Dict[str, str], mapping type name to the id of the schema that the type is from
    )
)


CrossSchemaEdgeDescriptor = namedtuple(
    'CrossSchemaEdgeDescriptor', (
        'edge_name',  # str, name used for the corresponding in and out fields
        'outbound_side',  # FieldReference namedtuple for the outbound (source) field
        'inbound_side',  # FieldReference namedtuple for the inbound (sink) field
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
    to appropriate vertices (types). New fields will be named out_ or in_ concatenated
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
          types/interfaces/enums/scalars, conflicts between the names of fields, or conflicts
          between the definition of directives with the same name
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

    if type_equivalence_hints is None:
        type_equivalence_hints = {}
    _add_cross_schema_edges(merged_schema_ast, type_name_to_schema_id, scalars,
                            cross_schema_edges, type_equivalence_hints, query_type)

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
    query_type_index = 1  # Query type is the second entry in the list of definitions
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


def _add_cross_schema_edges(schema_ast, type_name_to_schema_id, scalars, cross_schema_edges,
                            type_equivalence_hints, query_type):
    """Add cross schema edges into the schema AST.

    Each cross schema edge will be incorporated into the schema by adding vertex fields
    with a @stitch directive to relevant vertices (types). New fields will be named out_
    or in_ concatenated with the edge name.

    The type of the new field will either be the type of the opposing vertex specified in
    the cross schema edge, or the equivalent union type of the type of the opposing vertex
    if such a union type is specified by type_equivalence_hints.

    New vertex fields will be added to not only each vertex specified by the cross schema
    edge, but to all of their subclass vertices as well.

    For examples demonstrating the above behaviors, see tests in test_merge_schemas.py that
    involve subclasses.

    Args:
        scheam_ast: Document. It is modified by this function
        type_name_to_schema_id: Dict[str, str], mapping type name to the id of the schema that the
                                type is from
        scalars: Set[str], names of all scalars in the merged_schema so far
        cross_schema_edges: List[CrossSchemaEdgeDescriptor], containing all edges connecting
                            fields in multiple schemas to be added to the merged schema
        type_equivalence_hints: Dict[GraphQLObjectType, GraphQLUnionType].
                                Used as a workaround for GraphQL's lack of support for
                                inheritance across "types" (i.e. non-interfaces).
                                The key-value pairs in the dict specify that the "key" type
                                is equivalent to the "value" type, i.e. that the GraphQL type or
                                interface in the key is the most-derived common supertype
                                of every GraphQL type in the "value" GraphQL union
        query_type: str, name of the query type in the merged schema

    Raises:
        - SchemaNameConflictError if any cross schema edge name causes a name conflict with
          existing fields, or fields created by previous cross schema edges
        - InvalidCrossSchemaEdgeError if any cross schema edge lies within one schema, refers
          to nonexistent schemas, types, or fields, refers to Union types, stitches together
          fields that are not of a scalar type, or stitches together fields that are of
          different scalar types
    """
    # Build map of definitions for ease of modification
    type_name_to_definition = {}  # Dict[str, (Interface/Object)TypeDefinition]
    # fieldless_type_names = set()  # Set[str], contains Union, Enum, Scalar
    # The above is just for better error messages

    for definition in schema_ast.definitions:
        if (
            isinstance(definition, ast_types.ObjectTypeDefinition) and
            definition.name.value == query_type
        ):  # query type definition
            continue
        if isinstance(definition, (
            ast_types.InterfaceTypeDefinition,
            ast_types.ObjectTypeDefinition,
        )):
            type_name_to_definition[definition.name.value] = definition

    # NOTE: All merge_schemas needs is the dict mapping names to names, not the dict mapping
    # GraphQLObjects to GraphQLObjects. However, elsewhere in the repo, type_equivalence_hints
    # is a map of objects to objects, and thus we use that same input for consistency
    equivalent_type_names = {
        object_type.name: union_type.name
        for object_type, union_type in six.iteritems(type_equivalence_hints)
    }
    subclass_sets = compute_subclass_sets(build_ast_schema(schema_ast), type_equivalence_hints)

    # Iterate through edges list, incorporate each edge on one or both sides
    for cross_schema_edge in cross_schema_edges:
        _check_cross_schema_edge_is_valid(type_name_to_definition, type_name_to_schema_id,
                                          scalars, cross_schema_edge)

        edge_name = cross_schema_edge.edge_name
        outbound_side = cross_schema_edge.outbound_side
        inbound_side = cross_schema_edge.inbound_side

        # Get name of the type referenced by the edges in either direction
        # This is equal to the sink side's equivalent union type if it has one
        outbound_edge_sink_type_name = equivalent_type_names.get(
            inbound_side.type_name, inbound_side.type_name
        )
        inbound_edge_sink_type_name = equivalent_type_names.get(
            outbound_side.type_name, outbound_side.type_name
        )

        # Get set of names subclasses, aka all the types that need the new edge field
        outbound_edge_source_type_names = subclass_sets.get(outbound_side.type_name)
        inbound_edge_source_type_names = subclass_sets.get(inbound_side.type_name)

        for outbound_edge_source_type_name in outbound_edge_source_type_names:
            source_type_node = type_name_to_definition[outbound_edge_source_type_name]
            _add_edge_field(source_type_node, outbound_edge_sink_type_name,
                            outbound_side.field_name, inbound_side.field_name, edge_name, 'out')

        if not cross_schema_edge.out_edge_only:
            for inbound_edge_source_type_name in inbound_edge_source_type_names:
                source_type_node = type_name_to_definition[inbound_edge_source_type_name]
                _add_edge_field(source_type_node, inbound_edge_sink_type_name,
                                inbound_side.field_name, outbound_side.field_name, edge_name, 'in')


def _check_cross_schema_edge_is_valid(type_name_to_definition, type_name_to_schema_id, scalars,
                                      cross_schema_edge):
    """Check that the edge crosses schemas and has valid field references of correct types.

    Args:
        type_name_to_definition: Dict[str, (Interface/Object/Union)TypeDefinition], mapping
                                 name of types to their definitions
        type_name_to_schema_id: Dict[str, str], mapping type name to the id of the schema that the
                                type is from
        scalars: Set[str], names of all scalars in the merged_schema so far
        cross_schema_edge: CrossSchemaEdgeDescriptor namedtuple, the edge that we check the
                           validity of

    Raises:
        - InvalidCrossSchemaEdgeError if the cross schema edge lies within one schema, refers
          to nonexistent schemas, types, or fields, refers to Union types, stitches together
          fields that are not of a scalar type, or stitches together fields that are of
          different scalar types
    """
    outbound_side = cross_schema_edge.outbound_side
    inbound_side = cross_schema_edge.inbound_side

    _check_field_reference_is_valid(type_name_to_definition, type_name_to_schema_id, outbound_side)
    _check_field_reference_is_valid(type_name_to_definition, type_name_to_schema_id, inbound_side)

    if outbound_side.schema_id == inbound_side.schema_id:  # not cross schema
        raise InvalidCrossSchemaEdgeError(
            u'Edge "{}" does not cross schemas.'.format(cross_schema_edge)
        )

    _check_field_types_are_matching_scalars(type_name_to_definition, scalars, cross_schema_edge)


def _check_field_reference_is_valid(type_name_to_definition, type_name_to_schema_id,
                                    field_reference):
    """Check that the field reference refers to a valid field.

    In particular, check that the field reference is on a type that exists in the correct
    schema, and that the type contains the field of the expected name.

    Args:
        type_name_to_definition: Dict[str, (Interface/Object/Union)TypeDefinition], mapping
                                 name of types to their definitions
        type_name_to_schema_id: Dict[str, str], mapping type name to the id of the schema that the
                                type is from
        field_reference: FieldReference namedtuple, what we check the validity of

    Raises:
        - InvalidCrossSchemaEdgeError if the cross schema edge refers to nonexistent schemas,
          types, or fields, or refers to Union types
    """
    schema_id = field_reference.schema_id
    type_name = field_reference.type_name
    field_name = field_reference.field_name

    # Error if the type is nonexistent (includes if type is an enum or scalar)
    # TODO: Consider improving error message if type is a union or enum or scalar
    if type_name not in type_name_to_definition:
        raise InvalidCrossSchemaEdgeError(
            u'Type "{}" specified in the field reference "{}" is not found '
            u'in the merged schema.'.format(type_name, field_reference)
        )

    # Error if the type is in a wrong or nonexistent schema
    if type_name_to_schema_id[type_name] != schema_id:
        raise InvalidCrossSchemaEdgeError(
            u'Type "{}" specified in the field reference "{}" is expected to be in '
            u'schema "{}", but is instead bound in schema "{}"'.format(
                type_name, field_reference, schema_id, type_name_to_schema_id[type_name]
            )
        )

    # Error if the type doesn't have the expected field
    type_definition = type_name_to_definition[type_name]
    type_fields = type_definition.fields
    if not any(field.name.value==field_name for field in type_fields):
        raise InvalidCrossSchemaEdgeError(
            u'Field "{}" is not found under type "{}" in schema "{}", as expected by the '
            u'field reference "{}".'.format(
                field_name, type_name, schema_id, field_reference
            )
        )


def _check_field_types_are_matching_scalars(type_name_to_definition, scalars, cross_schema_edge):
    """Check that stitched fields in a cross schema edge are of the same scalar type.

    It is also legal for fields to be of a NonNull wrapped scalar type.

    Args:
        type_name_to_definition: Dict[str, (Interface/Object/Union)TypeDefinition], mapping
                                 name of types to their definitions
        scalars: Set[str], names of all scalars in the merged_schema so far
        cross_schema_edge: CrossSchemaEdgeDescriptor namedtuple, the edge that we check the
                           validity of

    Raises:
        - InvalidCrossSchemaEdgeError if the cross schema edge stitches together fields that are
          not of a scalar type, or stitched together fields that are of different scalar types
    """
    field_type_names = []

    for direction, field_reference in (
        ('out', cross_schema_edge.outbound_side),
        ('in', cross_schema_edge.inbound_side),
    ):
        type_name = field_reference.type_name
        field_name = field_reference.field_name

        fields = type_name_to_definition[type_name].fields  # List[FieldDefinition]
        field_type = None
        for field in fields:
            if field.name.value == field_name:
                field_type = field.type
                while isinstance(field_type, ast_types.NonNullType):  # strip NonNull
                    field_type = field_type.type
                break

        if field_type is None:  # should never happen after _check_field_reference_is_valid
            raise AssertionError(u'Field "{}" unexpectedly not found.'.format(field_name))

        if isinstance(field_type, ast_types.ListType):
            raise InvalidCrossSchemaEdgeError(
                u'The {}bound field of cross schema edge "{}" gives a list, while it '
                u'should be a single scalar'.format(
                    direction, cross_schema_edge
                )
            )
        elif isinstance(field_type, ast_types.NamedType):
            if field_type.name.value not in scalars:
                raise InvalidCrossSchemaEdgeError(
                    u'The {}bound field of cross schema edge "{}" is of type "{}", which '
                    u'is not a scalar'.format(
                        direction, cross_schema_edge, field_type.name.value
                    )
                )
        else:  # since NonNull is stripped, field_type can only be ListType or NamedType
            raise AssertionError(
                u'Field has missed type "{}"'.format(type(field_type).__name__)
            )

        field_type_names.append(field_type.name.value)

    if field_type_names[0] != field_type_names[1]:  # fields return different scalars
        raise InvalidCrossSchemaEdgeError(
            u'The outbound and inbound fields of edge "{}" are of different types, '
            u'"{}" and "{}". They are expected to be of the same scalar type.'.format(
                cross_schema_edge, field_type_names[0], field_type_names[1]
            )
        )


def _add_edge_field(source_type_node, sink_type_name, source_field_name, sink_field_name,
                    edge_name, direction):
    """Add one direction of the specified edge as a field of the source type.

    Args:
        source_type_node: (Interface/Object)TypeDefinition, where a new field representing
                          one direction of the edge will be added. It is modified by this
                          function
        sink_type_name: str, name of the type that the edge leads to
        source_field_name: str, name of the source side field that will be stitched
        sink_field_name: str, name of the sink side field that will be stitched
        edge_name: str, name of the edge that will be used to name the new field
        direction: str, either 'in' or 'out'

    Raises:
        - SchemaNameConflictError if the new cross schema edge name causes a name conflict with
          existing fields, or fields created by previous cross schema edges
    """
    type_fields = source_type_node.fields
    new_edge_field_name = direction + '_' + edge_name

    # Error if new edge causes a field name clash
    if any(field.name.value == new_edge_field_name for field in type_fields):
        raise SchemaNameConflictError(
            u'New field "{}" under type "{}" created by the {}bound field of edge named '
            u'"{}" clashes with an existing field of the same name.'.format(
                new_edge_field_name, source_type_node.name.value, direction, edge_name
            )
        )

    new_edge_field_node = ast_types.FieldDefinition(
        name=ast_types.Name(value=new_edge_field_name),
        arguments=[],
        type=ast_types.ListType(
            type=ast_types.NamedType(
                name=ast_types.Name(value=sink_type_name),
            ),
        ),
        directives=[
            _build_stitch_directive(source_field_name, sink_field_name),
        ],
    )

    type_fields.append(new_edge_field_node)


def _build_stitch_directive(source_field_name, sink_field_name):
    """Build a Directive node for the stitch directive."""
    return ast_types.Directive(
        name=ast_types.Name(value='stitch'),
        arguments=[
            ast_types.Argument(
                name=ast_types.Name(value='source_field'),
                value=ast_types.StringValue(value=source_field_name),
            ),
            ast_types.Argument(
                name=ast_types.Name(value='sink_field'),
                value=ast_types.StringValue(value=sink_field_name),
            ),
        ],
    )
