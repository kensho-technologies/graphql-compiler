#!/usr/bin/env bash
# Copyright 2018-present Kensho Technologies, LLC.

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
# pylint doesn't support linting directories that aren't packages:
# https://github.com/PyCQA/pylint/issues/352
# Use **/*.py to supply all python files for individual linting.
pylint_lintable_locations="graphql_compiler/**/*.py"
if [ "$diff_only" -eq 1 ] ; then
    # Quotes don't need to be escaped because they nest with $( ).
    lintable_locations="$(git diff --name-only master... | grep "\.*\.py$")"
    pylint_lintable_locations="$lintable_locations"
fi

# Continue on error to allow ignoring certain linters.
# Errors are manually aggregated at the end.
set +e

echo -e '*** Running isort... ***\n'
isort --check-only --settings-path=setup.cfg --diff --recursive graphql_compiler/
isort_exit_code=$?
echo -e "\n*** End of isort run; exit: $isort_exit_code ***\n"

echo -e '*** Running flake8... ***\n'
flake8 --config=setup.cfg $lintable_locations
flake_exit_code=$?
echo -e "\n*** End of flake8 run, exit: $flake_exit_code ***\n"

echo -e '\n*** Running pydocstyle... ***\n'
pydocstyle --config=.pydocstyle $lintable_locations
pydocstyle_exit_code=$?
echo -e "\n*** End of pydocstyle run, exit: $pydocstyle_exit_code ***\n"

echo -e '\n*** Running pydocstyle on tests... ***\n'
pydocstyle --config=.pydocstyle_test $lintable_locations
pydocstyle_test_exit_code=$?
echo -e "\n*** End of pydocstyle on tests run, exit: $pydocstyle_test_exit_code ***\n"

echo -e '\n*** Running pylint... ***\n'
pylint $pylint_lintable_locations
pylint_exit_code=$?
echo -e "\n*** End of pylint run, exit: $pylint_exit_code ***\n"

echo -e '\n*** Running bandit... ***\n'
bandit -r $lintable_locations
bandit_exit_code=$?
echo -e "\n*** End of bandit run, exit: $bandit_exit_code ***\n"

if [[ ("$flake_exit_code" != "0") ||
      ("$pydocstyle_exit_code" != "0") ||
      ("$pydocstyle_test_exit_code" != "0") ||
      ("$pylint_exit_code" != "0") ||
      ("$bandit_exit_code" != "0") ||
      ("$isort_exit_code" != "0") ]]; then
    echo -e "\n*** Lint failed. ***\n"
    echo -e "isort exit: $isort_exit_code"
    echo -e "flake8 exit: $flake_exit_code"
    echo -e "pydocstyle exit: $pydocstyle_exit_code"
    echo -e "pydocstyle on tests exit: $pydocstyle_test_exit_code"
    echo -e "pylint exit: $pylint_exit_code"
    echo -e "bandit exit: $bandit_exit_code"
    exit 1
fi

echo -e "\n*** Lint successful. ***\n"
