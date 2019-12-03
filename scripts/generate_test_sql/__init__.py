# Copyright 2018-present Kensho Technologies, LLC.
import codecs
import datetime
from os import path
import random
import re
import sys

from .animals import get_animal_generation_commands
from .events import get_event_generation_commands
from .species import get_species_generation_commands


#  https://packaging.python.org/guides/single-sourcing-package-version/
#  #single-sourcing-the-version


def read_file(filename):
    """Read and return text from the file specified by `filename`, in the project root directory."""
    # intentionally *not* adding an encoding option to open
    # see here:
    # https://github.com/pypa/virtualenv/issues/201#issuecomment-3145690
    top_level_directory = path.dirname(path.dirname(path.dirname(path.abspath(__file__))))
    with codecs.open(path.join(top_level_directory, "graphql_compiler", filename), "r") as f:
        return f.read()


def find_version():
    """Return current version of package."""
    version_file = read_file("__init__.py")
    version_match = re.search(r'^__version__ = ["\']([^"\']*)["\']', version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


def main():
    """Print a list of SQL commands to generate the testing database."""
    random.seed(0)

    module_path = path.relpath(__file__)
    current_datetime = datetime.datetime.now().isoformat()

    log_message = (
        "# Auto-generated output from `{path}`.\n"
        "# Do not edit directly!\n"
        "# Generated on {datetime} from compiler version {version}.\n\n"
    )

    sys.stdout.write(
        log_message.format(path=module_path, datetime=current_datetime, version=find_version())
    )

    sql_command_generators = [
        get_event_generation_commands,
        get_species_generation_commands,
        get_animal_generation_commands,
    ]
    for sql_command_generator in sql_command_generators:
        sql_command_list = sql_command_generator()
        sys.stdout.write("\n".join(sql_command_list))
        sys.stdout.write("\n")


if __name__ == "__main__":
    main()
