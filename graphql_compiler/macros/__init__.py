# Copyright 2019-present Kensho Technologies, LLC.
from collections import namedtuple

from graphql import parse
from graphql.language.ast import (
    DirectiveNode,
    DocumentNode,
    FieldDefinitionNode,
    InterfaceTypeDefinitionNode,
    ListTypeNode,
    NamedTypeNode,
    NameNode,
    ObjectTypeDefinitionNode,
)
from graphql.language.printer import print_ast
from graphql.pyutils import FrozenList
from graphql.utilities import build_ast_schema, print_schema
import six

from ..ast_manipulation import safe_parse_graphql
from ..compiler.subclass import compute_subclass_sets
from ..compiler.validation import validate_schema_and_query_ast
from ..exceptions import GraphQLValidationError
from .macro_edge import make_macro_edge_descriptor
from .macro_edge.directives import MacroEdgeDirective, get_schema_for_macro_edge_definitions
from .macro_expansion import expand_macros_in_query_ast
from .validation import (
    check_macro_edge_for_definition_conflicts,
    check_macro_edge_for_reversal_definition_conflicts,
)


MacroRegistry = namedtuple(
    "MacroRegistry",
    (
        # GraphQLSchema, created using the GraphQL library
        "schema_without_macros",
        # Optional dict of GraphQL interface or type -> GraphQL union.
        # Used as a workaround for GraphQL's lack of support for
        # inheritance across "types" (i.e. non-interfaces), as well as a
        # workaround for Gremlin's total lack of inheritance-awareness.
        # The key-value pairs in the dict specify that the "key" type
        # is equivalent to the "value" type, i.e. that the GraphQL type or
        # interface in the key is the most-derived common supertype
        # of every GraphQL type in the "value" GraphQL union.
        # Recursive expansion of type equivalence hints is not performed,
        # and only type-level correctness of this argument is enforced.
        # See README.md for more details on everything this parameter does.
        # *****
        # Be very careful with this option, as bad input here will
        # lead to incorrect output queries being generated.
        # *****
        "type_equivalence_hints",
        # Dict[str, Set[str]] mapping class names to the set of its subclass names.
        # A class in this context means the name of a GraphQLObjectType,
        # GraphQLUnionType or GraphQLInterface.
        "subclass_sets",
        # #################
        # Macro edge info #
        # #################
        # List[MacroEdgeDescriptor] containing all defined macro edges
        "macro_edges",
        # Dict[str, Dict[str, MacroEdgeDescriptor]] mapping:
        # class name -> (macro edge name -> MacroEdgeDescriptor)
        # If a given macro edge is defined on a class X which has subclasses A and B,
        # then this dict will contain entries for that macro edge for all of [X, A, B].
        "macro_edges_at_class",
        # Dict[str, Dict[str, MacroEdgeDescriptor]] mapping:
        # class name -> (macro edge name -> MacroEdgeDescriptor)
        # If a given macro edge has class X as a target, which has subclasses A and B,
        # then this dict will contain entries for that macro edge for all of [X, A, B].
        "macro_edges_to_class",
        # ########################################################################
        # Any other macro types we may add in the future belong under this line. #
        # ########################################################################
    ),
)


def create_macro_registry(schema, type_equivalence_hints=None, subclass_sets=None):
    """Create and return a new empty macro registry."""
    if subclass_sets is None:
        subclass_sets = compute_subclass_sets(schema, type_equivalence_hints=type_equivalence_hints)

    return MacroRegistry(
        schema_without_macros=schema,
        type_equivalence_hints=type_equivalence_hints,
        subclass_sets=subclass_sets,
        macro_edges=list(),
        macro_edges_at_class=dict(),
        macro_edges_to_class=dict(),
    )


