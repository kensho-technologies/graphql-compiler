#!/usr/bin/env bash
# Copyright 2019-present Kensho Technologies, LLC.

# Treat undefined variables and non-zero exits in pipes as errors.
set -uo pipefail

# Ensure that the "**" glob operator is applied recursively.
# Make globs that do not match return null values.
shopt -s globstar nullglob

# Make sure the current working directory for this script is the root directory.
cd "$(git -C "$(dirname "${0}")" rev-parse --show-toplevel )"

is_py2="$(python --version 2>&1 | grep 'Python 2')"  # N.B.: Python 2 prints version info to stderr.

if [[ "$is_py2" != '' ]]; then
    echo "Found $is_py2, switching lockfiles to use the one compatible with Python 2."
    mv Pipfile.lock Pipfile.py3.lock
    mv Pipfile.py2.lock Pipfile.lock
else
    echo "Python was $(python --version 2>&1), sticking with Python 3 lockfile."
fi
