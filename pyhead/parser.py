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

from cStringIO import StringIO
import _ryan
import _zed


# The possible parsers
ZED = 0
RYAN = 1
KAZUHO = 2


class Parser(object):

    def __init__(self, flavour=ZED):

        self.consumer = None
        self.cached_body = None
        self.rbuf = ReadBuffer(self.recv)

        if flavour == ZED:
            self.parser = _zed.Parser()
        elif flavour == RYAN:
            self.parser = _ryan.Parser()
        #else:
            #self.parser = _

    def reset(self):
        ''' Resets the state of the parser'''
        self.cached_body = None
        self.parser.reset()

    def set_consumer(self, function):
        """ This will set a data feeder
            and exposes parsed data as a filelike object
        """
        self.consumer = function

    def set_continue_cb(self, function):
        """ Make sure that the 100-contue callback
            is being called on the first read attempt.
        """
        self.rbuf.continue_cb = function


    def extract_headers(self):
        """ This will read the headers
        """
        self.reset()
        while not self.headers_done:
            # XXX: Could add some security checks here
            #        * Max header size
            #        * Timeout?
            data = self.consumer( 1024 )
            if data == '':
                return False
            self.parser.execute(data)

        # Headers are done
        return data

    def recv(self, *args, **kwargs):
        """ This will excute function with provided
            arguments and parse the returned information
        """
        self.parser.execute(self.consumer(*args, **kwargs))
        return self.parser.get_last_body()

    def consume(self, size=None):
        return self.rbuf.read(size)

    def parse(self, pystr):
        """ This is a somewhat a hack to feed
            manual strings to the parser, it is
            not intended to be used like this.
        """
        def consumer_end(*args, **kwargs):
            return ''
        def consumer(*args, **kwargs):
            self.consumer = consumer_end
            return pystr
        self.consumer = consumer
        return self.consume()

    @property
    def environ(self):
        env = self.parser.get_environ()
        env['wsgi.input'] = self.rbuf
        return env

    @property
    def body(self):
        """ The body property acts a bit different,
            since the body is actually stored a ReadBuffer
            in wsgi.input, reading it once will wipe the 
            buffer. However, accessing this property will
            cache the result so you can xs it multiple times.
        """
        if self.cached_body == None:
            self.cached_body = self.rbuf.read()
        return self.cached_body


    #### Below you will only find simple properties

    @property
    def method(self):
        return self.environ.get('REQUEST_METHOD', None)

    @property
    def uri(self):
        return self.environ.get('REQUEST_URI', None)

    @property
    def server(self):
        return self.environ.get('Server', None)

    @property
    def scheme(self):
        #XXX to be implemented
        return

    @property
    def host(self):
        return self.environ.get('Host', None)

    @property
    def port(self):
        #return self.environ.get('SERVER_PORT', None)
        return 80

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
            if k not in ['FRAGMENT', 'CONTENT_LENGTH', 'SERVER_PROTOCOL', 'REQUEST_METHOD', 'QUERY_STRING', 'PATH_INFO', 'wsgi_input', 'wsgi.input', 'REQUEST_URI', 'SERVER_NAME', 'SERVER_PORT', 'HTTP_VERSION']:
                h.append( (k,v) )
        return h

    @property
    def message_done(self):
        return self.parser.is_message_done()

    @property
    def headers_done(self):
        return self.parser.is_header_done()



