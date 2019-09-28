OrientDB
========

.. TODO: Give more insight into how schema generation works for OrientDB, (i.e. how do vertex, and
         edge classes get mapped to OrientDB constructs).

The best way to integrate the compiler with OrientDB is by compiling to MATCH, our name for the
SQL dialect that OrientDB uses. Since the compiler was originally built to target an OrientDB
database backend, all query directives are supported when compiling to MATCH. Additionally, since
OrientDB is a graph database, generating a GraphQL schema from an OrientDB database requires
minimal configuration.

.. important:: We currently support OrientDB version 2.2.28+.

End-to-End Example
------------------

.. NOTE: See https://stackoverflow.com/questions/15394347/adding-a-cross-reference-to-a-subheading-or-anchor-in-another-page
         for more info on how cross references to other pages are added.

See :ref:`getting-started` for an end-to-end OrientDB example.
