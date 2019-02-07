#!/usr/bin/env bash
# Copyright 2018-present Kensho Technologies, LLC.

# Fail on first error, on undefined variables, and on errors in a pipeline.
set -euo pipefail

# Enable recursive globbing, and make globs that do not match return null values.
shopt -s globstar nullglob

# Make sure the current working directory for this script is the root directory.
cd "$(git -C "$(dirname "${0}")" rev-parse --show-toplevel )"

current_branch=$(git rev-parse --abbrev-ref HEAD)
if [[ "$current_branch" != 'master' ]]; then
    echo "Cannot make a release from a branch that is not master. Current branch: $current_branch"
    exit 1
fi

# Clean up old release artifacts. Ignore errors since these directories might not exist.
rm -r build/ dist/ || true

# Build the source distribution.
python setup.py sdist

# Build the binary distribution.
python setup.py bdist_wheel --universal

# Upload the new release.
twine upload dist/*

# Clean up release artifacts, so they stop showing up in searches.
rm -r build/ dist/ || true
