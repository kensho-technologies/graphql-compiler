# Copyright 2018-present Kensho Technologies, LLC.
import datetime
import os
import random
import sys

from ... import __version__
from .animals import get_animal_generation_commands
from .species import get_species_generation_commands


def main():
    """Print a list of SQL commands to generate the testing database."""
    random.seed(0)

    module_path = os.path.relpath(__file__)
    current_datetime = datetime.datetime.now().isoformat()

    log_message = ('# Auto-generated output from `{path}`.\n'
                   '# Do not edit directly!\n'
                   '# Generated on {datetime} from compiler version {version}.\n\n')

    sys.stdout.write(
        log_message.format(path=module_path, datetime=current_datetime, version=__version__))

    sql_command_generators = [
        get_species_generation_commands,
        get_animal_generation_commands,
    ]
    for sql_command_generator in sql_command_generators:
        sql_command_list = sql_command_generator()
        sys.stdout.write('\n'.join(sql_command_list))
        sys.stdout.write('\n')


if __name__ == '__main__':
    main()
