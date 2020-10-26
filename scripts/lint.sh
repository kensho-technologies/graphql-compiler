#!/usr/bin/env bash
# Copyright 2018-present Kensho Technologies, LLC.

# Treat undefined variables and non-zero exits in pipes as errors.
set -uo pipefail

# Ensure that the "**" glob operator is applied recursively.
# Make globs that do not match return null values.
shopt -s globstar nullglob

# Break on first error.
set -e


function get_physical_cores() {
    if [[ -f /proc/cpuinfo ]]
    then
        grep "core id" /proc/cpuinfo  |
        sort -u |
        wc -l
    else
        sysctl -n hw.physicalcpu 2>/dev/null || echo 4
    fi
}


# Parse input arguments.
diff_only=0
any_run_only_set=0
run_fast_linters=0  # copyright line check, isort, black, flake8, pydocstyle
run_pylint=0
run_mypy=0
run_bandit=0
run_sphinx_build=0
for i in "$@"; do
    case $i in
        --diff )
            diff_only=1
            shift;;

        --run-only-fast-linters )
            if [ "$any_run_only_set" -eq 1 ]; then
                echo "Multiple run-only options set, this is not supported.";
                exit 1;
            fi
            any_run_only_set=1
            run_fast_linters=1
            shift;;

        --run-only-pylint )
            if [ "$any_run_only_set" -eq 1 ]; then
                echo "Multiple run-only options set, this is not supported.";
                exit 1;
            fi
            any_run_only_set=1
            run_pylint=1
            shift;;

        --run-only-mypy )
            if [ "$any_run_only_set" -eq 1 ]; then
                echo "Multiple run-only options set, this is not supported.";
                exit 1;
            fi
            any_run_only_set=1
            run_mypy=1
            shift;;

        --run-only-bandit )
            if [ "$any_run_only_set" -eq 1 ]; then
                echo "Multiple run-only options set, this is not supported.";
                exit 1;
            fi
            any_run_only_set=1
            run_bandit=1
            shift;;

        --run-only-sphinx-build )
            if [ "$any_run_only_set" -eq 1 ]; then
                echo "Multiple run-only options set, this is not supported.";
                exit 1;
            fi
            any_run_only_set=1
            run_sphinx_build=1
            shift;;

        *)
            echo "Unknown option: $i";
            exit 1;;
    esac
done

if [ "$any_run_only_set" -eq 0 ]; then
    run_fast_linters=1
    run_pylint=1
    run_mypy=1
    run_bandit=1
    run_sphinx_build=1
fi

# Make sure the current working directory for this script is the root directory.
cd "$(git -C "$(dirname "${0}")" rev-parse --show-toplevel )"

# Assert script is running inside pipenv shell
set +u
if [[ "$VIRTUAL_ENV" == "" ]]
then
    echo "Please run pipenv shell first"
    exit 1
fi
set -u

# Get all python files or directories that need to be linted.
lintable_locations="."
# pylint doesn't support linting directories that aren't packages:
# https://github.com/PyCQA/pylint/issues/352
# Use **/*.py to supply all python files for individual linting.
pylint_lintable_locations="**/*.py *.py"
if [ "$diff_only" -eq 1 ] ; then
    # Quotes don't need to be escaped because they nest with $( ).
    lintable_locations="$(git diff --name-only main... | grep ".*\.py$")"
    pylint_lintable_locations="$lintable_locations"
fi

# Continue on error to allow ignoring certain linters.
# Errors are manually aggregated at the end.
set +e

if [ "$run_fast_linters" -eq 1 ]; then
    echo -e '*** Running copyright line check... ***\n'
    ./scripts/copyright_line_check.sh
    copyright_line_check_exit_code=$?
    echo -e "\n*** End of copyright line check run; exit: $copyright_line_check_exit_code ***\n"

    echo -e '*** Running isort... ***\n'
    isort --check-only --settings-path=setup.cfg --diff --recursive $lintable_locations
    isort_exit_code=$?
    echo -e "\n*** End of isort run; exit: $isort_exit_code ***\n"

    echo -e '*** Running black... ***\n'
    black --check --diff .
    black_exit_code=$?
    echo -e "\n*** End of black run; exit: $black_exit_code ***\n"

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
fi

