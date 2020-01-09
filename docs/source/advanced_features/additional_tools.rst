Additional Tools
================

GraphQL Query Pretty-Printer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To pretty-print GraphQL queries, use the included pretty-printer:

::

    python -m graphql_compiler.tool <input_file.graphql >output_file.graphql

It's modeled after Python's :code:`json.tool`, reading from stdin and
writing to stdout.
