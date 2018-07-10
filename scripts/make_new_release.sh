#!/usr/bin/env bash
# Copyright 2018-present Kensho Technologies, LLC.

# Fail on first error, on undefined variables, and on errors in a pipeline.
set -euo pipefail

# Enable recursive globbing, and make globs that do not match return null values.
shopt -s globstar nullglob

# Make sure the current working directory is the root directory.
if [ ! -f "./requirements.txt" ] || [ ! -f "./CHANGELOG.md" ]; then
    echo -e 'Please run this script from the root directory of the repo:\n'
    echo -e '    ./scripts/make_new_release.sh\n'
    exit 1
fi

# Clean up old release artifacts.
rm -r build/ dist/

# Build the source distribution.
python setup.py sdist

# Build the binary distribution.
python setup.py bdist_wheel --universal

# Upload the new release.
twine upload dist/*
