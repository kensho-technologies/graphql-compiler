Macro System
============

The macro system allows users to reshape how they *perceive* their data, without requiring changes
to the underlying database structures themselves.

In many real-life situations, the database schema does not fit the user's mental model of the data.
There are many causes of this, the most common one being database normalization.
The representation of the data that is convenient for storage within a database is rarely
the representation that makes for easy querying. As a result, users' queries frequently
include complex and repetitive query structures that work around the database's chosen data model.

The compiler's macro system empowers users *reshaping* their data's structure to fit
their mental model, minimizing query complexity and repetitiveness without requiring changes
to the shape of the data in the underlying data systems. The compiler achieves this by allowing
users to define **macros** -- type-safe rules for programmatic query rewriting
that transform user-provided queries on the *desired* data model into
queries on the *actual* data model in the underlying data systems.

When macros are defined, the compiler loads them into a :ref:`macro registry <macro_registry>` -- a
data structure that tracks all currently available macros, the resulting GraphQL schema
(accounting for macros), and any additional metadata needed by the compiler.
The compiler then leverages this registry to expand queries that rely on macros,
rewriting them into equivalent queries that do not contain any macros and therefore
reflect the actual underlying data model.

This makes macros somewhat similar to SQL's idea of non-materialized views,
though there are some key differences:

- SQL views require database access and special permissions; databases are
  completely oblivious to the use of macros since by the time the database gets the query,
  all macro uses have been already expanded.

- Macros can be stored and expanded client-side, so different users that query the same system may
  define their own personal macros which are not shared with other users or the server that executes
  the users' GraphQL queries. This is generally not achievable with SQL.

- Since macro expansion does not interact in any way with the underlying data system, it works
  seamlessly with all databases and even on schemas stitched together from multiple databases.
  In contrast, not all databases support SQL-like :code:`VIEW` functionality.

Currently, the compiler supports one type of macro: :ref:`macro edges <macro_edges>`, which allow
the creation of "virtual" edges computed from existing ones.
More types of macros are coming in the future.

.. _macro_registry:

Macro registry
--------------

The macro registry is where the definitions of all currently defined macros are stored,
together with the resulting GraphQL schema they form, as well as any associated metadata
that the compiler's macro system may need in order to expand any macros encountered in a query.

To create a macro registry object for a given GraphQL schema, use the :code:`create_macro_registry`
function:

.. code:: python

    from graphql_compiler.macros import create_macro_registry

    macro_registry = create_macro_registry(your_graphql_schema_object)

To retrieve the GraphQL schema object with all its macro-based additions, use
the :code:`get_schema_with_macros` function:

.. code:: python

    from graphql_compiler.macros import get_schema_with_macros

    graphql_schema = get_schema_with_macros(macro_registry)

Schema for defining macros
--------------------------

Macro definitions rely on additional directives that are not normally defined in the schema
the GraphQL compiler uses for querying. We intentionally do not include these directives in
the schema used for querying, since defining macros and writing queries are different modes
of use of the compiler, and we believe that controlling which sets of directives
are available in which mode will minimize the potential for user confusion.

The :code:`get_schema_for_macro_definition()` function is able to transform a querying schema
into one that is suitable for defining macros. Getting such a schema may be useful, for example,
when setting up a GraphQL editor (such as GraphiQL) to create and edit macros.

.. _macro_edges:

Macro edges
-----------

Macro edges allow users to define new edges that become part of the GraphQL schema, using existing
edges as building blocks. They allow users to define shorthand for common querying operations,
encapsulating uses of existing query functionality (e.g., tags, filters, recursion,
type coercions, etc.) into a virtual edge with a user-specified name that exists only on a specific
GraphQL type (and all its subtypes). Both macro edge definitions and their uses are
fully type-checked, ensuring the soundness of both the macro definition and any queries that use it.

Overview and use of macro edges
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let us explain the idea of macro edges through a simple example.

Consider the following query, which returns the list of grandchildren of a given animal:

.. code ::

    {
        Animal {
            name @filter(op_name: "=", value: ["$animal_name"])
            out_Animal_ParentOf {
                out_Animal_ParentOf {
                    name @output(out_name: "grandchild_name")
                }
            }
        }
    }

