Contributing
============

Thank you for taking the time to contribute to this project!

To get started, make sure that you have :code:`pipenv`, :code:`docker` and
:code:`docker-compose` installed on your computer. Additionally, since this
is a package that supports both Python 2 and Python 3, please make sure
you have Python 2.7.15+ and Python 3.7+ installed locally. This project
assumes that they are available on the system as :code:`python2` and
:code:`python3`, respectively. If you do not already have them installed,
consider doing so using `pyenv <https://github.com/pyenv/pyenv>`__.

Integration tests are run against multiple SQL databases, some of which
require dialect specific installations to be available in the
development environment. Currently this affects MySQL. A compatible
driver can be installed on OSX with:

.. code:: bash

   brew install mysql

or on Ubuntu with:

.. code:: bash

   apt-get install python-mysqldb

For more details on other systems please refer to `MySQL dialect
information <https://docs.sqlalchemy.org/en/latest/dialects/mysql.html>`__.

Once the dev environment is prepared, from the root of the repository,
run:

::

   docker-compose up -d
   pipenv sync --dev
   pipenv shell

   py.test graphql_compiler/tests

Some snapshot and integration tests take longer to setup, run, and
teardown. These can be optionally skipped during development by running:

.. code:: bash

   py.test -m 'no-slow'

If you run into any issues, please consult the :ref:`troubleshooting guide <troubleshooting>`.
If you encounter and resolve an issue that is not already part of the
troubleshooting guide, we'd appreciate it if you open a pull request and
update the guide to make future development easier.

A test method or class can be marked as slow to be skipped in this
fashion by decorating with the :code:`@pytest.mark.slow` flag.

Code of Conduct
---------------

This project adheres to the Contributor Covenant :doc:`code of
conduct <code_of_conduct>`. By participating, you are expected to
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
:code:`scripts/lint.sh --diff`.

Finally, all python files in the repository must display the copyright
of the project, to protect the terms of the license. Please make sure
that your files start with a line like:

::

   # Copyright 20xx-present Kensho Technologies, LLC.

Python 2 vs Python 3
--------------------

In order to ensure that tests run with a fixed set of packages in both
Python 2 and Python 3, we always run the tests in a virtualenv managed
by pipenv. However, since some of our dependencies have different
requirements for Python 2 and Python 3, we have to keep two pipenv
lockfiles -- one per Python version.

We have chosen to make the Python 3 lockfile the default (hence named
:code:`Pipfile.lock`), since Python 3 offers better performance and we like
our tests and linters running quickly. The Python 2 lockfile is named
:code:`Pipfile.py2.lock`.

If you need to set up a Python 2 virtualenv locally, simply run the
following script:

::

   ./scripts/make_py2_venv.sh

If you change the Pipfile or the package requirements, please make sure
to regenerate the lockfiles for both Python versions. The easiest way to
do so is with the following script:

::

   ./scripts/make_pipenv_lockfiles.sh

Then, re-run

::

   pipenv sync --dev

to install the relevant dependencies.

Read the Docs
-------------

We are currently in the process of moving most of our documentation to
Read the Docs, a web utility that makes it easy to view and present
documentation. We first plan to get the Read the Docs documentation up
to date with the markdown documentation present as of commit
16fd083e78551f866a0cf0c7397542aea1c214d9 and then working on adding the
documentation added since that commit.

Since Read the Docs does not currently `support
Pipfiles <https://github.com/readthedocs/readthedocs.org/issues/3181>`__
the package requirements are in:

::

   docs/requirements.txt

The relevant source code lives in:

::

   docs/source

To build the website run:

::

   cd docs
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

   sudo apt-get install python3.6-dev libmysqlclient-dev

after which

::

   pipenv install --dev

should work fine.

This error might happen even if you've run

::

   apt-get install python-mysqldb

because that only installs the interface to MySQL.
