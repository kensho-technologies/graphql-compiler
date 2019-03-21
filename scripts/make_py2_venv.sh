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

# Switch the lockfiles so the Python 2 becomes the lockfile that pipenv will find.
# N.B.: The "sync" is necessary here since some file systems (looking at you, OSX)
#       will have issues executing the second move after the first one leaves dirty state around.
mv Pipfile.lock Pipfile.py3.lock
sync
mv Pipfile.py2.lock Pipfile.lock

cleaned_up=0
function cleanup {
    # Clean up after ourselves, but exactly once.
    if [[ "$cleaned_up" == '0' ]]; then
        cleaned_up=1
        echo "Cleaning up..."

        # Switch the lockfiles back to their original configuration.
        # N.B.: The "sync" is necessary here for the same reason as above.
        mv Pipfile.lock Pipfile.py2.lock
        sync
        mv Pipfile.py3.lock Pipfile.lock
    fi
}

# Make sure we trigger cleanup, no matter what happens next.
trap cleanup ERR
trap cleanup 0

# Wipe out and recreate the virtualenv using the Python 2 lockfile.
pipenv --rm 2>/dev/null || true  # Don't error if there is no virtualenv yet.
pipenv install --python "$(which python2)" --dev
