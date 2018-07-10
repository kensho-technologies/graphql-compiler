# Copyright 2017-present Kensho Technologies, LLC.
import codecs
import os
import re

from setuptools import find_packages, setup


#  https://packaging.python.org/guides/single-sourcing-package-version/
#  #single-sourcing-the-version


def read_file(filename):
    """Read package file as text to get name and version"""
    # intentionally *not* adding an encoding option to open
    # see here:
    # https://github.com/pypa/virtualenv/issues/201#issuecomment-3145690
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, 'graphql_compiler', filename), 'r') as f:
        return f.read()


def find_version():
    """Only define version in one place"""
    version_file = read_file('__init__.py')
    version_match = re.search(r'^__version__ = ["\']([^"\']*)["\']',
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError('Unable to find version string.')


def find_name():
    """Only define name in one place"""
    name_file = read_file('__init__.py')
    name_match = re.search(r'^__package_name__ = ["\']([^"\']*)["\']',
                           name_file, re.M)
    if name_match:
        return name_match.group(1)
    raise RuntimeError('Unable to find name string.')


setup(name=find_name(),
      version=find_version(),
      description='Turn complex GraphQL queries into optimized database queries.',
      url='https://github.com/kensho-technologies/graphql-compiler',
      author='Kensho Technologies, LLC.',
      author_email='graphql-compiler-maintainer@kensho.com',
      license='Apache 2.0',
      packages=find_packages(exclude=['tests*']),
      install_requires=[
          'arrow>=0.7.0',
          'funcy>=1.6',
          'graphql-core==1.1',
          'pytz>=2016.10',
          'six>=1.10.0',
      ],
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Topic :: Database :: Front-Ends',
          'Topic :: Software Development :: Compilers',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: Apache Software License',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
      ],
      keywords='graphql database compiler orientdb',
      python_requires='>=2.7,!=3.0.*,!=3.1.*,!=3.2.*',
      )
