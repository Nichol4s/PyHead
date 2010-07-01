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

#------------------------------------------------------------------------------
# Imports
#------------------------------------------------------------------------------

import os
from stdlib cimport *
from python_bytes cimport PyBytes_AsStringAndSize
from python_string cimport PyString_FromStringAndSize, PyString_FromFormat
from python_dict cimport PyDict_SetItem
import struct



#------------------------------------------------------------------------------
# Header files
#------------------------------------------------------------------------------

cdef extern from "errno.h":
    int errno

cdef extern from "unistd.h" nogil:
    ctypedef signed off_t

cdef extern from "http_parser.h" nogil:

    cdef enum http_method:
        HTTP_DELETE, HTTP_GET, HTTP_HEAD, HTTP_POST, HTTP_PUT,
        HTTP_CONNECT, HTTP_OPTIONS, HTTP_TRACE,
        HTTP_COPY, HTTP_LOCK, HTTP_MKCOL, HTTP_PROPFIND, HTTP_PROPPATCH, HTTP_UNLOCK,
        HTTP_REPORT, HTTP_MKACTIVITY, HTTP_CHECKOUT, HTTP_MERGE

    cdef enum http_parser_type:
        HTTP_REQUEST, HTTP_RESPONSE, HTTP_BOTH

    struct http_parser:
        # Read only properties
        short http_major
        short http_minor
        short status_code
        char method
        char upgrade
        # Public (point to connection)
        void *data

    ctypedef int (*http_cb)(http_parser*)
    ctypedef int (*http_data_cb)(http_parser*, char *at, size_t length)

    struct http_parser_settings:
        http_cb      on_message_begin
        http_data_cb on_path
        http_data_cb on_query_string
        http_data_cb on_url
        http_data_cb on_fragment
        http_data_cb on_header_field
        http_data_cb on_header_value
        http_cb      on_headers_complete
        http_data_cb on_body
        http_cb      on_message_complete

    int http_parser_init(   http_parser *parser,
                            http_parser_type)
    size_t http_parser_execute( http_parser *parser,
                                http_parser_settings *settings,
                                char *data,
                                size_t len)

    int http_should_keep_alive(http_parser *parser)
    char* http_method_str(http_method)


#------------------------------------------------------------------------------
# Callacks
#------------------------------------------------------------------------------

cdef int on_message_begin_cb(http_parser *parser):
    d = <dict>parser.data
    d['pyhead_done'] = False
    return 0

cdef int on_message_complete_cb(http_parser *parser):
    d = <dict>parser.data
    d['pyhead_done'] = True
    return 0


cdef int on_path_cb(http_parser *parser, char *at, size_t length):
    set_dict_value(parser, 'PATH_INFO', at, length)
    return 0

cdef int on_query_string_cb(http_parser *parser, char *at, size_t length):
    set_dict_value(parser, 'QUERY_STRING', at, length)
    return 0

cdef int on_url_cb(http_parser *parser, char *at, size_t length):
    set_dict_value(parser, 'REQUEST_URI', at, length)
    return 0

cdef int on_fragment_cb(http_parser *parser, char *at, size_t length):
    set_dict_value(parser, 'FRAGMENT', at, length)
    return 0

cdef int on_body_cb(http_parser *parser, char *at, size_t length):
    set_dict_value(parser, 'BODY', at, length)
    return 0

cdef void set_dict_value(http_parser * parser, key, char *valstr, size_t length):
    value = PyString_FromStringAndSize(valstr, length)
    d = <dict>parser.data
    d[key] = d.get(key, '') + value


cdef int on_header_field_cb(http_parser *parser, char *at, size_t length):
    header_field = PyString_FromStringAndSize(at, length)
    d = <dict>parser.data
    if 'last_header_field' in d and d['last_header_value'] and d['last_header_field'] != header_field:
        d[ d['last_header_field'] ] = d['last_header_value']
        d[ 'last_header_field' ] = header_field
        d[ 'last_header_value' ] = ""
    else:
        d['last_header_field'] = d.get('last_header_field', '') + header_field
        d['last_header_value'] = ''
    return 0

cdef int on_header_value_cb(http_parser *parser, char *at, size_t length):
    d = <dict>parser.data
    header_value = PyString_FromStringAndSize(at, length)
    d['last_header_value'] += header_value
    return 0

cdef int on_headers_complete_cb(http_parser *parser):
    d = <dict>parser.data
    if 'last_header_field' in d:
        d[ d['last_header_field'] ] = d.get('last_header_value', '')
        del d['last_header_field']
        if 'last_header_value' in d:
            del d['last_header_value']
    return 0

#------------------------------------------------------------------------------
# Code
#------------------------------------------------------------------------------

cdef class Parser:

    cdef http_parser parser
    cdef http_parser_settings parser_settings
    cdef int rc
    cdef dict environ
    cdef char* latest_header
    cdef bool message_finished

    def __cinit__(self):

        # Set up parsers settings
        self.parser_settings.on_path = <http_data_cb>on_path_cb
        self.parser_settings.on_query_string = <http_data_cb>on_query_string_cb
        self.parser_settings.on_url = <http_data_cb>on_url_cb
        self.parser_settings.on_fragment = <http_data_cb>on_fragment_cb
        self.parser_settings.on_body = <http_data_cb>on_body_cb
        self.parser_settings.on_header_field = <http_data_cb>on_header_field_cb
        self.parser_settings.on_header_value = <http_data_cb>on_header_value_cb

        self.parser_settings.on_message_begin = <http_cb>on_message_begin_cb
        self.parser_settings.on_message_complete = <http_cb>on_message_complete_cb
        self.parser_settings.on_headers_complete = <http_cb>on_headers_complete_cb

        http_parser_init( &self.parser, HTTP_BOTH)
        # Point to self
        self.environ = dict()
        self.parser.data = <void *>self.environ

    def execute(self, pybuf):
        cdef char *data
        cdef size_t datalen
        rc = PyBytes_AsStringAndSize(pybuf, <char **>&data, <Py_ssize_t *>&datalen)
        if rc == -1:
            raise TypeError("Specified object does not provide ByteArray interace")
        rval = http_parser_execute(&self.parser, &self.parser_settings, data, datalen)
        if self.environ.get('pyhead_done', False):
            self.message_finished = True
        self._setup_wsgi_environ()
        return rval

    def _setup_wsgi_environ(self):
        env = self.environ
        # Manual fixxes
        env['REQUEST_METHOD'] = self.get_method()
        try:
            idx = env['Server'].rfind('/') + 1
            env['SERVER_NAME'], env['SERVER_PORT'] = env['Server'][idx:].split(':')
        except KeyError:
            pass
        env['SERVER_PROTOCOL'] = 'HTTP/%s.%s' % (self.get_version())
        env['HTTP_VERSION'] = env['SERVER_PROTOCOL']
        env.pop('pyhead_done')
        # Convert client provided headers
        for key in env.keys():
            if key.startswith('HTTP_'):
                env[key.split(':')[0].upper().replace('-', '_')] = env.pop(key)

    def get_environ(self):
        return self.environ

    def get_version(self):
        return (self.parser.http_major, self.parser.http_minor)

    def get_method(self):
        return http_method_str(<http_method>self.parser.method)

    def get_status_code(self):
        return self.parser.status_code

    def is_keepalive(self):
        return http_should_keep_alive(&self.parser)

    def is_upgrade(self):
        return self.parser.upgrade

    def message_done(self):
        return self.message_finished

    def get_body(self):
        return self.environ['BODY']



