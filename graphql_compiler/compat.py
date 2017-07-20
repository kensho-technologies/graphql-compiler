#!/usr/bin/env/python

"""A minimal compatibility shim for Python 2 and Python 3."""


try:               # Python 2
    basestring = basestring
    unicode = unicode
    xrange = xrange
except NameError:  # Python 3
    basestring = str
    unicode = str
    xrange = range  # pylint: disable=redefined-variable-type