If operations on animals' grandchildren are common in our use case, we may wish that
an edge like :code:`out_Animal_GrandparentOf` had existed and saved us some repetitive typing.

One of our options is to materialize such an edge in the underlying database itself.
However, this causes denormalization of the database -- there are now two places where
an animal's grandchildren are written down -- requiring additional storage space,
and introducing potential for user confusion and data inconsistency between the two representations.

Another option is to introduce a non-materialized view within the database that *makes it appear*
that such an edge exists, and query this view via the GraphQL compiler. While this avoids some
of the drawbacks of the previous approach, not all databases support non-materialized views.
Also, querying users are not always able to add views to the database, and may require additional
permissions on the database system.

Macro edges give us the opportunity to define a new :code:`out_Animal_GrandparentOf` edge without
involving the underlying database systems at all. We simply state that such an edge
is constructed by composing two :code:`out_Animal_ParentOf` edges together:

.. code:: python

    from graphql_compiler.macros import register_macro_edge

    macro_edge_definition = '''{
        Animal @macro_edge_definition(name: "out_Animal_GrandparentOf") {
            out_Animal_ParentOf {
                out_Animal_ParentOf @macro_edge_target {
                    uuid
                }
            }
        }
    }'''
    macro_edge_args = {}

    register_macro_edge(your_macro_registry_object, macro_edge_definition, macro_edge_args)

Let's dig into the GraphQL macro edge definition one step at a time:

- We know that the new macro edge is being defined on the :code:`Animal` GraphQL type, since that
  is the type where the definition begins.

- The :code:`@macro_edge_definition` directive specifies the name of the new macro edge.

- The newly-defined :code:`out_Animal_GrandparentOf` edge connects :code:`Animal` vertices
  to the vertices reachable after exactly two traversals along :code:`out_Animal_ParentOf` edges;
  this is what the :code:`@macro_edge_target` directive signifies.

- As the :code:`out_Animal_ParentOf` field containing the :code:`@macro_edge_target` directive
  is of type :code:`[Animal]` (we know this from our schema), the compiler will automatically infer
  that the :code:`out_Animal_GrandparentOf` macro edge also points to vertices
  of type :code:`Animal`.

- The :code:`uuid` within the inner :code:`out_Animal_ParentOf` scope is a "pro-forma" field -- it
  is there simply to satisfy the GraphQL parser, since per the GraphQL specification, each pair of
  curly braces must reference at least one field. The named field has no meaning in this definition,
  and the user may choose to use any field that exists within that pair of curly braces.
  The preferred convention for pro-forma fields is to use whichever field represents
  the primary key of the given type in the underlying database.

- This macro edge does not take arguments, so we set the :code:`macro_edge_args` value to an empty
  dictionary. We will cover macro edges with arguments later.

Having defined this macro edge, we are now able to rewrite our original query into a simpler
yet equivalent form:

.. code::

    {
        Animal {
            name @filter(op_name: "=", value: ["$animal_name"])
            out_Animal_GrandparentOf {
                name @output(out_name: "grandchild_name")
            }
        }
    }

We can now observe the process of macro expansion in action:

.. code:: python

    from graphql_compiler.macros import get_schema_with_macros, perform_macro_expansion

    query = '''{
        Animal {
            name @filter(op_name: "=", value: ["$animal_name"])
            out_Animal_GrandparentOf {
                name @output(out_name: "grandchild_name")
            }
        }
    }'''
    args = {
        'animal_name': 'Hedwig',
    }

    schema_with_macros = get_schema_with_macros(macro_registry)
    new_query, new_args = perform_macro_expansion(macro_registry, schema_with_macros, query, args)

    print(new_query)
    # Prints out the following query:
    # {
    #     Animal {
    #         name @filter(op_name: "=", value: ["$animal_name"])
    #         out_Animal_ParentOf {
    #             out_Animal_ParentOf {
    #                 name @output(out_name: "grandchild_name")
    #             }
    #         }
    #     }
    # }

    print(new_args)
    # Prints out the following arguments:
    # {'animal_name': 'Hedwig'}

