# Copyright 2017-present Kensho Technologies, LLC.
import codecs
import os
import re

from setuptools import find_packages, setup


#  https://packaging.python.org/guides/single-sourcing-package-version/
#  #single-sourcing-the-version


def read_file(filename: str) -> str:
    """Read package file as text to get name and version."""
    # intentionally *not* adding an encoding option to open
    # see here:
    # https://github.com/pypa/virtualenv/issues/201#issuecomment-3145690
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, "graphql_compiler", filename), "r") as f:
        return f.read()


def find_version() -> str:
    """Only define version in one place."""
    version_file = read_file("__init__.py")
    version_match = re.search(r'^__version__ = ["\']([^"\']*)["\']', version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


def find_name() -> str:
    """Only define name in one place."""
    name_file = read_file("__init__.py")
    name_match = re.search(r'^__package_name__ = ["\']([^"\']*)["\']', name_file, re.M)
    if name_match:
        return name_match.group(1)
    raise RuntimeError("Unable to find name string.")


def find_long_description() -> str:
    """Return the content of the README.rst file."""
    return read_file("../README.rst")


setup(
    name=find_name(),
    version=find_version(),
    description="Turn complex GraphQL queries into optimized database queries.",
    long_description=find_long_description(),
    long_description_content_type="text/x-rst",
    url="https://github.com/kensho-technologies/graphql-compiler",
    author="Kensho Technologies, LLC.",
    author_email="graphql-compiler-maintainer@kensho.com",
    license="Apache 2.0",
    packages=find_packages(exclude=["tests*"]),
    install_requires=[  # Make sure to keep in sync with Pipfile requirements.
        "ciso8601>=2.1.3,<3",
        "funcy>=1.7.3,<2",
        "graphql-core>=3.1.2,<3.2",
        "six>=1.10.0",
        "sqlalchemy>=1.3.0,<2",
    ],
    extras_require={
        ':python_version<"3.7"': ["dataclasses>=0.7,<1"],
        ':python_version<"3.8"': [
            "backports.cached-property>=1.0.0.post2,<2",
            "typing-extensions>=3.7.4.2,<4",
        ],
    },
    package_data={"": ["py.typed"]},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Topic :: Database :: Front-Ends",
        "Topic :: Software Development :: Compilers",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    keywords="graphql database compiler sql orientdb",
    python_requires=">=3.6",
)
