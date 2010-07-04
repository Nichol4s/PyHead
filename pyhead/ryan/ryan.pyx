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
    res = <object>parser.data
    res.message_done = False
    return 0

cdef int on_message_complete_cb(http_parser *parser):
    res = <object>parser.data
    res.message_done = True
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
    res = <object>parser.data
    pystr = PyString_FromStringAndSize(at, length)
    res.last_body_part = pystr
    return 0

cdef void set_dict_value(http_parser * parser, key, char *valstr, size_t length):
    value = PyString_FromStringAndSize(valstr, length)
    res = <object>parser.data
    env = res.environ
    env[ key ] = env.get(key, '') + value


cdef int on_header_field_cb(http_parser *parser, char *at, size_t length):
    header_field = PyString_FromStringAndSize(at, length)
    res = <object>parser.data
    if res.state_is_value:
        res.last_header_field = ''
        res.state_is_value = False
    res.last_header_field += header_field
    return 0

cdef int on_header_value_cb(http_parser *parser, char *at, size_t length):
    res = <object>parser.data
    env = res.environ
    header_value = PyString_FromStringAndSize(at, length)
    env[ res.last_header_field ] = env.get( res.last_header_field, '') + header_value
    res.state_is_value = True
    return 0

cdef int on_headers_complete_cb(http_parser *parser):
    res = <object>parser.data
    res.headers_done = True
    return 0

#------------------------------------------------------------------------------
# Code
#------------------------------------------------------------------------------


class ParseResult(object):
    """ A container to collect the parsed results """

    def __init__(self):

        self.headers_done = False
        self.message_done = False

        self.last_header_field = ''
        self.last_body_part = ''
        self.state_is_value = False

        self.environ = {}


cdef class Parser:

    cdef http_parser parser
    cdef http_parser_settings parser_settings
    cdef int rc
    cdef dict environ
    cdef char* latest_header
    cdef bool message_finished
    cdef object result

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
        self.reset()


    def reset(self):
        # Point to data
        self.result = ParseResult()
        self.environ = self.result.environ
        self.parser.data = <void *>self.result

    def execute(self, pybuf):
        cdef char *data
        cdef size_t datalen

        rc = PyBytes_AsStringAndSize(pybuf, <char **>&data, <Py_ssize_t *>&datalen)
        if rc == -1:
            raise TypeError("Specified object does not provide ByteArray interace")
        return http_parser_execute(&self.parser, &self.parser_settings, data, datalen)

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


    def get_environ(self):
        self._setup_wsgi_environ()
        return self.environ

    def get_version(self):
        return (self.parser.http_major, self.parser.http_minor)

    def get_method(self):
        return http_method_str(<http_method>self.parser.method)

    def get_status_code(self):
        return self.parser.status_code

    def get_last_body(self):
        last_body = self.result.last_body_part
        self.result.last_body_part = ''
        return last_body

    def is_keepalive(self):
        return http_should_keep_alive(&self.parser)

    def is_upgrade(self):
        return self.parser.upgrade

    def is_message_done(self):
        return self.result.message_done

    def is_header_done(self):
        return self.result.headers_done

