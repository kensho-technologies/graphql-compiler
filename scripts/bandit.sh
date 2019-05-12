#!/usr/bin/env bash
# Copyright 2019-present Kensho Technologies, LLC.

# Treat undefined variables and non-zero exits in pipes as errors.
set -uo pipefail

# Ensure that the "**" glob operator is applied recursively.
# Make globs that do not match return null values.
shopt -s globstar nullglob

# Break on first error.
set -e

# Parse input arguments.
diff_only=0
for i in "$@"; do
    case $i in
        --diff )
            diff_only=1
            shift;;

        *)
            echo "Unknown option: $i";
            exit 1;;
    esac
done

# Make sure the current working directory for this script is the root directory.
cd "$(git -C "$(dirname "${0}")" rev-parse --show-toplevel )"

# Get all python files or directories that need to be linted.
lintable_locations="graphql_compiler/"

# Get all python files or directories that need to be linted.
lintable_locations="graphql_compiler/"

echo -e '\n*** Running bandit... ***\n'
bandit -r $lintable_locations
echo -e "\n*** Bandit finished successfully. ***\n"

