#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2010 Nicholas Piël

# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

import os, sys

from distutils.core import setup, Command
from distutils.extension import Extension

from unittest import TextTestRunner, TestLoader
from glob import glob
from os.path import splitext, basename, join as pjoin, walk


#-----------------------------------------------------------------------------
# Extra commands
#-----------------------------------------------------------------------------

class TestCommand(Command):
    user_options = [ ]

    def initialize_options(self):
        self._dir = os.getcwd()

    def finalize_options(self):
        pass

    def run(self):
        '''
        Finds all the tests modules in pyhead/tests/, and runs them.
        '''
        testfiles = [ ]
        for t in glob(pjoin(self._dir, 'tests', '*test*.py')):
            if not t.endswith('__init__.py'):
                testfiles.append('.'.join(
                    ['tests', splitext(basename(t))[0]])
                )
        tests = TestLoader().loadTestsFromNames(testfiles)
        t = TextTestRunner(verbosity = 2)
        t.run(tests)


class CleanCommand(Command):
    user_options = [ ]

    def initialize_options(self):
        self._clean_me = [pjoin('pyhead', 'pyhead.so') ]
        for root, dirs, files in os.walk('.'):
            for f in files:
                if f.endswith('.pyc'):
                    self._clean_me.append(pjoin(root, f))

    def finalize_options(self):
        pass

    def run(self):
        for clean_me in self._clean_me:
            try:
                os.unlink(clean_me)
            except:
                pass

#-----------------------------------------------------------------------------
# Extensions
#-----------------------------------------------------------------------------

cmdclass = {'test':TestCommand, 'clean':CleanCommand }
ryan_parser_source = os.path.join('pyhead', 'ryan', 'http_parser.c')
zed_parser_source = os.path.join('pyhead', 'zed', 'http11_parser.c')
try:
    from Cython.Distutils import build_ext
except ImportError:
    ryan_parser = os.path.join('pyhead', 'ryan', 'ryan.c')
    zed_parser = os.path.join('pyhead', 'zed', 'zed.c')
else:
    ryan_parser = os.path.join('pyhead', 'ryan', 'ryan.pyx')
    zed_parser = os.path.join('pyhead', 'zed', 'zed.pyx')
    cmdclass['build_ext'] =  build_ext

ryan = Extension(
    'pyhead._ryan',
    sources = [ryan_parser, ryan_parser_source],
    include_dirs=[os.path.join('pyhead','ryan')]
)

zed = Extension(
    'pyhead._zed',
    sources = [zed_parser, zed_parser_source],
    include_dirs=[os.path.join('pyhead','zed')]
)

#-----------------------------------------------------------------------------
# Main setup
#-----------------------------------------------------------------------------

setup(
    name = "pyhead",
    version = "0.1",
    packages = ['pyhead'],
    ext_modules = [ryan, zed],
    author = "Nicholas Piël",
    author_email = "nicholas@nichol.as",
    description = "Python bindings for different HTTP parsers",
    license = "MIT",
    cmdclass = cmdclass
)
