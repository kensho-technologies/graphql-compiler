from ...schema_generation.sqlalchemy.scalar_type_mapper import (
    GENERIC_SQL_CLASS_TO_GRAPHQL_TYPE, UNSUPPORTED_GENERIC_SQL_TYPES,
    UNSUPPORTED_MSSQL_TYPES, MSSQL_CLASS_TO_GRAPHQL_TYPE, SQL_CLASS_TO_GRAPHQL_TYPE
)
import sqlalchemy.types as sqlalchemy_module
import sqlalchemy.dialects.mssql as mssql_module
import unittest


def _get_class_names(classes):
    """Return the set of class names of the inputted classes."""
    return set(python_class.__name__ for python_class in classes)


class SQLAlchemyScalarMapperTests(unittest.TestCase):
    def _validate_type_mapping(
            self, sql_to_graphql_mapping, unsupported_sql_types, module, classes_to_ignore):
        """Validate that we address all SQL types in the module."""
        supported_generic_type_names = (
            set(generic_sql_class.__name__
                for generic_sql_class in sql_to_graphql_mapping.keys())
        )
        unsupported_generic_type_names = (
            set(unsupported_type.__name__ for unsupported_type in unsupported_sql_types)
        )
        self.assertEqual(supported_generic_type_names.union(unsupported_generic_type_names),
                         set(module.__all__).difference(classes_to_ignore))

    def test_address_all_generic_types(self):
        classes_to_ignore = {
            'Concatenable',
            'Indexable',
            'TypeDecorator',
            'UserDefinedType',
            'TypeEngine',
            'INT',  # INT = INTEGER, (which is a covered type).
        }
        self._validate_type_mapping(
            GENERIC_SQL_CLASS_TO_GRAPHQL_TYPE, UNSUPPORTED_GENERIC_SQL_TYPES, sqlalchemy_module,
            classes_to_ignore
        )

    def test_address_all_mssql_types(self):
        classes_to_ignore = {
            'Concatenable',
            'Indexable',
            'TypeDecorator',
            'UserDefinedType',
            'TypeEngine',
            'INT',  # INT = INTEGER, (which is a covered type).
        }
        self._validate_type_mapping(
            SQL_CLASS_TO_GRAPHQL_TYPE, UNSUPPORTED_MSSQL_TYPES, mssql_module,
            classes_to_ignore
        )
