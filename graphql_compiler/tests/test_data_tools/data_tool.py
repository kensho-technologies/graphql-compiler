# Copyright 2018-present Kensho Technologies, LLC.
import datetime
from glob import glob
from os import path
import string

from funcy import retry
from redisgraph import Edge, Node
import six
from sqlalchemy import create_engine, text
from sqlalchemy.schema import CreateSchema

from ...global_utils import merge_non_overlapping_dicts
from ..integration_tests.integration_backend_config import (
    EXPLICIT_DB_BACKENDS,
    SQL_BACKEND_TO_CONNECTION_STRING,
    SqlTestBackend,
    test_backend,
)
from ..test_helpers import get_sqlalchemy_schema_info


def get_integration_data():
    """Get the small integration data set.

    Returns:
        tuple containing:
        - vertex_values: Dict mapping vertex classes tuples containing the properties of
                         each vertex of that class.
        - edge_values: Dict mapping edges to tuples containing the source and destination vertex
                       of each edge of that class.
        - uuid_to_class_name: Dict mapping vertex uuids to their classnames. The data is
                              already contained in vertex_values, but this can be convenient.
    """
    uuids = {
        "A1": "cfc6e625-8594-0927-468f-f53d864a7a51",
        "A2": "cfc6e625-8594-0927-468f-f53d864a7a52",
        "A3": "cfc6e625-8594-0927-468f-f53d864a7a53",
        "A4": "cfc6e625-8594-0927-468f-f53d864a7a54",
        "S1": "c2c14d8b-0e13-4e64-be63-c86704161850",
        "S2": "35d33f6a-14ab-4b5c-a797-ee9ab817c1fb",
        "B1": "cfc6e625-8594-0927-468f-f53d864a7a55",
        "B2": "cfc6e625-8594-0927-468f-f53d864a7a56",
    }
    vertex_values = {
        "Animal": (
            {
                "uuid": uuids["A1"],
                "name": "Animal 1",
                "net_worth": 100,
                "birthday": datetime.date(1900, 1, 1),
            },
            {
                "uuid": uuids["A2"],
                "name": "Animal 2",
                "net_worth": 200,
                "birthday": datetime.date(1950, 2, 2),
            },
            {
                "uuid": uuids["A3"],
                "name": "Animal 3",
                "net_worth": 300,
                "birthday": datetime.date(1975, 3, 3),
            },
            {
                "uuid": uuids["A4"],
                "name": "Animal 4",
                "net_worth": 400,
                "birthday": datetime.date(2000, 4, 4),
            },
        ),
        "Species": (
            {
                "uuid": uuids["S1"],
                "name": "Species 1",
            },
            {
                "uuid": uuids["S2"],
                "name": "Species 2",
            },
        ),
        "BirthEvent": (
            {
                "uuid": uuids["B1"],
                "name": "birth_event_1",
                "event_date": datetime.datetime(2000, 1, 1, 1, 1, 1),
            },
            {
                "uuid": uuids["B2"],
                "name": "birth_event_2",
                "event_date": datetime.datetime(2000, 1, 1, 1, 1, 2),
            },
        ),
    }
    edge_values = {
        "Entity_Related": (
            {
                "from_uuid": uuids["S1"],
                "to_uuid": uuids["S2"],
            },
        ),
        "Animal_ParentOf": (
            {
                "from_uuid": uuids["A1"],
                "to_uuid": uuids["A1"],
            },
            {
                "from_uuid": uuids["A1"],
                "to_uuid": uuids["A2"],
            },
            {
                "from_uuid": uuids["A1"],
                "to_uuid": uuids["A3"],
            },
            {
                "from_uuid": uuids["A3"],
                "to_uuid": uuids["A4"],
            },
        ),
    }

    # Find the class name of each vertex uuid
    uuid_to_class_name = {}
    for vertex_name, values in six.iteritems(vertex_values):
        for value in values:
            if value["uuid"] in uuid_to_class_name:
                raise AssertionError("Duplicate uuid found {}".format(value["uuid"]))
            uuid_to_class_name[value["uuid"]] = vertex_name

    return vertex_values, edge_values, uuid_to_class_name


