from setuptools import find_packages, setup

package_name = 'graphql-compiler'
version = '1.0.0'

setup(name=package_name,
      version=version,
      description='Turn complex GraphQL queries into optimized database queries.',
      packages=find_packages(),
      install_requires=[
          'arrow>=0.7.0',
          'funcy>=1.6',
          'graphql-core==1.1',
          'pytz>=2016.10'
      ],
      )
