#!/usr/bin/env bash
# Copyright 2018-present Kensho Technologies, LLC.

# Fail on first error, on undefined variables, and on errors in a pipeline.
set -euo pipefail

# Enable recursive globbing, and make globs that do not match return null values.
shopt -s globstar nullglob

# Make sure the current working directory for this script is the root directory.
cd "$(git rev-parse --show-toplevel)"

# Clean up old release artifacts. Ignore errors since these directories might not exist.
rm -r build/ dist/ || true

# Build the source distribution.
python setup.py sdist

# Build the binary distribution.
python setup.py bdist_wheel --universal

# Upload the new release.
twine upload dist/*
