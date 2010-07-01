# Copyright 2009 Paul J. Davis <paul.joseph.davis@gmail.com>
#
# This file is part of the pywebmachine package released
# under the MIT license.

import inspect
import os
import random
import re
import sys
import urlparse

from parser import RequestParser

dirname = os.path.dirname(__file__)
random.seed()

def uri(data):
    ret = {"raw": data}
    parts = urlparse.urlparse(data)
    ret["scheme"] = parts.scheme or None
    ret["host"] = parts.netloc.rsplit(":", 1)[0] or None
    ret["port"] = parts.port or 80
    if parts.path and parts.params:
        ret["path"] = ";".join([parts.path, parts.params])
    elif parts.path:
        ret["path"] = parts.path
    elif parts.params:
        # Don't think this can happen
        ret["path"] = ";" + parts.path
    else:
        ret["path"] = None
    ret["query"] = parts.query or None
    ret["fragment"] = parts.fragment or None
    return ret

class request(object):
    def __init__(self, name, expect):
        self.name = name
        self.fname = os.path.join(dirname, "data", "requests", name)
        with open(self.fname) as handle:
            self.data = handle.read()
        self.data = self.data.replace("\n", "").replace("\\r\\n", "\r\n")
        self.expect = expect
        if not isinstance(self.expect, list):
            self.expect = [self.expect]

    # Functions for sending data to the parser.
    # These functions mock out reading from a
    # socket or other data source that might
    # be used in real life.

    def send_all(self):
        yield self.data

    def send_lines(self):
        lines = self.data
        pos = lines.find("\r\n")
        while pos > 0:
            yield lines[:pos+2]
            lines = lines[pos+2:]
            pos = lines.find("\r\n")
        if len(lines):
            yield lines

    def send_bytes(self):
        for d in self.data:
            yield d
    
    def send_random(self):
        maxs = len(self.data) / 10
        read = 0
        while read < len(self.data):
            chunk = random.randint(1, maxs)
            yield self.data[read:read+chunk]
            read += chunk                

    # These functions define the sizes that the
    # read functions will read with.

    def size_all(self):
        return -1
    
    def size_bytes(self):
        return 1
    
    def size_small_random(self):
        return random.randint(0, 2)
    
    def size_random(self):
        return random.randint(1, 4096)

    # Match a body against various ways of reading
    # a message. Pass in the request, expected body
    # and one of the size functions.

    def szread(self, func, sizes):
        sz = sizes()
        data = func(sz)
        if sz >= 0 and len(data) > sz:
            raise AssertionError("Read more than %d bytes: %s" % (sz, data))
        return data

    def match_read(self, req, body, sizes):
        data = self.szread(req.body.read, sizes)
        count = 1000   # XXX old value
        while len(body):
            if body[:len(data)] != data:
                raise AssertionError("Invalid body data read: %r != %r" % (
                                        data, body[:len(data)]))
            body = body[len(data):]
            data = self.szread(req.body.read, sizes)
            if not data:
                count -= 1
            if count <= 0:
                raise AssertionError("Unexpected apparent EOF")

        if len(body):
            raise AssertionError("Failed to read entire body: %r" % body)
        elif len(data):
            raise AssertionError("Read beyond expected body: %r" % data)        
        data = req.body.read(sizes())
        if data:
            raise AssertionError("Read after body finished: %r" % data)

    def match_readline(self, req, body, sizes):
        data = self.szread(req.body.readline, sizes)
        count = 1000
        while len(body):
            if body[:len(data)] != data:
                raise AssertionError("Invalid data read: %r" % data)
            if '\n' in data[:-1]:
                raise AssertionError("Embedded new line: %r" % data)
            body = body[len(data):]
            data = self.szread(req.body.readline, sizes)
            if not data:
                count -= 1
            if count <= 0:
                raise AssertionError("Apparent unexpected EOF")
        if len(body):
            raise AssertionError("Failed to read entire body: %r" % body)
        elif len(data):
            raise AssertionError("Read beyond expected body: %r" % data)        
        data = req.body.readline(sizes())
        if data:
            raise AssertionError("Read data after body finished: %r" % data)

    def match_readlines(self, req, body, sizes):
        """\
        This skips the sizes checks as we don't implement it.
        """
        data = req.body.readlines()

        for line in data:
            if '\n' in line[:-1]:
                raise AssertionError("Embedded new line: %r" % line)
            if line != body[:len(line)]:
                raise AssertionError("Invalid body data read: %r != %r" % (
                                                    line, body[:len(line)]))
            body = body[len(line):]
        #if len(body):
            #raise AssertionError("Failed to read entire body: %r" % body)
        data = req.body.readlines(sizes())
        if data:
            raise AssertionError("Read data after body finished: %r" % data)
    
    def match_iter(self, req, body, sizes):
        """\
        This skips sizes because there's its not part of the iter api.
        """
        for line in req.body:
            if '\n' in line[:-1]:
                raise AssertionError("Embedded new line: %r" % line)
            if line != body[:len(line)]:
                raise AssertionError("Invalid body data read: %r != %r" % (
                                                    line, body[:len(line)]))
            body = body[len(line):]
        #if len(body):
            #raise AssertionError("Failed to read entire body: %r" % body)
        try:
            data = iter(req.body).next()
            raise AssertionError("Read data after body finished: %r" % data)
        except StopIteration:
            pass

    # Construct a series of test cases from the permutations of
    # send, size, and match functions.
    
    def gen_cases(self):
        def get_funs(p):
            return [v for k, v in inspect.getmembers(self) if k.startswith(p)]
        senders = get_funs("send_")
        sizers = get_funs("size_")
        matchers = get_funs("match_")
        cfgs = [
            (mt, sz, sn)
            for mt in matchers
            for sz in sizers
            for sn in senders
        ]
        # Strip out match_readlines, match_iter for all but one sizer
        cfgs = [
            (mt, sz, sn)
            for (mt, sz, sn) in cfgs
            if mt in [self.match_readlines, self.match_iter]
            and sz != self.size_all
            or mt not in [self.match_readlines, self.match_iter]
        ]
        
        ret = []
        for (mt, sz, sn) in cfgs:
            mtn = mt.func_name[6:]
            szn = sz.func_name[5:]
            snn = sn.func_name[5:]
            def test_req(sn, sz, mt):
                self.check(sn, sz, mt)
            desc = "%s: MT: %s SZ: %s SN: %s" % (self.name, mtn, szn, snn)
            test_req.description = desc
            ret.append((test_req, sn, sz, mt))
        return ret

    def check(self, sender, sizer, matcher):
        cases = self.expect[:]
        ended = False
        try:
            p = RequestParser(sender())
        except Exception, e:
            if not isinstance(cases[0], Exception):
                raise
            self.same_error(e, cases[0])
            eq(len(casese), 1)
        while True:
            try:
                req = p.next()
            except StopIteration, e:

                eq(len(cases), 0)
                ended = True
                break
            except Exception, e:
                raise
                if not isinstance(cases[0], Exception):
                    raise
                self.same_error(e, cases.pop(0))
            else:
                self.same(req, sizer, matcher, cases.pop(0))
        eq(len(cases), 0)
        eq(ended, True)

    def same(self, req, sizer, matcher, exp):
        if isinstance(req, Exception):
            self.same_error(req, exp)
        else:
            self.same_obj(req, sizer, matcher, exp)
    
    def same_error(self, req, exp):
        istype(req, Exception)
        istype(exp, Exception)
        istype(req, exp)
    
    def same_obj(self, req, sizer, matcher, exp):
        eq(req.method, exp["method"])
        eq(req.uri, exp["uri"]["raw"])
        eq(req.scheme, exp["uri"]["scheme"])
        eq(req.host, exp["uri"]["host"])
        eq(req.port, exp["uri"]["port"])
        eq(req.path, exp["uri"]["path"])
        eq(req.query, exp["uri"]["query"])
        eq(req.fragment, exp["uri"]["fragment"])
        eq(req.version, exp["version"])
        eq(sorted(req.headers), sorted(exp["headers"]))
        matcher(req, exp["body"], sizer)
        #eq(req.body, exp["body"])
        eq(req.trailers, exp.get("trailers", []))

def eq(a, b):
    assert a == b, "%r != %r" % (a, b)

def ne(a, b):
    assert a != b, "%r == %r" % (a, b)

def lt(a, b):
    assert a < b, "%r >= %r" % (a, b)

def gt(a, b):
    assert a > b, "%r <= %r" % (a, b)

def isin(a, b):
    assert a in b, "%r is not in %r" % (a, b)

def isnotin(a, b):
    assert a not in b, "%r is in %r" % (a, b)

def has(a, b):
    assert hasattr(a, b), "%r has no attribute %r" % (a, b)

def hasnot(a, b):
    assert not hasattr(a, b), "%r has an attribute %r" % (a, b)

def istype(a, b):
    assert isinstance(a, b), "%r is not an instance of %r" % (a, b)

def raises(exctype, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except exctype, inst:
        pass
    else:
        func_name = getattr(func, "func_name", "<builtin_function>")
        fmt = "Function %s did not raise %s"
        raise AssertionError(fmt % (func_name, exctype.__name__))

