#!/usr/bin/python3-utf8
import sys
import os
import time
import ssl
import http.server
import threading
import configparser


class MovieBotRequestHandler(http.server.BaseHTTPRequestHandler):
    #
    # - self.client_address is a tuple(host, port)
    # - self.headers is an instance of email.message.Message (or a derived class)
    #   containing the header information;
    # - self.rfile is a file object open for reading positioned at the
    #   start of the optional input data part;
    # - self.wfile is a file object open for writing.

    def __init__(self, request, client_address, server):
        # to make pycharm happy
        self.content_type = ''
        self.request_method = ''
        self.routes = {}
        # setup() is called in superclass's __init__()
        # so, we need variable decalrations to be placed before super.__init__() call
        super(MovieBotRequestHandler, self).__init__(request, client_address, server)

    def setup(self):
        # need to call superclass's setup, it creates read/write files
        # self.rfile, self.wfile from incoming client connection socket
        super(MovieBotRequestHandler, self).setup()
        # pre-setup some vars
        self.server_version = self.server.server_version
        self.content_type = 'text/plain; charset=utf-8'  # default content_type
        self.protocol_version = 'HTTP/1.1'
        self.request_method = ''
        # routing table
        self.routes = {
            '/': self.handle_webroot,
            '/status': self.handle_status,
            '/shutdown' : self.handle_shutdown,
            '/command': self.handle_command
        }

    def do_GET(self):
        self.request_method = 'GET'
        # First, try to serve request as static file
        if self.serve_static_file():
            return
        # Try to find a proper resource handler
        if self.route_request():
            return
        # if we are here, routing failed
        self._404_not_found()

    def do_POST(self):
        self.request_method = 'POST'
        # Try to find a proper resource handler
        if self.route_request():
            return
        # if we are here, routing failed
        self._404_not_found()

    def route_request(self):
        if self.path in self.routes:
            handler_function = self.routes[self.path]
            print('Found handler, calling', str(handler_function))
            ret = handler_function()
            return ret
        return False
        # mname = 'do_' + 'zzz'
        # if not hasattr(self, mname):
        #    self.send_error(501, "Unsupported method (%r)" % self.command)
        #    return
        # method = getattr(self, mname)
        # method()

    # return False if not static file was requested (guess by file name/ext)
    def serve_static_file(self):
        is_static = False
        path = str(self.path)
        # check requested file name/ext
        if path == '/favicon.ico':
            is_static = True
            self.content_type = 'image/vnd.microsoft.icon'
        if not is_static:
            return False
        # try to open file
        try:
            f = open('.' + path, mode='rb')
            contents = f.read()
            f.close()

            self.send_response(200)
            self.send_header('Content-Type', self.content_type)
            self.send_header('Content-length', len(contents))
            self.end_headers()
            self.wfile.write(contents)
        except IOError:
            self._404_not_found()
        return True

    def _404_not_found(self):
        message = 'Not found: ' + str(self.path)
        #
        self.send_response(404)
        self.send_header('Content-Type', self.content_type)
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(message.encode('utf-8'))
        self.wfile.flush()

    def _301_redirect(self, location: str):
        self.send_response(301)  # moved permanently
        self.send_header('Location', str(location))
        self.send_header('Content-Type', self.content_type)
        self.end_headers()
        message = 'Location: <a href="' + str(location) + '">link</a>'
        self.wfile.write(message.encode('utf-8'))

    def handle_webroot(self):
        self._301_redirect('/status')
        return True

    def handle_status(self):
        self.send_response(200)
        self.send_header('Content-Type', self.content_type)
        self.send_header('Connection', 'close')
        self.end_headers()
        message = 'Status here'
        self.wfile.write(message.encode('utf-8'))
        return True

    def handle_command(self):
        return False

    def handle_shutdown(self):
        self.send_response(200)
        self.send_header('Content-Type', self.content_type)
        self.send_header('Connection', 'close')
        self.end_headers()
        message = 'Bot will be shut down!'
        self.wfile.write(message.encode('utf-8'))
        self.wfile.flush()
        # self.server.shutdown()
        self.server.user_shutdown_request = True
        return True


class MovieBotService(http.server.HTTPServer, threading.Thread):
    def __init__(self, server_address):
        # super(MovieBotService, self).__init__(server_address, MovieBotRequestHandler)
        http.server.HTTPServer.__init__(self, server_address, MovieBotRequestHandler)
        threading.Thread.__init__(self, daemon=False)
        #
        self.server_version = 'MovieBot/1.0'
        self.user_shutdown_request = False
        self.name = 'MovieBotService'
        self.daemon = False
        #
        if len(self.server_address) == 2:
            print('{0} listening @ {1}:{2}'.format(
                self.server_version,
                self.server_address[0],
                self.server_address[1]))

    def run(self):
        print('BG Thread started')
        while not self.user_shutdown_request:
            time.sleep(1)
        print('BG Thread: shutting down http server')
        self.shutdown()
        print('BG Thread: ending')
        return


if __name__ == '__main__':
    #
    # defaults
    #
    use_https = False
    bind_address = '0.0.0.0'
    bind_port = 8000
    ssl_cert = ''
    ssl_key = ''
    #
    # read config
    #
    cfg = configparser.ConfigParser()
    cfg.read('conf/bot.conf', encoding='utf-8')
    if cfg.has_section('server'):
        if 'bind_address' in cfg['server']:
            bind_address = str(cfg['server']['bind_address'])
        if 'bind_port' in cfg['server']:
            bind_port = int(cfg['server']['bind_port'])
        if 'https' in cfg['server']:
            iuse_https = int(cfg['server']['https'])
            if iuse_https != 0:
                use_https = True
        if 'ssl_cert' in cfg['server']:
            ssl_cert = str(cfg['server']['ssl_cert'])
        if 'ssl_key' in cfg['server']:
            ssl_key = str(cfg['server']['ssl_key'])
    #
    # create server object
    my_server_address = (bind_address, bind_port)
    srv = MovieBotService(my_server_address)

    # wrap server socket to SSL, if HTTPS was enabled
    if use_https and (ssl_cert != '') and (ssl_key != ''):
        srv.socket = ssl.wrap_socket(srv.socket, keyfile=ssl_key, certfile=ssl_cert, server_side=True)

    # start BG thread
    srv.start()

    # start http server
    srv.serve_forever()
