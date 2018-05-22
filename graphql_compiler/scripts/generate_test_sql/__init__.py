from .animals import get_animal_generators
from .species import get_species_generators


if __name__ == '__main__':
    sql_generators = [
        get_species_generators,
        get_animal_generators,
    ]
    sql_generator_strings = []
    for generator in sql_generators:
        sql_generator_strings.extend(generator())

    print '\n'.join(sql_generator_strings)
