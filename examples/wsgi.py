# Copyright (c) 2005-2009, eventlet contributors
# Copyright (c) 2009-2010, gevent contributors

import errno
import sys
import time
import traceback
import mimetools
from datetime import datetime
from urllib import unquote

import pyhead

from stop import socketq as socket
from stop.server import StreamServer

#from gevent import socket
#import gevent
#from gevent.server import StreamServer


__all__ = ['WSGIHandler', 'WSGIServer']


MAX_REQUEST_LINE = 8192

# Weekday and month names for HTTP date/time formatting; always English!
_WEEKDAYNAME = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTHNAME = [None, # Dummy so we can use 1-based month numbers
              "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


_INTERNAL_ERROR_STATUS = '500 Internal Server Error'
_INTERNAL_ERROR_BODY = 'Internal Server Error'
_INTERNAL_ERROR_HEADERS = [('Content-Type', 'text/plain'),
                           ('Connection', 'close'),
                           ('Content-Length', str(len(_INTERNAL_ERROR_BODY)))]
_REQUEST_TOO_LONG_RESPONSE = "HTTP/1.0 414 Request URI Too Long\r\nConnection: close\r\nContent-length: 0\r\n\r\n"
_BAD_REQUEST_RESPONSE = "HTTP/1.0 400 Bad Request\r\nConnection: close\r\nContent-length: 0\r\n\r\n"

_CONTINUE_RESPONSE = "HTTP/1.1 100 Continue\r\n\r\n"

def format_date_time(timestamp):
    year, month, day, hh, mm, ss, wd, _y, _z = time.gmtime(timestamp)
    return "%s, %02d %3s %4d %02d:%02d:%02d GMT" % (_WEEKDAYNAME[wd], day, _MONTHNAME[month], year, hh, mm, ss)



class WSGIHandler(object):
    protocol_version = 'HTTP/1.1'
    MessageClass = mimetools.Message

    def __init__(self, socket, address, server):
        self.socket = socket
        self.client_address = address
        self.server = server

        self.keep_alive = True
        self.close_connection = False
        self.send_continue = False
        self.application = self.server.application

        # Set up parser
        self.parser = pyhead.Parser(flavour=pyhead.RYAN)
        self.parser.set_consumer(self.socket.recv)
        self.parser.set_continue_cb(self._send_100_continue)

        self.rfile = self.parser.rbuf
        #self.wfile = socket.makefile('wb', 0)
        

    def _send_100_continue(self):
        if self.send_continue:
            self.write(_CONTINUE_RESPONSE)
            #self.socket.sendall(_CONTINUE_RESPONSE)
            self.send_continue = False

    def handle(self):
        try:

            while not self.close_connection:

                self.time_start = time.time()
                self.time_finish = 0
                self.response_length = 0
                #self.parser.reset()
                result = self.parser.extract_headers()
                self.set_environ()

                if result is False:        # Client closed connection
                    break
                elif result is True:       # Serve regular request 
                    try:
                        #print "   ---> sending"
                        t = time.time()
                        self.handle_one_response()
                        e = time.time()
                        #print "   ---> sent", e-t
                    except socket.error, ex:
                        # Broken pipe, connection reset by peer
                        if ex[0] in (errno.EPIPE, errno.ECONNRESET):
                            sys.exc_clear()
                            break
                        else:
                            raise
                    #self.close_connection = True
                else:                      # Error in request
                    self.status, response_body = result
                    #self.wfile.write(_BAD_REQUEST_RESPONSE)
                    self.socket.qsend(_BAD_REQUEST_RESPONSE) 
                    #self.log_request()
                    break
        except socket.error, ex:
            if ex[0] in (errno.EPIPE, errno.ECONNRESET, errno.EBADF):
                print "WSGI Caught:", ex
                sys.exc_clear()
            else:
                raise ex
        finally:
            self.socket.close(wait=True)
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                pass
            except socket.error:
                # Ignore socket.shutdown error
                sys.exc_clear()
            self.__dict__.pop('socket', None)
            self.__dict__.pop('rfile', None)
            self.__dict__.pop('wfile', None)
            self.__dict__.pop('environ', None)
            self.__dict__.pop('parser', None)
            self.__dict__.pop('content_length', None)
            self.__dict__.pop('request_version', None)


    def log_error(self, msg, *args):
        try:
            message = msg % args
        except Exception:
            traceback.print_exc()
            message = '%r %r' % (msg, args)
            sys.exc_clear()
        try:
            message = '%s: %s' % (self.socket, message)
        except Exception:
            sys.exc_clear()
        try:
            sys.stderr.write(message + '\n')
        except Exception:
            traceback.print_exc()
            sys.exc_clear()

    def write(self, data):
        towrite = []
        if not self.status:
            raise AssertionError("The application did not call start_response()")
        if not self.headers_sent:
            if hasattr(self.result, '__len__') and 'Content-Length' not in self.response_headers_list:
                self.response_headers.append(('Content-Length', str(sum(len(chunk) for chunk in self.result))))
                self.response_headers_list.append('Content-Length')

            if 'Date' not in self.response_headers_list:
                self.response_headers.append(('Date', format_date_time(time.time())))
                self.response_headers_list.append('Date')

            if self.request_version == 'HTTP/1.0' and 'Connection' not in self.response_headers_list:
                self.response_headers.append(('Connection', 'close'))
                self.response_headers_list.append('Connection')
                self.close_connection = True
            elif ('Connection', 'close') in self.response_headers:
                self.close_connection = True

            if data and self.request_version != 'HTTP/1.0' and 'Content-Length' not in self.response_headers_list:
                self.response_use_chunked = True
                self.response_headers.append(('Transfer-Encoding', 'chunked'))
                self.response_headers_list.append('Transfer-Encoding')

            towrite.append('%s %s\r\n' % (self.request_version, self.status))
            for header in self.response_headers:
                towrite.append('%s: %s\r\n' % header)

            towrite.append('\r\n')
            self.headers_sent = True

        if data:
            if self.response_use_chunked:
                ## Write the chunked encoding
                towrite.append("%x\r\n%s\r\n" % (len(data), data))
            else:
                towrite.append(data)

        #self.wfile.writelines(towrite)
        for i in towrite:
            self.socket.qsend(i)
        self.response_length += sum(len(x) for x in towrite)

    def start_response(self, status, headers, exc_info=None):
        if exc_info:
            try:
                if self.headers_sent:
                    # Re-raise original exception if headers sent
                    raise exc_info[0], exc_info[1], exc_info[2]
            finally:
                # Avoid dangling circular ref
                exc_info = None
        self.status = status
        self.response_headers = [('-'.join([x.capitalize() for x in key.split('-')]), value) for key, value in headers]
        self.response_headers_list = [x[0] for x in self.response_headers]
        return self.write

    def log_request(self):
        log = self.server.log
        if log:
            #print type(log)
            print "logging:", self.format_request()
            #log.write(self.format_request() + '\n')

    def format_request(self):
        now = datetime.now().replace(microsecond=0)
        return '%s - - [%s] "%s" %s %s %.6f' % (
            self.client_address[0],
            now,
            self.requestline,
            (self.status or '000').split()[0],
            self.response_length,
            self.time_finish - self.time_start)

    def handle_one_response(self):
        self.time_start = time.time()
        self.status = None
        self.headers_sent = False

        self.result = None
        self.response_use_chunked = False
        self.response_length = 0
        try:
            try:
                self.result = self.application(self.environ, self.start_response)
                for data in self.result:
                    if data:
                        self.write(data)
                if self.status and not self.headers_sent:
                    self.write('')
                if self.response_use_chunked:
                    #self.wfile.writelines('0\r\n\r\n')
                    self.socket.qsend('0\r\n\r\n')
                    self.response_length += 5
            except Exception:
                traceback.print_exc()
                sys.exc_clear()
                try:
                    args = (getattr(self, 'server', ''),
                            getattr(self, 'requestline', ''),
                            getattr(self, 'client_address', ''),
                            getattr(self, 'application', ''))
                    msg = '%s: Failed to handle request:\n  request = %s from %s\n  application = %s\n\n' % args
                    sys.stderr.write(msg)
                except Exception:
                    sys.exc_clear()
                if not self.response_length:
                    self.start_response(_INTERNAL_ERROR_STATUS, _INTERNAL_ERROR_HEADERS)
                    self.write(_INTERNAL_ERROR_BODY)
        finally:
            self.parser.discard()
            if hasattr(self.result, 'close'):
                self.result.close()
            self.time_finish = time.time()
            self.log_request()

    @property
    def requestline(self):
        env = self.environ
        return env.get('REQUEST_METHOD','UNKNOWN'), env.get('PATH_INFO',''), env.get('HTTP_VERSION','')

    def set_environ(self):
        self.environ = self.server.get_environ()
        self.environ.update(self.parser.environ.copy())
        host, port = self.socket.getsockname()
        self.environ['SCRIPT_NAME'] = ''
        self.environ['SERVER_NAME'] = host
        self.environ['SERVER_PORT'] = str(port)
        self.environ['REMOTE_ADDR'] = self.client_address[0]
        self.environ['GATEWAY_INTERFACE'] = 'CGI/1.1'
        self.request_version = self.environ.get('HTTP_VERSION','?')
        if self.environ.get("HTTP_CONNECTION", "").lower() == 'close':
            self.close_connection = True

        if self.environ.get('HTTP_EXPECT') == '100-continue':
            self.send_continue = True


class WSGIServer(StreamServer):
    """A WSGI server based on :class:`StreamServer` that supports HTTPS."""

    handler_class = WSGIHandler
    base_env = {'GATEWAY_INTERFACE': 'CGI/1.1',
                'SERVER_SOFTWARE': 'Steve/0.1',
                'SCRIPT_NAME': '',
                'wsgi.version': (1, 0),
                'wsgi.multithread': False,
                'wsgi.multiprocess': False,
                'wsgi.run_once': False}

    def __init__(self, listener, application=None, backlog=None, spawn='default', log='default', handler_class=None,
                 environ=None, **ssl_args):
        StreamServer.__init__(self, listener, backlog=backlog, spawn=spawn, **ssl_args)
        if application is not None:
            self.application = application
        if handler_class is not None:
            self.handler_class = handler_class
        if log == 'default':
            self.log = sys.stderr
        else:
            self.log = log
        self.set_environ(environ)

    def set_environ(self, environ=None):
        if environ is not None:
            self.environ = environ
        environ_update = getattr(self, 'environ', None)
        self.environ = self.base_env.copy()
        if self.ssl_enabled:
            self.environ['wsgi.url_scheme'] = 'https'
        else:
            self.environ['wsgi.url_scheme'] = 'http'
        if environ_update is not None:
            self.environ.update(environ_update)
        if self.environ.get('wsgi.errors') is None:
            self.environ['wsgi.errors'] = sys.stderr

    def get_environ(self):
        return self.environ.copy()

    def pre_start(self):
        StreamServer.pre_start(self)
        if 'SERVER_NAME' not in self.environ:
            self.environ['SERVER_NAME'] = socket.getfqdn(self.server_host)
        self.environ.setdefault('SERVER_PORT', str(self.server_port))

    def handle(self, socket, address):
        handler = self.handler_class(socket, address, self)
        handler.handle()

def nb_sendfile(out_fd, in_fd, offset, count):
    total_sent = 0
    while total_sent < count:
        try:
            _offset, sent = original_sendfile(out_fd, in_fd, offset +
                    total_sent, count - total_sent)
            total_sent += sent
        except OSError, ex:
            if ex[0] == EAGAIN:
                wait_write(out_fd)
            else:
                raise
    return offset + total_sent, total_sent

class FileWrapper(object):
    # Look at: http://www.python.org/dev/peps/pep-0333/#optional-platform-specific-file-handling
    # "And here is a snippet"

    def __init__(self, fd, size=None):
        """docstring for __init__"""
        self.fd = fd

    def close(self):
        return self.fd.close()

    def read(self, *args, **kwargs):
        return self.fd.read(*args, **kwargs)

    def __iter__(self):
        # Actually send the file
        self.socket.sendall(fd.read())
        yield