class ReadBuffer(object):
    """Code adapted from _fileobj in
       Python 2.6 socket module"""

    default_bufsize = 8192

    def __init__(self, reader, bufsize=-1):
        self.reader = reader
        self.continue_cb = None

        if bufsize < 0:
            bufsize = self.default_bufsize

        self.bufsize = bufsize

        # _rbufsize is the suggested recv buffer size.  It is *strictly*
        # obeyed within readline() for recv calls.  If it is larger than
        # default_bufsize it will be used for recv calls within read().
        if bufsize == 0:
            self._rbufsize = 1
        elif bufsize == 1:
            self._rbufsize = self.default_bufsize
        else:
            self._rbufsize = bufsize

        # We use StringIO for the read buffer to avoid holding a list
        # of variously sized string objects which have been known to
        # fragment the heap due to how they are malloc()ed and often
        # realloc()ed down much smaller than their original allocation.
        self._rbuf = StringIO()

    def read(self, size=-1):
        # A read attempt, fire the 100-continue callback
        if self.continue_cb:
            self.continue_cb()
        # Use max, disallow tiny reads in a loop as they are very inefficient.
        # We never leave read() with any leftover data from a new recv() call
        # in our internal buffer.
        rbufsize = max(self._rbufsize, self.default_bufsize)
        # Our use of StringIO rather than lists of string objects returned by
        # recv() minimizes memory usage and fragmentation that occurs when
        # rbufsize is large compared to the typical return value of recv().
        buf = self._rbuf
        buf.seek(0, 2)  # seek end
        if size < 0:
            # Read until EOF
            self._rbuf = StringIO()  # reset _rbuf.  we consume it via buf.
            while True:
                data = self.reader(rbufsize)
                if not data:
                    break
                buf.write(data)
            return buf.getvalue()
        else:
            # Read until size bytes or EOF seen, whichever comes first
            buf_len = buf.tell()
            if buf_len >= size:
                # Already have size bytes in our buffer?  Extract and return.
                buf.seek(0)
                rv = buf.read(size)
                self._rbuf = StringIO()
                self._rbuf.write(buf.read())
                return rv

            self._rbuf = StringIO()  # reset _rbuf.  we consume it via buf.
            while True:
                left = size - buf_len
                # recv() will malloc the amount of memory given as its
                # parameter even though it often returns much less data
                # than that.  The returned data string is short lived
                # as we copy it into a StringIO and free it.  This avoids
                # fragmentation issues on many platforms.
                data = self.reader(left)
                if not data:
                    break
                n = len(data)
                if n == size and not buf_len:
                    # Shortcut.  Avoid buffer data copies when:
                    # - We have no data in our buffer.
                    # AND
                    # - Our call to recv returned exactly the
                    #   number of bytes we were asked to read.
                    return data
                if n == left:
                    buf.write(data)
                    del data  # explicit free
                    break
                assert n <= left, "recv(%d) returned %d bytes" % (left, n)
                buf.write(data)
                buf_len += n
                del data  # explicit free
                #assert buf_len == buf.tell()
            return buf.getvalue()

    def readline(self, size=-1):
        # A read attempt, fire the 100-continue callback
        if self.continue_cb:
            self.continue_cb()
        buf = self._rbuf
        buf.seek(0, 2)  # seek end
        if buf.tell() > 0:
            # check if we already have it in our buffer
            buf.seek(0)
            bline = buf.readline(size)
            if bline.endswith('\n') or len(bline) == size:
                self._rbuf = StringIO()
                self._rbuf.write(buf.read())
                return bline
            del bline
        if size < 0:
            # Read until \n or EOF, whichever comes first
            if self._rbufsize <= 1:
                # Speed up unbuffered case
                buf.seek(0)
                buffers = [buf.read()]
                self._rbuf = StringIO()  # reset _rbuf.  we consume it via buf.
                data = None
                recv = self.reader
                while data != "\n":
                    data = recv(1)
                    if not data:
                        break
                    buffers.append(data)
                return "".join(buffers)

            buf.seek(0, 2)  # seek end
            self._rbuf = StringIO()  # reset _rbuf.  we consume it via buf.
            while True:
                data = self.reader(self._rbufsize)
                if not data:
                    break
                nl = data.find('\n')
                if nl >= 0:
                    nl += 1
                    buf.write(data[:nl])
                    self._rbuf.write(data[nl:])
                    del data
                    break
                buf.write(data)
            return buf.getvalue()
        else:
            # Read until size bytes or \n or EOF seen, whichever comes first
            buf.seek(0, 2)  # seek end
            buf_len = buf.tell()
            if buf_len >= size:
                buf.seek(0)
                rv = buf.read(size)
                self._rbuf = StringIO()
                self._rbuf.write(buf.read())
                return rv
            self._rbuf = StringIO()  # reset _rbuf.  we consume it via buf.
            while True:
                data = self.reader(self._rbufsize)
                if not data:
                    break
                left = size - buf_len
                # did we just receive a newline?
                nl = data.find('\n', 0, left)
                if nl >= 0:
                    nl += 1
                    # save the excess data to _rbuf
                    self._rbuf.write(data[nl:])
                    if buf_len:
                        buf.write(data[:nl])
                        break
                    else:
                        # Shortcut.  Avoid data copy through buf when returning
                        # a substring of our first recv().
                        return data[:nl]
                n = len(data)
                if n == size and not buf_len:
                    # Shortcut.  Avoid data copy through buf when
                    # returning exactly all of our first recv().
                    return data
                if n >= left:
                    buf.write(data[:left])
                    self._rbuf.write(data[left:])
                    break
                buf.write(data)
                buf_len += n
                #assert buf_len == buf.tell()
            return buf.getvalue()

    def readlines(self, sizehint=0):
        total = 0
        list = []
        while True:
            line = self.readline()
            if not line:
                break
            list.append(line)
            total += len(line)
            if sizehint and total >= sizehint:
                break
        return list

    # Iterator protocols

    def __iter__(self):
        return self

    def next(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line

