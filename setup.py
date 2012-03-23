from setuptools import setup, find_packages
import sys, os

version = '0.0'

setup(name='apppkg',
      version=version,
      description="Support library for Application Packages",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='wsgi web',
      author='Ian Bicking',
      author_email='ian@ianbicking.org',
      url='http://github.com/ianb/apppkg',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      zip_safe=False,
      install_requires=[
          "pyyaml",
      ],
      )
