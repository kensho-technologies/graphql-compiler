#!/usr/bin/env bash
# Copyright 2019-present Kensho Technologies, LLC.

# Fail on first error, on undefined variables, and on errors in a pipeline.
set -euo pipefail

# Ensure that the "**" glob operator is applied recursively.
# Make globs that do not match return null values.
shopt -s globstar nullglob

# Make sure the current working directory for this script is the root directory.
cd "$(git -C "$(dirname "${0}")" rev-parse --show-toplevel )"

# Make sure that the system has both a Python 2 and a Python 3 available.
# Since we've set -e above, if "grep" doesn't find anything, the script will break.
python2 --version 2>&1 | grep 'Python 2'  # N.B.: Python 2 prints version info to stderr.
python3 --version | grep 'Python 3'

# Delete the existing lockfiles.
echo 'Deleting old lockfiles...'
rm Pipfile.lock Pipfile.py2.lock || true  # Don't error if the lockfiles weren't there to start.

echo 'Creating Python 2 lockfile...'
pipenv --rm || true  # Don't error if there is no virtualenv yet.
pipenv lock --python="$(which python2)" --dev
mv Pipfile.lock Pipfile.py2.lock

echo 'Creating Python 3 lockfile...'
pipenv --rm
pipenv lock --python="$(which python3)" --dev

echo 'All done!'