def generate_orient_snapshot_data(client):
    """Create OrientDB test DB from the SQL commands file for snapshot testing."""
    project_root = path.dirname(path.abspath(__file__))
    sql_files = glob(path.join(project_root, "snapshot_data/*.sql"))

    _load_sql_files_to_orient_client(client, sql_files)


def _validate_name(name):
    """Check conservatively for allowed vertex and field names."""
    if not isinstance(name, six.string_types):
        raise AssertionError("Expected string name. Received {}".format(name))
    allowed_characters = string.ascii_uppercase + string.ascii_lowercase + string.digits + "_"
    if any(c not in allowed_characters for c in str(name)):
        raise AssertionError("Name {} contains disallowed characters".format(name))


def _write_orient_equality(field_name, field_value):
    """Write a '{} = {}' statement to be used in queries, validating against SQL injection."""
    _validate_name(field_name)
    if isinstance(field_value, six.string_types):
        allowed_characters = string.ascii_uppercase + string.ascii_lowercase + string.digits + "-_ "
        if any(c not in allowed_characters for c in str(field_value)):
            raise AssertionError(
                "String value {} contains disallowed characters".format(field_value)
            )
    elif isinstance(field_value, (six.integer_types, float, datetime.date)):
        pass
    else:
        raise NotImplementedError(
            "Value validation for type {} is not implemented".format(type(field_value))
        )

    field_value_representation = repr(field_value)
    if isinstance(field_value, datetime.date):
        field_value_representation = 'DATE("' + field_value.strftime("%Y-%m-%d %H:%M:%S") + '")'
    template = "{} = {}"
    return template.format(field_name, field_value_representation)


def generate_orient_integration_data(client):
    """Create OrientDB test DB from the standard integration data."""
    vertex_values, edge_values, uuid_to_class_name = get_integration_data()
    for vertex_name, vertices in six.iteritems(vertex_values):
        for vertex_props in vertices:
            _validate_name(vertex_name)
            command = "CREATE VERTEX {} SET ".format(vertex_name) + ", ".join(
                _write_orient_equality(key, value) for key, value in six.iteritems(vertex_props)
            )
            client.command(command)
    for edge_name, edges in six.iteritems(edge_values):
        for edge_spec in edges:
            from_classname = uuid_to_class_name[edge_spec["from_uuid"]]
            to_classname = uuid_to_class_name[edge_spec["to_uuid"]]
            _validate_name(from_classname)
            _validate_name(to_classname)
            vertex_template = "SELECT FROM {} WHERE {}"
            from_selection = vertex_template.format(
                from_classname, _write_orient_equality("uuid", edge_spec["from_uuid"])
            )
            to_selection = vertex_template.format(
                from_classname, _write_orient_equality("uuid", edge_spec["to_uuid"])
            )
            command = "CREATE EDGE {} FROM ({}) TO ({})".format(
                edge_name, from_selection, to_selection
            )
            client.command(command)


def generate_neo4j_integration_data(client):
    """Create Neo4j test DB from the standard integration data."""
    vertex_values, edge_values, _ = get_integration_data()
    with client.driver.session() as session:
        session.run("match (n) detach delete n")
        for vertex_name, vertices in six.iteritems(vertex_values):
            _validate_name(vertex_name)
            for vertex_props in vertices:
                for key in vertex_props:
                    _validate_name(key)
                command = "create (:{} {{{}}})".format(
                    vertex_name, ", ".join(f"{key}: ${key}" for key in vertex_props)
                )
                session.run(command, vertex_props)
    with client.driver.session() as session:
        for edge_name, edges in six.iteritems(edge_values):
            _validate_name(edge_name)
            for edge_spec in edges:
                command = (
                    """
                    match (a {uuid: $from_uuid}), (b {uuid: $to_uuid})
                    create (a)-[:"""
                    + edge_name
                    + "]->(b)"
                )
                args = {
                    "from_uuid": edge_spec["from_uuid"],
                    "to_uuid": edge_spec["to_uuid"],
                }
                session.run(command, args)


