#!/usr/bin/env bash
# Copyright 2018-present Kensho Technologies, LLC.

# Fail on first error, on undefined variables, and on errors in a pipeline.
set -euo pipefail

# Enable recursive globbing, and make globs that do not match return null values.
shopt -s globstar nullglob

# Make sure the current working directory is the root directory.
if [ ! -f "./requirements.txt" ] || [ ! -f "./CHANGELOG.md" ]; then
    echo -e 'Please run this script from the root directory of the repo:\n'
    echo -e '    ./scripts/copyright_line_check.sh\n'
    exit 1
fi

ensure_file_has_copyright_line() {
    filename="$1"

    lines_to_examine=2
    copyright_regex='# Copyright 2\d\d\d\-present Kensho Technologies, LLC\.'

    set +e
    head -"$lines_to_examine" "$filename" | grep -e "$copyright_regex" >/dev/null
    result="$?"
    set -e

    if [[ "$result" != "0" ]]; then
        # The check will have to be more sophisticated if we
        echo "The file $filename appears to be missing a copyright line."
        echo 'Please add the following at the top of the file (right after the #! line in scripts):'
        echo -e "\n    # Copyright $(date +%Y)-present Kensho Technologies, LLC.\n"
    fi
}

ensure_file_has_copyright_line './setup.py'
for filename in ./graphql_compiler/**/*.py; do
    ensure_file_has_copyright_line "$filename"
done

