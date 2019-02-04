#!/usr/bin/env bash

# Treat undefined variables and non-zero exits in pipes as errors.
set -uo pipefail

# Ensure that the "**" glob operator is applied recursively.
shopt -s globstar

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

cd "$(git rev-parse --show-toplevel)"

# Get all python files or directories that need to be linted.
lintable_locations="graphql_compiler/"
# pylint doesn't support linting directories that aren't packages:
# https://github.com/PyCQA/pylint/issues/352
# Use **/*.py to supply all python files for individual linting.
pylint_lintable_locations="graphql_compiler/**/*.py"
if [ "$diff_only" -eq 1 ] ; then
    # Quotes don't need to be escaped because they nest with $( ).
    lintable_locations="$(git diff --name-only master... | grep "*\.py$")"
    pylint_lintable_locations="$lintable_locations"
fi

# Continue on error to allow ignoring certain linters.
# Errors are manually aggregated at the end.
set +e

echo -e '*** Running isort... ***\n'
isort --check-only --recursive graphql_compiler/
isort_exit_code=$?
echo -e "\n*** End of isort run; exit: $isort_exit_code ***\n"

echo -e '*** Running flake8... ***\n'
flake8 graphql_compiler/
flake_exit_code=$?
echo -e "\n*** End of flake8 run, exit: $flake_exit_code ***\n"

echo -e '\n*** Running pydocstyle... ***\n'
pydocstyle graphql_compiler/
pydocstyle_exit_code=$?
echo -e "\n*** End of pydocstyle run, exit: $pydocstyle_exit_code ***\n"

echo -e '\n*** Running pylint... ***\n'
pylint graphql_compiler/
pylint_exit_code=$?
echo -e "\n*** End of pylint run, exit: $pylint_exit_code ***\n"

echo -e '\n*** Running bandit... ***\n'
bandit -r graphql_compiler/
bandit_exit_code=$?
echo -e "\n*** End of bandit run, exit: $bandit_exit_code ***\n"

if [[ ("$flake_exit_code" != "0") ||
      ("$pydocstyle_exit_code" != "0") ||
      ("$pylint_exit_code" != "0") ||
      ("$bandit_exit_code" != "0") ||
      ("$isort_exit_code" != "0") ]]; then
    exit 1
fi