Advanced macro edges use cases
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When defining macro edges, one may freely use other compiler query functionality,
such as :code:`@recurse`, :code:`@filter`, :code:`@tag`, and so on. Here is a more complex
macro edge definition that relies on such more advanced features to define an edge
that connects :code:`Animal` vertices to their siblings who are both older and have a
higher net worth:

.. code:: python

    from graphql_compiler.macros import register_macro_edge

    macro_edge_definition = '''
    {
        Animal @macro_edge_definition(name: "out_Animal_RicherOlderSiblings") {
            net_worth @tag(tag_name: "self_net_worth")
            out_Animal_BornAt {
                event_date @tag(tag_name: "self_birthday")
            }
            in_Animal_ParentOf {
                out_Animal_ParentOf @macro_edge_target {
                    net_worth @filter(op_name: ">", value: ["%self_net_worth"])
                    out_Animal_BornAt {
                        event_date @filter(op_name: "<", value: ["%self_birthday"])
                    }
                }
            }
        }
    }'''
    macro_edge_args = {}

    register_macro_edge(your_macro_registry_object, macro_edge_definition, macro_edge_args)

Similarly, macro edge definitions are also able to use runtime parameters in
their :code:`@filter` directives, by simply including the runtime parameters needed by
the macro edge in the call to :code:`register_macro_edge()`. The following example defines a
macro edge connecting :code:`Animal` vertices to their grandchildren that go by the name of "Nate".

.. code:: python

    macro_edge_definition = '''
    {
        Animal @macro_edge_definition(name: "out_Animal_GrandchildrenCalledNate") {
            out_Animal_ParentOf {
                out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["$nate_name"])
                                    @macro_edge_target {
                    uuid
                }
            }
        }
    }'''
    macro_edge_args = {
        'nate_name': 'Nate',
    }

    register_macro_edge(your_macro_registry_object, macro_edge_definition, macro_edge_args)

When a GraphQL query uses this macro edge, the :code:`perform_macro_expansion()` function will
automatically ensure that the macro edge's arguments become part of the expanded query's arguments:

.. code:: python

    query = '''{
        Animal {
            name @output(out_name: "animal_name")
            out_Animal_GrandchildrenCalledNate {
                uuid @output(out_name: "grandchild_id")
            }
        }
    }'''
    args = {}
    schema_with_macros = get_schema_with_macros(macro_registry)
    expanded_query, new_args = perform_macro_expansion(
          macro_registry, schema_with_macros, query, args)

    print(expanded_query)
    # Prints out the following query:
    # {
    #     Animal {
    #         name @output(out_name: "animal_name")
    #         out_Animal_ParentOf {
    #             out_Animal_ParentOf @filter(op_name: "name_or_alias", value: ["$nate_name"]) {
    #                 uuid @output(out_name: "grandchild_id")
    #             }
    #         }
    #     }
    # }

    print(new_args)
    # Prints out the following arguments:
    # {'nate_name': 'Nate'}

Constraints and rules for macro edge definitions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- Macro edge definitions cannot use other macros as part of their definition.
- A macro definition contains exactly one :code:`@macro_edge_definition` and
  one :code:`@macro_edge_target` directive. These directives can only be used
  within macro edge definitions.
- The :code:`@macro_edge_target` cannot be at or within a scope
  marked :code:`@fold` or :code:`@optional`.
- The scope marked :code:`@macro_edge_target` cannot immediately contain a type coercion.
  Instead, place the :code:`@macro_edge_target` directive at the type coercion itself instead of
  on its enclosing scope.
- Macros edge definitions cannot contain uses of :code:`@output` or :code:`@output_source`.


Constraints and rules for macro edge usage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- The :code:`@optional` and :code:`@recurse` directives cannot be used on macro edges.
- During the process of macro edge expansion, any directives applied on the vertex field belonging
  to the macro edge are applied to the vertex field marked with :code:`@macro_edge_target` in the
  macro edge's definition.

In the future, we hope to add support for using :code:`@optional` on macro edges. We have opened
a `GitHub issue <https://github.com/kensho-technologies/graphql-compiler/issues/586>`_ to track
this effort, and we welcome contributions!
