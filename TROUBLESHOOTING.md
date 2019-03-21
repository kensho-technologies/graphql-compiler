# Troubleshooting Guide

## Issues starting MySQL with docker-compose

If you have any trouble starting the MySQL database, make sure the MySQL service is not already
running outside of docker. You can stop the MySQL service in OSX with:
```bash
brew services stop mysql
```
or on Ubuntu with
```bash
service mysql stop
```

## Issues installing the Python MySQL package

Sometimes, precompiled wheels for the Python MySQL package are not available, and your pipenv may
try to build the wheels itself. If you are on OSX, you may then sometimes see an error
like the following:
```
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
```

The solution is to install OpenSSL on your system:
```
brew install openssl
```
Then, make sure that `clang` is able to find it by adding the following line to your `.bashrc`.
```
export LIBRARY_PATH=$LIBRARY_PATH:/usr/local/opt/openssl/lib/
```