def generate_redisgraph_integration_data(client):
    """Create Redisgraph test DB from the standard integration data."""
    vertex_values, edge_values, _ = get_integration_data()
    client.query("create (n)")
    client.query("match (n) delete n")
    uuid_to_node = {}
    for vertex_name, vertices in six.iteritems(vertex_values):
        for vertex_props in vertices:
            # NOTE(bojanserafimov): Dates and datetimes are not supported in redisgraph,
            #                       so we just omit them from the dataset.
            uuid_to_node[vertex_props["uuid"]] = Node(
                label=vertex_name,
                properties={
                    key: value
                    for key, value in six.iteritems(vertex_props)
                    if not isinstance(value, (datetime.date, datetime.datetime))
                },
            )
            client.add_node(uuid_to_node[vertex_props["uuid"]])
    for edge_name, edges in six.iteritems(edge_values):
        for edge_spec in edges:
            client.add_edge(
                Edge(
                    uuid_to_node[edge_spec["from_uuid"]],
                    edge_name,
                    uuid_to_node[edge_spec["to_uuid"]],
                )
            )
    client.commit()


def _load_sql_files_to_orient_client(client, sql_files):
    """Load list of supplied SQL files into the supplied OrientDB client."""
    for filepath in sql_files:
        with open(filepath) as f:
            for command in f.readlines():
                sanitized_command = command.strip()
                if len(sanitized_command) == 0 or sanitized_command[0] == "#":
                    # comment or empty line, ignore
                    continue

                client.command(sanitized_command)


@retry(tries=1, timeout=1)  # pylint: disable=no-value-for-parameter
def init_sql_integration_test_backends():
    """Connect to and open transaction on each SQL DB under test."""
    sql_test_backends = {}
    for backend_name, base_connection_string in six.iteritems(SQL_BACKEND_TO_CONNECTION_STRING):
        engine = create_engine(base_connection_string)
        # safely create the test DATABASE for all SQL backends except sqlite
        # sqlite's in-memory database does not need to be explicitly created/dropped.
        if backend_name in EXPLICIT_DB_BACKENDS:

            if backend_name == test_backend.POSTGRES:
                # Drop schemas and dependent tables if they exist.
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text("DROP SCHEMA IF EXISTS schema_1 CASCADE;")
                )
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text("DROP SCHEMA IF EXISTS schema_2 CASCADE;")
                )
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text("DROP SCHEMA IF EXISTS schema_3 CASCADE;")
                )
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text("DROP SCHEMA IF EXISTS schema_4 CASCADE;")
                )

                # Create the test schemas.
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    CreateSchema("schema_1")
                )
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    CreateSchema("schema_2")
                )
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    CreateSchema("schema_3")
                )
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    CreateSchema("schema_4")
                )
            else:
                # Drop databases if they exist
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text("DROP DATABASE IF EXISTS db_1;")
                )
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text("DROP DATABASE IF EXISTS db_2;")
                )

                # create the test databases
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text("CREATE DATABASE db_1;")
                )
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text("CREATE DATABASE db_2;")
                )

                engine.execution_options(isolation_level="AUTOCOMMIT").execute(text("USE db_1;"))
                # create the test schemas in db_1
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    CreateSchema("schema_1")
                )
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    CreateSchema("schema_2")
                )

                engine.execution_options(isolation_level="AUTOCOMMIT").execute(text("USE db_2;"))
                # create the test schemas in db_2
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    CreateSchema("schema_1")
                )
                engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                    CreateSchema("schema_2")
                )

                engine.execution_options(isolation_level="AUTOCOMMIT").execute(text("USE master;"))

        sql_test_backend = SqlTestBackend(engine, base_connection_string)
        sql_test_backends[backend_name] = sql_test_backend
    return sql_test_backends


