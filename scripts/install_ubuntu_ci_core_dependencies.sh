#!/usr/bin/env bash
# Copyright 2020-present Kensho Technologies, LLC.

# Treat undefined variables and non-zero exits in pipes as errors.
set -uo pipefail

# Ensure that the "**" glob operator is applied recursively.
# Make globs that do not match return null values.
shopt -s globstar nullglob

# Break on first error.
set -e

# This script is intended for use in the CI environment.
# If it happens to work outside of CI as well, that is a pleasant but non-guaranteed side effect.
#
# Install all the binary dependencies needed on an Ubuntu system.
bash -c "wget -qO- https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -"
sudo add-apt-repository "$(wget -qO- https://packages.microsoft.com/config/ubuntu/"$(lsb_release -r -s)"/prod.list)"
sudo apt-get update
sudo apt-get install unixodbc-dev python-mysqldb libmysqlclient-dev
ACCEPT_EULA=Y sudo apt-get install msodbcsql17

# Ensure pip, setuptools, and pipenv are latest available versions.
python -m pip install --upgrade pip
python -m pip install --upgrade setuptools pipenv