if [ "$run_mypy" -eq 1 ]; then
    echo -e '*** Running mypy... ***\n'
    mypy $lintable_locations
    mypy_exit_code=$?
    echo -e "\n*** End of mypy run, exit: $mypy_exit_code ***\n"
fi

if [ "$run_pylint" -eq 1 ]; then
    physical_core_count="$(get_physical_cores)"
    echo -e "\n*** Running pylint using ${physical_core_count} cores... ***\n"
    pylint --jobs="$physical_core_count" $pylint_lintable_locations
    pylint_exit_code=$?
    echo -e "\n*** End of pylint run, exit: $pylint_exit_code ***\n"
fi

if [ "$run_bandit" -eq 1 ]; then
    echo -e '\n*** Running bandit... ***\n'
    bandit -r $lintable_locations
    bandit_exit_code=$?
    echo -e "\n*** End of bandit run, exit: $bandit_exit_code ***\n"
fi

if [ "$run_sphinx_build" -eq 1 ]; then
    echo -e '\n*** Running sphinx-build to test documentation... ***\n'
    # Arguments:
    # -n: Runs in nit-picky mode. Currently, this generates warnings for all missing references.
    # -q: Do not output anything on standard output, only write warnings and errors to standard error.
    # -W: Turn warnings into errors. This means that the build stops at the first warning and
    #     sphinx-build exits with exit status 1.
    # -b <buildername>: Selects a builder. In this case we are using the dummy builder. Note that it
    #                   doesn't produce any output but still needs a build directory parameter.
    # --keep-going: With -W option, keep going processing when getting warnings to the end of build,
    #               and sphinx-build exits with exit status 1.
    # For more info see: https://www.sphinx-doc.org/en/master/man/sphinx-build.html
    sphinx-build -n -q -W -b dummy docs/source/ docs/build/ --keep-going
    sphinx_build_exit_code=$?
    echo -e "\n*** End of sphinx-build, exit: $sphinx_build_exit_code ***\n"
fi

if  [[
        (
            ("$run_fast_linters" == 1) && (
                ("$copyright_line_check_exit_code" != "0") ||
                ("$isort_exit_code" != "0") ||
                ("$black_exit_code" != "0") ||
                ("$flake_exit_code" != "0") ||
                ("$pydocstyle_exit_code" != "0") ||
                ("$pydocstyle_test_exit_code" != "0")
            )
        ) || (
            ("$run_mypy" == 1) && ("$mypy_exit_code" != "0")
        ) || (
            ("$run_pylint" == 1) && ("$pylint_exit_code" != "0")
        ) || (
            ("$run_bandit" == 1) && ("$bandit_exit_code" != "0")
        ) || (
            ("$run_sphinx_build" == 1) && ("$sphinx_build_exit_code" != "0")
        )
    ]]; then
    echo -e "\n*** Lint failed. ***\n"

    if [ "$run_fast_linters" -eq 1 ]; then
        echo -e "copyright line check exit: $copyright_line_check_exit_code"
        echo -e "isort exit: $isort_exit_code"
        echo -e "black exit: $black_exit_code"
        echo -e "flake8 exit: $flake_exit_code"
        echo -e "pydocstyle exit: $pydocstyle_exit_code"
        echo -e "pydocstyle on tests exit: $pydocstyle_test_exit_code"
    fi
    if [ "$run_mypy" -eq 1 ]; then
        echo -e "mypy exit: $mypy_exit_code"
    fi
    if [ "$run_pylint" -eq 1 ]; then
        echo -e "pylint exit: $pylint_exit_code"
    fi
    if [ "$run_bandit" -eq 1 ]; then
        echo -e "bandit exit: $bandit_exit_code"
    fi
    if [ "$run_sphinx_build" -eq 1 ]; then
        echo -e "sphinx-build exit: $sphinx_build_exit_code"
    fi

    exit 1
fi

echo -e "\n*** Lint successful. ***\n"