def register_macro_edge(macro_registry, macro_edge_graphql, macro_edge_args):
    """Add the new macro edge descriptor to the provided MacroRegistry object, mutating it.

    In order to register a new macro edge, the following properties must be true:
    - The macro edge, with the addition of any output value, must become a valid query. This ensures
      that it is compliant with the schema, supplies values for all runtime and tagged parameters,
      and obeys all other rules imposed by the compiler.
    - The macro edge must not contain any directives that are prohibited in macro edge definitions.
    - The macro edge will become a new vertex field on its base type, and therefore must be named
      a vertex field name (prefixed with "out_" or "in_").
    - Any class together with its subclasses may have defined at most one macro edge with that name.
    - Any class together with its subclasses must be the target of at most one macro edge with
      that name.
    - For any macro edge named out_X (similarly, in_Y) defined at type A and with target type B,
      the reversed macro edge in_X (similarly, out_Y) defined at type B and with target type A
      either already exists, or could be defined without violating any of the above rules.

    Args:
        macro_registry: MacroRegistry object containing macro descriptors, where the new
                        macro edge descriptor should be added.
        macro_edge_graphql: string, GraphQL defining how the new macro edge should be expanded
        macro_edge_args: dict mapping strings to any type, containing any arguments the macro edge
                         requires in order to function.
    """
    # The below function will validate that the macro edge in question is valid in isolation,
    # when considered only against the macro-less schema. After geting this result,
    # we simply need to check the macro edge descriptor against other artifacts in the macro system
    # that might also cause conflicts.
    macro_descriptor = make_macro_edge_descriptor(
        macro_registry.schema_without_macros,
        macro_registry.subclass_sets,
        macro_edge_graphql,
        macro_edge_args,
        type_equivalence_hints=macro_registry.type_equivalence_hints,
    )

    # Ensure there's no conflict with macro edges defined on subclasses and superclasses.
    check_macro_edge_for_definition_conflicts(macro_registry, macro_descriptor)

    # Ensure there's no conflict between existing macro edges and the (hypothetical) reversed
    # macro edge of the one being defined.
    check_macro_edge_for_reversal_definition_conflicts(macro_registry, macro_descriptor)

    for subclass_name in macro_registry.subclass_sets[macro_descriptor.base_class_name]:
        macro_registry.macro_edges_at_class.setdefault(subclass_name, dict())[
            macro_descriptor.macro_edge_name
        ] = macro_descriptor

    for subclass_name in macro_registry.subclass_sets[macro_descriptor.target_class_name]:
        macro_registry.macro_edges_to_class.setdefault(subclass_name, dict())[
            macro_descriptor.macro_edge_name
        ] = macro_descriptor

    macro_registry.macro_edges.append(macro_descriptor)


