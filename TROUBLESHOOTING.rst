Troubleshooting Guide
=====================

Issues starting MySQL, PostgreSQL, or redis server with docker-compose
----------------------------------------------------------------------

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
------------------------------------------

Sometimes, precompiled wheels for the Python MySQL package are not
available, and your pipenv may try to build the wheels itself. This has
happened on OSX and Ubuntu.

OSX
~~~

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
~~~~~~~~~~~~

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
------------------

If you have any issues installing :Code:`pydobc` when running :code:`pipenv install`, then it might
mean that you have failed to correctly install the ODBC driver.

Another reason that your `pyodbc` installation might fail is because your python installation
did not include the required header files. This issue has only affected Ubuntu users so far and
can be resolved on Ubuntu by running:

.. bash::

    sudo apt-get install python3.8-dev
