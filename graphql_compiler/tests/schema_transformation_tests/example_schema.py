# Copyright 2019-present Kensho Technologies, LLC
from collections import OrderedDict

from graphql import parse
from graphql_compiler.schema_transformation.rename_schema import rename_schema

from ..test_helpers import SCHEMA_TEXT


basic_schema = parse(SCHEMA_TEXT)


basic_renamed_schema = rename_schema(
    basic_schema, {'Animal': 'NewAnimal', 'Entity': 'NewEntity', 'BirthEvent': 'NewBirthEvent'}
)
