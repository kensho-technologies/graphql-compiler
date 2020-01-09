#!/usr/bin/env bash
# Copyright 2018-present Kensho Technologies, LLC.

# Assert script is running inside pipenv shell
if [[ "$VIRTUAL_ENV" == "" ]]
then
    echo "Please run pipenv shell first"
    exit 1
fi

# Make sure the current working directory for this script is the root directory.
cd "$(git -C "$(dirname "${0}")" rev-parse --show-toplevel )"

# Print each command
set -o xtrace

black .
isort --recursive .
