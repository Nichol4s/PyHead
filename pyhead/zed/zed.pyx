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

import cStringIO

#------------------------------------------------------------------------------
# Header files
#------------------------------------------------------------------------------

cdef extern from "errno.h":
    int errno

cdef extern from "unistd.h" nogil:
    ctypedef signed off_t

cdef extern from "http11_parser.h" nogil:

    ctypedef void (*element_cb)(void *data, char *at, size_t length)
    ctypedef void (*field_cb)(void *data, char *field, size_t flen, char *value, size_t vlen)

    struct http_parser "http_parser":
        int cs
        size_t body_start
        int content_len
        size_t nread
        size_t mark
        size_t field_start
        size_t field_len
        size_t query_start

        int socket_started
        int json_sent

        void *data

        field_cb http_field
        element_cb request_method
        element_cb request_uri
        element_cb fragment
        element_cb request_path
        element_cb query_string
        element_cb http_version
        element_cb header_done

    int http_parser_init(http_parser *parser)
    size_t http_parser_execute(http_parser *parser, char *data, size_t length, size_t dataoff)
    int http_parser_has_error(http_parser *parser)
    int http_parser_is_finished(http_parser *parser)


#------------------------------------------------------------------------------
# Callacks
#------------------------------------------------------------------------------

cdef void store_field_cb(void *data, char *field, size_t flen, char *value, size_t vlen):
    key = PyString_FromStringAndSize(field, flen)
    set_dict_value(data, key, value, vlen)

cdef void request_method_cb(void *data, char *buf, size_t buf_len):
    set_dict_value(data, 'REQUEST_METHOD', buf, buf_len)

cdef void request_uri_cb(void *data, char *buf, size_t buf_len):
    set_dict_value(data, 'REQUEST_URI', buf, buf_len)

cdef void fragment_cb(void *data, char *buf, size_t buf_len):
    set_dict_value(data, 'FRAGMENT', buf, buf_len)

cdef void request_path_cb(void *data, char *buf, size_t buf_len):
    set_dict_value(data, 'REQUEST_PATH', buf, buf_len)

cdef void query_string_cb(void *data, char *buf, size_t buf_len):
    set_dict_value(data, 'QUERY_STRING', buf, buf_len)

cdef void http_version_cb(void *data, char *buf, size_t buf_len):
    set_dict_value(data, 'HTTP_VERSION', buf, buf_len)

cdef void header_done_cb(void *data, char *buf, size_t buf_len):
    res = <object>data
    res.headers_done = True

cdef void set_dict_value(void * data, key, char *valstr, size_t length):
    value = PyString_FromStringAndSize(valstr, length)
    res = <object>data
    env = res.environ
    env[ key ] = env.get(key, '') + value

#------------------------------------------------------------------------------
# Code
#------------------------------------------------------------------------------


class ParseResult:

    def __init__(self):
        self.headers_done = False
        self.environ = {}

cdef class Parser:

    cdef http_parser parser
    cdef int rc
    cdef int idx
    cdef dict environ
    cdef str body
    cdef object results

    def __cinit__(self):
        self.parser.http_field = <field_cb>store_field_cb
        self.parser.request_method = <element_cb>request_method_cb
        self.parser.request_uri = <element_cb>request_uri_cb
        self.parser.fragment = <element_cb>fragment_cb
        self.parser.request_path = <element_cb>request_path_cb
        self.parser.query_string = <element_cb>query_string_cb
        self.parser.http_version = <element_cb>http_version_cb
        self.parser.header_done = <element_cb>header_done_cb
        self.reset()


    def reset(self):
        self.body = ""
        self.results = ParseResult()
        self.parser.data = <void *>self.results
        self.environ = self.results.environ
        http_parser_init( &self.parser )

    def execute(self, pybuf, parse_chunks=False):
        cdef char *data
        cdef size_t datalen
        rc = PyBytes_AsStringAndSize(pybuf, <char **>&data, <Py_ssize_t *>&datalen)
        if rc == -1:
            raise TypeError("Object does not provide ByteArray interace")
        self.idx = http_parser_execute(&self.parser, data, datalen, 0)
        self.body = pybuf[self.idx:]
        self._setup_wsgi_environ()
        # Zeds parser does not handle incoming chunks
        #      this is simply a check so it will raise
        #      an error when the incoming data is chunked
        if not parse_chunks:
            try:
                if self.environ['Transfer-Encoding'] == 'chunked':
                    raise NotImplementedError('Zed parser does not handle request chunking')
            except KeyError:
                pass
        return self.idx

    def _setup_wsgi_environ(self):
        env = self.environ
        # A few manual fixes
        env['PATH_INFO'] = env.pop('REQUEST_PATH', '')
        if env['PATH_INFO'] == '' and 'REQUEST_URI' in env and '?' in env['REQUEST_URI']:
            pidx = env['REQUEST_URI'].index('?')
            env['PATH_INFO'] = env['REQUEST_URI'][:pidx] 
        #env['CONTENT_TYPE'] = env.pop('Content-Type', '')
        #if 'Content-Length' in env:
            #env['CONTENT_LENGTH'] = env.pop('Content-Length')
        try:
            idx = env['Server'].rfind('/') + 1
            env['SERVER_NAME'], env['SERVER_PORT'] = env['Server'][idx:].split(':')
        except KeyError:
            pass
        try:
            env['SERVER_PROTOCOL'] = env.get('HTTP_VERSION')
        except KeyError:
            pass

        # The Raw Request URI should include the Fragment
        if env.get('FRAGMENT'):
            env['REQUEST_URI'] += '#' + env.get('FRAGMENT', '')


    def has_error(self):
        return http_parser_has_error(&self.parser)

    def is_header_done(self):
        #return http_parser_is_finished(&self.parser)
        return self.results.headers_done

    def is_message_done(self):
        return self.is_header_done()
        try:
            content_length = int(self.environ['Content-Length'])
        except KeyError:
            # No body content just look at the header
            return self.is_header_done()
        return self.is_header_done() and len(self.body) >= content_length

    def socket_started(self):
        return self.parser.socket_started

    def get_version(self):
        s =  self.environ['SERVER_PROTOCOL']
        return tuple([int(i) for i in s[-3:].split('.')])

    def json_sent(self):
        return self.parser.json_sent

    def get_environ(self):
        return self.environ

    def get_last_body(self):
        return self.body