def get_schema_with_macros(macro_registry):
    """Get a new GraphQLSchema with fields where macro edges can be used.

    Preconditions:
    1. No macro in the registry has the same name as a field on the vertex where it applies.
    2. Members of a union type do not have outgoing macros with the same name.

    An easy way to satisfy the preconditions is to create the macro_registry using
    create_macro_registry, and only update it with register_macro_edge, which does all
    the necessary validation.

    Postconditions:
    1. Every GraphQLQuery that uses macros from this registry appropriately should
       successfully type-check against the schema generated from this function.
    2. A GraphQLQuery that uses macros not present in the registry, or uses valid
       macros but on types they are not defined at should fail schema validation with
       the schema generated from this function.
    3. This function is total -- A valid macro registry should not fail to create a
       GraphQL schema with macros.

    Args:
        macro_registry: MacroRegistry object containing a schema and macro descriptors
                        we want to add to the schema.

    Returns:
        GraphQLSchema with additional fields where macro edges can be used.
    """
    # The easiest way to manipulate the schema is through its AST. The easiest
    # way to get an AST is to print it and parse it.
    schema_ast = parse(print_schema(macro_registry.schema_without_macros))

    fields_by_definition_name = {}
    for definition in schema_ast.definitions:
        if isinstance(definition, (ObjectTypeDefinitionNode, InterfaceTypeDefinitionNode)):
            # Cast to list (from FrozenList) to allow for updates.
            fields_by_definition_name[definition.name.value] = list(definition.fields)

    for class_name, macros_for_class in six.iteritems(macro_registry.macro_edges_at_class):
        for macro_edge_name, macro_edge_descriptor in six.iteritems(macros_for_class):
            list_type_at_target = ListTypeNode(
                type=NamedTypeNode(name=NameNode(value=macro_edge_descriptor.target_class_name))
            )
            arguments = []
            directives = [DirectiveNode(name=NameNode(value=MacroEdgeDirective.name))]
            fields_by_definition_name[class_name].append(
                FieldDefinitionNode(
                    name=NameNode(value=macro_edge_name),
                    arguments=arguments,
                    type=list_type_at_target,
                    directives=directives,
                )
            )

    new_definitions = []
    for definition in schema_ast.definitions:
        # Create new (Object)/(Interface)TypeDefinitionNode based on the updated fields.
        if isinstance(definition, ObjectTypeDefinitionNode):
            new_definitions.append(
                ObjectTypeDefinitionNode(
                    interfaces=definition.interfaces,
                    description=definition.description,
                    name=definition.name,
                    directives=definition.directives,
                    loc=definition.loc,
                    fields=FrozenList(fields_by_definition_name[definition.name.value]),
                )
            )
        elif isinstance(definition, InterfaceTypeDefinitionNode):
            new_definitions.append(
                InterfaceTypeDefinitionNode(
                    description=definition.description,
                    name=definition.name,
                    directives=definition.directives,
                    loc=definition.loc,
                    fields=FrozenList(fields_by_definition_name[definition.name.value]),
                )
            )
        else:
            new_definitions.append(definition)

    new_schema_ast = DocumentNode(definitions=new_definitions)
    return build_ast_schema(new_schema_ast)


def get_schema_for_macro_definition(schema):
    """Return a schema with macro definition directives added in.

    Preconditions:
    1. All compiler-supported and GraphQL-default directives have their default behavior.

    This returned schema can be used to validate macro definitions, and support GraphQL
    macro editors, enabling them to autocomplete on the @macro_edge_definition and
    @macro_edge_target directives. Some directives that are disallowed in macro edge definitions,
    like @output and @output_source, will be removed from the directives list.

    Args:
        schema: GraphQLSchema over which we want to write macros

    Returns:
        GraphQLSchema usable for writing macros. Modifying this schema is undefined behavior.

    Raises:
        AssertionError, if the schema contains directive names that are non-default.
    """
    return get_schema_for_macro_edge_definitions(schema)


def perform_macro_expansion(macro_registry, schema_with_macros, graphql_with_macro, graphql_args):
    """Return a new GraphQL query string and args, after expanding any encountered macros.

    Args:
        macro_registry: MacroRegistry, the registry of macro descriptors used for expansion
        schema_with_macros: A schema obtained by running get_schema_with_macros(macro_registry)
        graphql_with_macro: string, GraphQL query that potentially requires macro expansion
        graphql_args: dict mapping strings to any type, containing the arguments for the query

    Returns:
        tuple (new_graphql_string, new_graphql_args) containing the rewritten GraphQL query and
        its new args, after macro expansion. If the input GraphQL query contained no macros,
        the returned values are guaranteed to be identical to the input query and args.
    """
    query_ast = safe_parse_graphql(graphql_with_macro)
    validation_errors = validate_schema_and_query_ast(schema_with_macros, query_ast)
    if validation_errors:
        raise GraphQLValidationError(
            "The provided GraphQL input does not validate: {} {}".format(
                graphql_with_macro, validation_errors
            )
        )

    new_query_ast, new_args = expand_macros_in_query_ast(macro_registry, query_ast, graphql_args)
    new_graphql_string = print_ast(new_query_ast)

    return new_graphql_string, new_args
