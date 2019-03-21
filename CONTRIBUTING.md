# Contributing

Thank you for taking the time to contribute to this project!

To get started, make sure that you have `pipenv`, `docker` and `docker-compose` installed
on your computer.

Integration tests are run against multiple SQL databases, some of which require dialect specific
installations to be available in the development environment.
Currently this affects MySQL. A compatible driver can be installed on OSX with:
```bash
brew install mysql
```
or on Ubuntu with:
```bash
apt-get install python-mysqldb
```

For more details on other systems please refer to
[MySQL dialect information](https://docs.sqlalchemy.org/en/latest/dialects/mysql.html).

Once the dev environment is prepared, from the root of the repository, run:
```
docker-compose up -d
pipenv sync --dev
pipenv shell

py.test graphql_compiler/tests
```

If you have any trouble starting the mysql database, make sure mysql service is not already 
running outside of docker. You can do stop mysql service in OSX with:
```bash 
brew services stop mysql
```
or on Ubuntu with 
```bash
service mysql stop
```

Some snapshot and integration tests take longer to setup, run, and teardown. These can be optionally
skipped during development by running the tests with the `--skip-slow` flag:
```bash
py.test graphql_compiler/tests --skip-slow
```

A test method or class can be marked as slow to be skipped in this fashion by decorating with the
`@pytest.mark.slow` flag.

## Code of Conduct

This project adheres to the Contributor Covenant [code of conduct](CODE_OF_CONDUCT.md).
By participating, you are expected to uphold this code.
Please report unacceptable behavior at
[graphql-compiler-maintainer@kensho.com](mailto:graphql-compiler-maintainer@kensho.com).

## Contributor License Agreement

Each contributor is required to agree to our
[Contributor License Agreement](https://www.clahub.com/agreements/kensho-technologies/graphql-compiler),
to ensure that their contribution may be safely merged into the project codebase and
released under the existing code license. This agreement does not change contributors'
rights to use the contributions for any other purpose -- it is simply used for the protection
of both the contributors and the project.

## Style Guide

This project follows the
[Google Python style guide](https://google.github.io/styleguide/pyguide.html).

Additionally, any contributions must pass the linter `scripts/lint.sh` when executed from a pipenv shell (i.e. after running `pipenv shell`). To run the linter on changed files only, commit your changes and run `scripts/lint.sh --diff`.

Finally, all python files in the repository must display the copyright of the project,
to protect the terms of the license. Please make sure that your files start with a line like:
```
# Copyright 20xx-present Kensho Technologies, LLC.
```
