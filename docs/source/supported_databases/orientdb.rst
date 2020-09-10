OrientDB
========

.. TODO: Give more insight into how schema generation works for OrientDB, (i.e. how do vertex, and
         edge classes get mapped to OrientDB constructs).

The best way to integrate the compiler with OrientDB is by compiling to MATCH, our name for the
SQL dialect that OrientDB uses. All query directives are supported when compiling to MATCH. Additionally, since
OrientDB is a graph database, generating a GraphQL schema from an OrientDB database requires
minimal configuration.

.. important:: We currently support OrientDB version 2.2.28+.

End-to-End Example
------------------

.. include:: ../../../README.rst
   :start-after: end-to-end-orientdb-example-start
   :end-before: end-to-end-orientdb-example-end

Performance Penalties
---------------------

.. _compound_optional_performance_penalty:

Compound :code:`optional` Performance Penalty
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When compiling to MATCH, including an optional statement in GraphQL has no performance issues on
its own, but if you continue expanding vertex fields within an optional scope, there may be
significant performance implications.

Going forward, we will refer to two different kinds of :code:`@optional` directives.

-  A *"simple"* optional is a vertex with an :code:`@optional` directive
   that does not expand any vertex fields within it. For example:

   .. code::

       {
           Animal {
               name @output(out_name: "name")
               in_Animal_ParentOf @optional {
                   name @output(out_name: "parent_name")
               }
           }
       }

   OrientDB :code:`MATCH` currently allows the last step in any traversal to
   be optional. Therefore, the equivalent :code:`MATCH` traversal for the
   above :code:`GraphQL` is as follows:

   ::

       SELECT
       Animal___1.name as `name`,
       Animal__in_Animal_ParentOf___1.name as `parent_name`
       FROM (
       MATCH {
           class: Animal,
           as: Animal___1
       }.in('Animal_ParentOf') {
           as: Animal__in_Animal_ParentOf___1
       }
       RETURN $matches
       )

-  A *"compound"* optional is a vertex with an :code:`@optional` directive
   which does expand vertex fields within it. For example:

   .. code::

       {
           Animal {
               name @output(out_name: "name")
               in_Animal_ParentOf @optional {
                   name @output(out_name: "parent_name")
                   in_Animal_ParentOf {
                       name @output(out_name: "grandparent_name")
                   }
               }
           }
       }

   Currently, this cannot represented by a simple :code:`MATCH` query.
   Specifically, the following is *NOT* a valid :code:`MATCH` statement,
   because the optional traversal follows another edge:

   ::

       -- NOT A VALID QUERY
       SELECT
       Animal___1.name as `name`,
       Animal__in_Animal_ParentOf___1.name as `parent_name`
       FROM (
       MATCH {
           class: Animal,
           as: Animal___1
       }.in('Animal_ParentOf') {
           optional: true,
           as: Animal__in_Animal_ParentOf___1
       }.in('Animal_ParentOf') {
           as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
       }
       RETURN $matches
       )

Instead, we represent a *compound* optional by taking an union
(:code:`UNIONALL`) of two distinct :code:`MATCH` queries. For instance, the
:code:`GraphQL` query above can be represented as follows:

::

    SELECT EXPAND($final_match)
    LET
        $match1 = (
            SELECT
                Animal___1.name AS `name`
            FROM (
                MATCH {
                    class: Animal,
                    as: Animal___1,
                    where: (
                        (in_Animal_ParentOf IS null)
                        OR
                        (in_Animal_ParentOf.size() = 0)
                    ),
                }
            )
        ),
        $match2 = (
            SELECT
                Animal___1.name AS `name`,
                Animal__in_Animal_ParentOf___1.name AS `parent_name`
            FROM (
                MATCH {
                    class: Animal,
                    as: Animal___1
                }.in('Animal_ParentOf') {
                    as: Animal__in_Animal_ParentOf___1
                }.in('Animal_ParentOf') {
                    as: Animal__in_Animal_ParentOf__in_Animal_ParentOf___1
                }
            )
        ),
        $final_match = UNIONALL($match1, $match2)

In the first case where the optional edge is not followed, we have to
explicitly filter out all vertices where the edge *could have been
followed*. This is to eliminate duplicates between the two :code:`MATCH`
selections.

.. note::

    The previous example is not *exactly* how we implement *compound*
    optionals (we also have :code:`SELECT` statements within :code:`$match1` and
    :code:`$match2`), but it illustrates the the general idea.

Performance Analysis
^^^^^^^^^^^^^^^^^^^^

If we have many *compound* optionals in the given :code:`GraphQL`, the above
procedure results in the union of a large number of :code:`MATCH` queries.
Specifically, for :code:`n` compound optionals, we generate 2n different
:code:`MATCH` queries. For each of the 2n subsets :code:`S` of the :code:`n`
optional edges:

- We remove the :code:`@optional` restriction for each traversal in :code:`S`.
- For each traverse :code:`t` in the complement of :code:`S`, we entirely discard :code:`t` along
  with all the vertices and directives within it, and we add a filter on the previous traverse to
  ensure that the edge corresponding to :code:`t` does not exist.

Therefore, we get a performance penalty that grows exponentially with
the number of *compound* optional edges. This is important to keep in
mind when writing queries with many optional directives.

If some of those *compound* optionals contain :code:`@optional` vertex
fields of their own, the performance penalty grows since we have to
account for all possible subsets of :code:`@optional` statements that can be
satisfied simultaneously.
