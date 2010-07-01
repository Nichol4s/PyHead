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

import urlparse
import _ryan
import _zed


# The possible parsers
ZED = 0
RYAN = 1
KAZUHO = 2

class Parser(object):

    def __init__(self, flavour=ZED):
        if flavour == ZED:
            self.parser = _zed.Parser()
        elif flavour == RYAN:
            self.parser = _ryan.Parser()
        #else:
            #self.parser = _

    def reset(self):
        ''' Resets the state of the parser'''
        self.parser.reset()

    def parse(self, pystr):
        return self.parser.execute(pystr)

    @property
    def environ(self):
        return self.parser.get_environ()

    @property
    def method(self):
        try:
            return self.environ['REQUEST_METHOD']
        except KeyError:
            return None

    @property
    def uri(self):
        try:
            return self.environ['REQUEST_URI']
        except KeyError:
            return None

    @property
    def server(self):
        try:
            return self.environ['Server']
        except KeyError:
            return None

    @property
    def scheme(self):
        #XXX to be implemented
        return

    @property
    def host(self):
        return self.environ.get('SERVER_NAME', None)

    @property
    def port(self):
        return self.environ.get('SERVER_PORT', None)

    @property
    def path(self):
        return self.environ.get('PATH_INFO', None)

    @property
    def query(self):
        return self.environ.get('QUERY_STRING', None)

    @property
    def fragment(self):
        return self.environ.get('FRAGMENT', None)

    @property
    def version(self):
        return self.parser.get_version()

    @property
    def test_headers(self):
        h = []
        for k,v in self.environ.items():
            if k not in ['FRAGMENT', 'BODY', 'pyhead_done', 'CONTENT_LENGTH', 'SERVER_PROTOCOL', 'REQUEST_METHOD', 'QUERY_STRING', 'PATH_INFO', 'wsgi_input', 'REQUEST_URI', 'HEADER_DONE', 'SERVER_NAME', 'SERVER_PORT']:
                h.append( (k,v) ) 
        return h

    @property
    def body(self):
        try:
            #return self.environ['HEADER_DONE']
            return self.parser.get_body()
        except KeyError:
            return ''
        #return self.environ['wsgi_input']

    @property
    def is_finished(self):
        return self.parser.is_finished()

    @property
    def mesg_done(self):
        return self.parser.message_done()



