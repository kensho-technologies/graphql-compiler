#!/usr/bin/env/python

"""
    A minimal compatibility shim for Python 2 and Python 3.
"""

# pylint: disable=redefined-builtin

try:               # Python 2
    basestring
except NameError:  # Python 3
    basestring = str  
    unicode = str
    xrange = range
 