def tear_down_integration_test_backends(sql_test_backends):
    """Rollback backends' transactions to wipe test data and to close the active connections."""
    for backend_name, sql_test_backend in six.iteritems(sql_test_backends):
        if backend_name not in EXPLICIT_DB_BACKENDS:
            continue
        # explicitly release engine resources, specifically to disconnect from active DB
        # some backends including Postgres do no not allow an in use DB to be dropped
        sql_test_backend.engine.dispose()
        # connect to base server, not explicit DB, so DB can be dropped
        engine = create_engine(sql_test_backend.base_connection_string)
        # set execution options to AUTOCOMMIT so that the DB drop is not performed in a transaction
        # as this is not allowed on some SQL backends
        if backend_name == test_backend.POSTGRES:
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                text("DROP SCHEMA IF EXISTS schema_1 CASCADE;")
            )
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                text("DROP SCHEMA IF EXISTS schema_2 CASCADE;")
            )
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                text("DROP SCHEMA IF EXISTS schema_3 CASCADE;")
            )
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                text("DROP SCHEMA IF EXISTS schema_4 CASCADE;")
            )
        else:
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                text("DROP DATABASE IF EXISTS db_1;")
            )
            engine.execution_options(isolation_level="AUTOCOMMIT").execute(
                text("DROP DATABASE IF EXISTS db_2;")
            )


def generate_sql_integration_data(sql_test_backends):
    """Populate test data for SQL backends for integration testing."""
    sql_schema_info = {}
    for backend_name, sql_test_backend in six.iteritems(sql_test_backends):
        backend_specific_sql_schema_info = get_sqlalchemy_schema_info(backend_name)
        vertex_values, edge_values, uuid_to_class_name = get_integration_data()

        # Represent all edges as foreign keys
        uuid_to_foreign_key_values = {}
        for edge_name, edge_values in six.iteritems(edge_values):
            for edge_value in edge_values:
                from_classname = uuid_to_class_name[edge_value["from_uuid"]]
                edge_field_name = "out_{}".format(edge_name)
                join_descriptor = backend_specific_sql_schema_info.join_descriptors[from_classname][
                    edge_field_name
                ]

                is_from_uuid = join_descriptor.from_column == "uuid"
                is_to_uuid = join_descriptor.to_column == "uuid"
                if is_from_uuid == is_to_uuid:
                    raise NotImplementedError(
                        "Exactly one of the join columns was expected to"
                        "be uuid. found {}".format(join_descriptor)
                    )

                if is_from_uuid:
                    existing_foreign_key_values = uuid_to_foreign_key_values.setdefault(
                        edge_value["to_uuid"], {}
                    )
                    if join_descriptor.to_column in existing_foreign_key_values:
                        raise NotImplementedError(
                            "The SQL backend does not support many-to-many "
                            "edges. Found multiple edges of class {} from "
                            "vertex {}.".format(edge_name, edge_value["to_uuid"])
                        )
                    existing_foreign_key_values[join_descriptor.to_column] = edge_value["from_uuid"]
                elif is_to_uuid:
                    existing_foreign_key_values = uuid_to_foreign_key_values.setdefault(
                        edge_value["from_uuid"], {}
                    )
                    if join_descriptor.from_column in existing_foreign_key_values:
                        raise NotImplementedError(
                            "The SQL backend does not support many-to-many "
                            "edges. Found multiple edges of class {} to "
                            "vertex {}.".format(edge_name, edge_value["to_uuid"])
                        )
                    existing_foreign_key_values[join_descriptor.from_column] = edge_value["to_uuid"]

        # Insert all the prepared data into the test database
        # for sql_test_backend in six.itervalues(sql_test_backends):
        for vertex_name, insert_values in six.iteritems(vertex_values):
            table = backend_specific_sql_schema_info.vertex_name_to_table[vertex_name]
            table.delete(bind=sql_test_backend.engine)
            table.create(bind=sql_test_backend.engine)
            for insert_value in insert_values:
                foreign_key_values = uuid_to_foreign_key_values.get(insert_value["uuid"], {})
                all_values = merge_non_overlapping_dicts(insert_value, foreign_key_values)
                sql_test_backend.engine.execute(table.insert().values(**all_values))

        sql_schema_info[backend_name] = backend_specific_sql_schema_info

    return sql_schema_info
