#!/usr/bin/env bash
# Copyright 2019-present Kensho Technologies, LLC.

# Fail on first error, on undefined variables, and on errors in a pipeline.
set -euo pipefail

# Ensure that the "**" glob operator is applied recursively.
# Make globs that do not match return null values.
shopt -s globstar nullglob

# Make sure the current working directory for this script is the root directory.
cd "$(git -C "$(dirname "${0}")" rev-parse --show-toplevel )"

# Make sure that the system has Python 3 available as "python".
# Since we've set -e above, if "grep" doesn't find anything, the script will break.
python --version | grep 'Python 3'

# Delete the existing lockfile.
echo 'Deleting old lockfile...'
rm Pipfile.lock || true  # Don't error if the lockfile wasn't there to start.

echo 'Creating Python 3 lockfile...'
pipenv --rm
pipenv lock --python="$(which python)" --dev

echo 'All done!'
