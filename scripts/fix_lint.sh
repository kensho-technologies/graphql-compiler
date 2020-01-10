#!/usr/bin/env bash
# Copyright 2020-present Kensho Technologies, LLC.

# Assert script is running inside pipenv shell
if [[ "$VIRTUAL_ENV" == "" ]]
then
    echo "Please run pipenv shell first"
    exit 1
fi

# Exit non-zero on errors, undefined variables, and errors in pipelines.
set -euo pipefail

# Ensure that the "**" glob operator is applied recursively.
# Make globs that do not match return null values.
shopt -s globstar nullglob

# Make sure the current working directory for this script is the root directory.
cd "$(git -C "$(dirname "${0}")" rev-parse --show-toplevel )"

# Print each command
set -x

black .
isort --recursive .
