Contributing
============

Thank you for taking the time to contribute to this project!

To get started, make sure that you have :code:`pipenv`, :code:`docker` and
:code:`docker-compose` installed on your computer.

Although GraphQL compiler supports multiple Python 3.6+ versions,
we have chosen to use Python 3.8 for development. If you do not already have it installed,
consider doing so using `pyenv <https://github.com/pyenv/pyenv>`__.

If developing on Linux, please also ensure that your Python installation includes header files.
The command to install Python header files should look something like this,
depending on chosen flavor of Linux.
.. ::

    sudo apt-get install python3.8-dev


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

   pytest -m 'not slow'

If you run into any issues, please consult the `troubleshooting guide <troubleshooting>`__.
If you encounter and resolve an issue that is not already part of the
troubleshooting guide, we'd appreciate it if you open a pull request and
update the guide to make future development easier.

A test method or class can be marked as slow to be skipped in this
fashion by decorating with the :code:`@pytest.mark.slow` flag.

Code of Conduct
---------------

This project adheres to the Contributor Covenant `code of
conduct <https://graphql-compiler.readthedocs.io/en/latest/about/code_of_conduct.html>`__. By
participating, you are expected to uphold this code. Please report unacceptable behavior at
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

.. _troubleshooting:

Troubleshooting Guide
---------------------

Issues starting MySQL, PostgreSQL, or redis server with docker-compose
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have any trouble starting the MySQL/PostgreSQL database or the
redis server, make sure any database service or any other related
service is not already running outside of docker. On OSX, you can stop
the MySQL, PostgreSQL, and redis server services by executing:

.. code:: bash

   brew services stop mysql
   brew services stop postgresql
   brew services stop redis-server

or on Ubuntu with:

.. code:: bash

   service mysql stop
   service postgresql stop
   service redis-server stop

Issues installing the Python MySQL package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sometimes, precompiled wheels for the Python MySQL package are not
available, and your pipenv may try to build the wheels itself. This has
happened on OSX and Ubuntu.

OSX
^^^

You may then sometimes see an error like the following:

::

   [pipenv.exceptions.InstallError]:   File "/usr/local/lib/python3.7/site-packages/pipenv/core.py", line 1874, in do_install
   [pipenv.exceptions.InstallError]:       keep_outdated=keep_outdated
   [pipenv.exceptions.InstallError]:   File "/usr/local/lib/python3.7/site-packages/pipenv/core.py", line 1253, in do_init
   [pipenv.exceptions.InstallError]:       pypi_mirror=pypi_mirror,
   [pipenv.exceptions.InstallError]:   File "/usr/local/lib/python3.7/site-packages/pipenv/core.py", line 859, in do_install_dependencies
   [pipenv.exceptions.InstallError]:       retry_list, procs, failed_deps_queue, requirements_dir, **install_kwargs
   [pipenv.exceptions.InstallError]:   File "/usr/local/lib/python3.7/site-packages/pipenv/core.py", line 763, in batch_install
   [pipenv.exceptions.InstallError]:       _cleanup_procs(procs, not blocking, failed_deps_queue, retry=retry)
   [pipenv.exceptions.InstallError]:   File "/usr/local/lib/python3.7/site-packages/pipenv/core.py", line 681, in _cleanup_procs
   [pipenv.exceptions.InstallError]:       raise exceptions.InstallError(c.dep.name, extra=err_lines)
   [pipenv.exceptions.InstallError]: ['Collecting mysqlclient==1.3.14
   ...
   < lots of error output >
   ...
   ld: library not found for -lssl
   ...
   < lots more error output >
   ...
   error: command 'clang' failed with exit status 1
   ...

The solution is to install OpenSSL on your system:

::

   brew install openssl

Then, make sure that :code:`clang` is able to find it by adding the
following line to your :code:`.bashrc`.

::

   export LIBRARY_PATH=$LIBRARY_PATH:/usr/local/opt/openssl/lib/

.. _ubuntu-1804:

Ubuntu 18.04
^^^^^^^^^^^^

When running

::

   pipenv install --dev

you might get an error like the following:

::

   [pipenv.exceptions.InstallError]:   File "/home/$USERNAME/.local/lib/python2.7/site-packages/pipenv/core.py", line 1875, in do_install

   [pipenv.exceptions.InstallError]:       keep_outdated=keep_outdated

   [pipenv.exceptions.InstallError]:   File "/home/$USERNAME/.local/lib/python2.7/site-packages/pipenv/core.py", line 1253, in do_init

   [pipenv.exceptions.InstallError]:       pypi_mirror=pypi_mirror,

   [pipenv.exceptions.InstallError]:   File "/home/$USERNAME/.local/lib/python2.7/site-packages/pipenv/core.py", line 859, in do_install_dependencies

   [pipenv.exceptions.InstallError]:       retry_list, procs, failed_deps_queue, requirements_dir, **install_kwargs

   [pipenv.exceptions.InstallError]:   File "/home/$USERNAME/.local/lib/python2.7/site-packages/pipenv/core.py", line 763, in batch_install

   [pipenv.exceptions.InstallError]:       _cleanup_procs(procs, not blocking, failed_deps_queue, retry=retry)

   [pipenv.exceptions.InstallError]:   File "/home/$USERNAME/.local/lib/python2.7/site-packages/pipenv/core.py", line 681, in _cleanup_procs

   [pipenv.exceptions.InstallError]:       raise exceptions.InstallError(c.dep.name, extra=err_lines)

   [pipenv.exceptions.InstallError]: ['Collecting mysqlclient==1.3.14 (from -r /tmp/pipenv-ZMU3RA-requirements/pipenv-n_utvZ-requirement.txt (line 1))', '  Using cached https://files.pythonhosted.org/packages/f7/a2/1230ebbb4b91f42ad6b646e59eb8855559817ad5505d81c1ca2b5a216040/mysqlclient-1.3.14.tar.gz']

   [pipenv.exceptions.InstallError]: ['ERROR: Complete output from command python setup.py egg_info:', '    ERROR: /bin/sh: 1: mysql_config: not found', '    Traceback (most recent call last):', '      File "<string>", line 1, in <module>', '      File "/tmp/pip-install-ekmq8s3j/mysqlclient/setup.py", line 16, in <module>', '        metadata, options = get_config()', '      File "/tmp/pip-install-ekmq8s3j/mysqlclient/setup_posix.py", line 53, in get_config', '        libs = mysql_config("libs_r")', '      File "/tmp/pip-install-ekmq8s3j/mysqlclient/setup_posix.py", line 28, in mysql_config', '        raise EnvironmentError("%s not found" % (mysql_config.path,))', '    OSError: mysql_config not found', '    ----------------------------------------', 'ERROR: Command "python setup.py egg_info" failed with error code 1 in /tmp/pip-install-ekmq8s3j/mysqlclient/']

The solution is to install MySQL:

::

   sudo apt-get install python3.8-dev libmysqlclient-dev

after which

::

   pipenv install --dev

should work fine.

This error might happen even if you've run

::

   apt-get install python-mysqldb

because that only installs the interface to MySQL.

Issues with pyodbc
^^^^^^^^^^^^^^^^^^

If you have any issues installing :Code:`pydobc` when running :code:`pipenv install`, then it might
mean that you have failed to correctly install the ODBC driver.

Another reason that your `pyodbc` installation might fail is because your python installation
did not include the required header files. This issue has only affected Ubuntu users so far and
can be resolved on Ubuntu by running:

.. ::

    sudo apt-get install python3.8-dev
