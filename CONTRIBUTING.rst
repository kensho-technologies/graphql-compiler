Contributing
============

Thank you for taking the time to contribute to this project!

To get started, make sure that you have :code:`pipenv`, :code:`docker` and
:code:`docker-compose` installed on your computer. Please make sure
you have Python 3.8+ installed locally. If you do not already have it installed,
consider doing so using `pyenv <https://github.com/pyenv/pyenv>`__.

Database Driver Installations
-----------------------------

Integration tests are run against multiple databases, some of which require that you install specific drivers. Below
you'll find the installation instructions for these drivers for Ubuntu and OSX. You might need to run some of the
commands with :code:`sudo` depending on your local setup.

MySQL Driver
~~~~~~~~~~~~

For MySQL a compatible driver can be installed on OSX with:

.. code:: bash

   brew install mysql

or on Ubuntu with:

.. code:: bash

   apt-get install libmysqlclient-dev python-mysqldb

For more details on other systems please refer to `MySQL dialect
information <https://docs.sqlalchemy.org/en/latest/dialects/mysql.html>`__.

Microsoft SQL Server ODBC Driver
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For MSSQL, you can install the required ODBC driver on OSX with:

.. code:: bash

    brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
    brew install msodbcsql17 mssql-tools

Or Ubuntu with:

.. code:: bash

    wget -qO- https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
    add-apt-repository "$(wget -qO- https://packages.microsoft.com/config/ubuntu/"$(lsb_release -r -s)"/prod.list)"
    apt-get update
    ACCEPT_EULA=Y apt-get install msodbcsql17
    apt-get install unixodbc-dev

To see the installation instructions for other operating systems, please follow this `link
<https://docs.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server?view=sql-server-2017&viewFallbackFrom=ssdt-18vs2017>`__.

Running tests
-------------

Once the dev environment is prepared, you can run the tests, from the root repository, with:

::

   docker-compose up -d
   pipenv sync --dev
   pipenv shell

   pytest graphql_compiler/tests

Some snapshot and integration tests take longer to setup, run, and
teardown. These can be optionally skipped during development by running:

.. code:: bash

   pytest -m 'no-slow'

If you run into any issues, please consult the TROUBLESHOOTING.md file.
If you encounter and resolve an issue that is not already part of the
troubleshooting guide, we'd appreciate it if you open a pull request and
update the guide to make future development easier.

A test method or class can be marked as slow to be skipped in this
fashion by decorating with the :code:`@pytest.mark.slow` flag.

Code of Conduct
---------------

This project adheres to the Contributor Covenant `code of
conduct <CODE_OF_CONDUCT.rst>`__. By participating, you are expected to
uphold this code. Please report unacceptable behavior at
graphql-compiler-maintainer@kensho.com.

Contributor License Agreement
-----------------------------

Each contributor is required to agree to our `Contributor License
Agreement <https://www.clahub.com/agreements/kensho-technologies/graphql-compiler>`__,
to ensure that their contribution may be safely merged into the project
codebase and released under the existing code license. This agreement
does not change contributors' rights to use the contributions for any
other purpose -- it is simply used for the protection of both the
contributors and the project.

Style Guide
-----------

This project primarily follows the `PEP 8 style guide
<https://www.python.org/dev/peps/pep-0008/>`__, and secondarily the
`Google Python style guide <https://google.github.io/styleguide/pyguide.html>`__.
If the style guides differ on a convention, the PEP 8 style guide is preferred.

Additionally, any contributions must pass the linter :code:`scripts/lint.sh`
when executed from a pipenv shell (i.e. after running :code:`pipenv shell`).
To run the linter on changed files only, commit your changes and run
:code:`scripts/lint.sh --diff`. Some linters can automatically fix errors.
Use :code:`scripts/fix_lint.sh` to run the automatic fixes.

Finally, all python files in the repository must display the copyright
of the project, to protect the terms of the license. Please make sure
that your files start with a line like:

::

   # Copyright 20xx-present Kensho Technologies, LLC.

Read the Docs
-------------

We are currently in the process of moving most of our documentation to
Read the Docs, a web utility that makes it easy to view and present
documentation.

Since Read the Docs does not currently `support Pipfiles
<https://github.com/readthedocs/readthedocs.org/issues/3181>`__, we must keep the
documentation building requirements in both the repository's :code:`Pipfile`, which we use for
continuous integration and local development, and in :code:`docs/requirements.txt`, which we use
for Read The Docs.

The relevant documentation source code lives in:

::

   docs/source

To build the website run:

::

   pipenv shell
   cd docs
   make clean
   make html

Then open :code:`docs/build/index.html` with a web browser to view it.
