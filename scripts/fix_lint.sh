#!/usr/bin/env bash
# Copyright 2018-present Kensho Technologies, LLC.

# Make sure the current working directory for this script is the root directory.
cd "$(git -C "$(dirname "${0}")" rev-parse --show-toplevel )"

# Print each command
set -o xtrace

black .
isort --recursive .
