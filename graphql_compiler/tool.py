#!/usr/bin/env python
# Copyright 2017-present Kensho Technologies, LLC.
"""Utility modeled after json.tool, pretty-prints GraphQL read from stdin and outputs to stdout.

Used as: python -m graphql_compiler.tool
"""
import sys

from . import pretty_print_graphql


def main() -> None:
    """Read a GraphQL query from standard input, and output it pretty-printed to standard output."""
    query = " ".join(sys.stdin.readlines())

    sys.stdout.write(pretty_print_graphql(query))


if __name__ == "__main__":
    main()
