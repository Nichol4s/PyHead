
import os
import re
import urlparse

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import pyhead

from body import ChunkedReader, LengthReader, EOFReader, Body

class Message(object):
    def __init__(self, unreader):
        self.unreader = unreader
        self.version = None
        self.headers = []
        self.trailers = []
        self.body = None

        self.hdrre = re.compile("[\x00-\x1F\x7F()<>@,;:\[\]={} \t\\\\\"]")

        unused = self.parse(self.unreader)
        self.unreader.unread(unused)
        self.set_body_reader()
    
    def parse(self):
        raise NotImplementedError()

    def parse_headers(self, data):
        headers = []
        lines = []
        while len(data):
            pos = data.find("\r\n")
            if pos < 0:
                lines.append(data)
                data = ""
            else:
                lines.append(data[:pos+2])
                data = data[pos+2:]
        while len(lines):
            # Parse initial header name : value pair.
            curr = lines.pop(0)
            if curr.find(":") < 0:
                raise InvalidHeader(curr.strip())
            name, value = curr.split(":", 1)
            name = name.rstrip(" \t")
            if self.hdrre.search(name):
                raise InvalidHeaderName(name)
            name, value = name.strip(), [value.lstrip()]
            
            # Consume value continuation lines
            while len(lines) and lines[0].startswith((" ", "\t")):
                value.append(lines.pop(0))
            value = ''.join(value).rstrip()
            
            headers.append((name, value))
        return headers

    def set_body_reader(self):

        chunked = False
        clength = None

        for (name, value) in self.headers:
            if name.upper() == "CONTENT-LENGTH":
                try:
                    clength = int(value)
                except ValueError:
                    clenth = None
            elif name.upper() == "TRANSFER-ENCODING":
                chunked = value.lower() == "chunked"
        
        if chunked:
            self.body = Body(ChunkedReader(self, self.unreader))
        elif clength is not None:
            self.body = Body(LengthReader(self.unreader, clength))
        else:
            self.body = Body(EOFReader(self.unreader))

    def should_close(self):
        for (h, v) in self.headers:
            if h.lower() == "connection":
                if v.lower().strip() == "close":
                    return True
                elif v.lower().strip() == "keep-alive":
                    return False
        return self.version <= (1, 0)


class Request(Message):
    def __init__(self, unreader):
        self.methre = re.compile("[A-Z0-9$-_.]{3,20}")
        self.versre = re.compile("HTTP/(\d+).(\d+)")
    
        self.method = None
        self.uri = None
        self.scheme = None
        self.host = None
        self.port = 80
        self.path = None
        self.query = None
        self.fragment = None


        super(Request, self).__init__(unreader)

    
    def get_data(self, unreader):
        data = unreader.read()
        if not data:
            raise StopIteration()
        return data
    
    def parse(self, unreader):


        buf = StringIO()

        hdrp = pyhead.Parser(flavour=pyhead.RYAN)
        body = ""
        while True:
            pd = self.get_data(unreader)
            #mystr = buf.getvalue()
            #print "buffer", buf.getvalue()
            body += hdrp.parse(pd)
            result = hdrp
            # Header part done
            if hdrp.headers_done:
                self.method = result.method
                self.uri = result.uri
                self.scheme = result.scheme
                self.host = result.host
                self.port = result.port
                self.path = result.path
                self.query = result.query
                self.fragment = result.fragment
                self.version = result.version
            if hdrp.message_done:
                self.body = Body(body)
                self.headers = result.test_headers
                self.trailers = []
                return ""

    def set_body_reader(self):
        pass

class Response(Message):
    def __init__(self, unreader):
        self.code = None
        self.status = None

        super(Response, self).__init__(unreader)
    
    def parse(self):
        raise NotImplemented()

