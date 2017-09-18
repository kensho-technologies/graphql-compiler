from setuptools import find_packages, setup

package_name = 'graphql-compiler'
version = '1.1.0'

setup(name=package_name,
      version=version,
      description='Turn complex GraphQL queries into optimized database queries.',
      url='https://github.com/kensho-technologies/graphql-compiler',
      author='Kensho Technologies, Inc.',
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
      python_requires='>=2.7',
      )
