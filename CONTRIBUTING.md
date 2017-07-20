# Contributing

Thank you for taking the time to contribute to this project!

To get started:
```
pip install -r dev-requirements.txt
pip install -r requirements.txt

py.test graphql_compiler/tests
```

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

Additionally, any contributions must pass the following set of lint and style checks with no issues:
```
flake8 graphql_compiler/

pydocstyle graphql_compiler/

isort --check-only --verbose --recursive graphql_compiler/

pylint graphql_compiler/

bandit -r graphql_compiler/
```
