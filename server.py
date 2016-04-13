#!/usr/bin/python3-utf8
import sys
import os
import time
import ssl
import http.server
import threading
import configparser
import socketserver
import datetime
import json

# check 3rd party libraries
try:
    import mako
except ImportError:
    sys.stderr.write('ImportError: Mako template engine not found!\n')
    sys.stderr.write('Try the foolowing: pip3 install mako, or equivalent\n')

try:
    import requests
except ImportError:
    sys.stderr.write('ImportError: requests not found!\n')
    sys.stderr.write('Try the foolowing: pip3 install requests, or equivalent\n')

from classes.template_engine import TemplateEngine
from classes.auth_service import AuthService
from classes import utils


ACTIVITY_MESSAGE = 'message'
ACTIVITY_ATTACHMENT = 'attachment'
ACTIVITY_CONTACTRELATIONUPDATE = 'contactRelationUpdate'
ACTIVITY_CONVERSATIONUPDATE = 'conversationUpdate'


# HTTP Request handler. New object is created for each new request
class MovieBotRequestHandler(http.server.BaseHTTPRequestHandler):
    #
    # - self.client_address is a tuple(host, port)
    # - self.headers is an instance of email.message.Message (or a derived class)
    #   containing the header information;
    # - self.rfile is a file object open for reading positioned at the
    #   start of the optional input data part;
    # - self.wfile is a file object open for writing.

    def __init__(self, request, client_address, server):
        # to make PyCharm happy
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
            '/shutdown': self.handle_shutdown,
            '/webhook_chat': self.handle_webhook_chat
        }

    # factory method to create template engine and assign default variables to it
    def create_template_engine(self) -> TemplateEngine:
        tmpl = TemplateEngine(self.server.get_template_engine_config())
        # default variables
        tmpl.assign('server', self.server)
        return tmpl

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
            # print('Found handler, calling', str(handler_function))
            ret = handler_function()
            return ret
        print('Cannot find handler for url: ' + str(self.path))
        return False

    # return False if not static file was requested (guess by file name/ext)
    # return True if file was served
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
            self.send_header('Content-Length', len(contents))
            if self.server.user_shutdown_request or self.server.is_shutting_down():
                self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(contents)
        except IOError:
            self._404_not_found()
        return True

    def serve_html(self, template_file: str):
        tmpl = self.create_template_engine()
        html = tmpl.render(template_file, expose_errors=True)
        # Mako can sometimes return 'bytes' instead of 'str' directly here...
        # UGLY FIX IT
        # also you should encode template files in UTF-8 with BOM (Byte Order Mark)
        html_enc = html
        if type(html) == str:
            # if the result is 'str' (unicode), we must convert it to 'bytes'
            html_enc = html.encode(encoding='utf-8')
        #
        self.content_type = 'text/html; charset=utf-8'
        self.send_response(200)
        self.send_header('Content-Type', self.content_type)
        self.send_header('Content-Length', len(html_enc))
        if self.server.user_shutdown_request or self.server.is_shutting_down():
            self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(html_enc)
        return True

    def _404_not_found(self):
        message = 'Not found: ' + str(self.path)
        message_enc = message.encode(encoding='utf-8')
        #
        self.send_response(404)
        self.send_header('Content-Type', self.content_type)
        self.send_header('Content-Length', len(message_enc))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(message_enc)
        self.wfile.flush()

    def _301_redirect(self, location: str, content: str=None):
        message = content
        if message is None:
            message = 'Location: <a href="' + str(location) + '">link</a>'
        message_enc = message.encode(encoding='utf-8')
        #
        self.send_response(301)  # moved permanently
        self.send_header('Location', str(location))
        self.send_header('Content-Type', self.content_type)
        self.send_header('Content-Length', len(message_enc))
        if self.server.user_shutdown_request or self.server.is_shutting_down():
            self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(message_enc)

    def _201_created(self):
        self.content_type = 'application/json; charset=utf-8'
        self.send_response(201)  # created
        self.send_header('Content-Type', self.content_type)
        self.send_header('Content-Length', 0)
        if self.server.user_shutdown_request or self.server.is_shutting_down():
            self.send_header('Connection', 'close')
        self.end_headers()

    def handle_webroot(self):
        self._301_redirect('/status')
        return True

    def handle_status(self):
        return self.serve_html('status.html')

    def handle_shutdown(self):
        message = 'Bot will be shut down!'
        self._301_redirect('/status', content=message)
        self.server.user_shutdown_request = True
        return True

    def handle_webhook_chat(self):
        """
        Outgoing webhooks are how Bots get notifications about new messages
        and other events. When your Bot registers via the Bot portal,
        you provide a HTTPS callback URL used by Skype Bot API for notifications.

        All messages are sent as POST requests to the Bot callback URL in JSON format

        Supported notifications are:
        - New message notification
          The message sent to the Bot (1:1 or via Conversation).
        - New attachment notification
          The attachment sent to Bot (1:1 or via Conversation).
        - Conversation event
          Notifications are sent in case:
          - Members are added or removed from the conversation.
          - The conversation's topic name changed.
          - The conversation's history is disclosed or hidden.
        - A contact was added to or removed from the Bot's contact list.

        Response from Bot Post requests
        The expected response is a “201 Created” without body content.
        Redirects will be ignored. Operations will time out after 5 seconds.
        :return:
        """
        if self.request_method != 'POST':
            sys.stderr.write('Webhook called not with POST method!\n')
            # self._404_not_found()
            self.send_response(405)  # Method Not Allowed
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', '0')
            self.send_header('Connection', 'close')
            self.end_headers()
            return True
        #
        # also we should check peer certificate here
        # it should be issued to skype.com :)
        if self.server.config['USE_HTTPS']:
            # self.request should be instance of ssl.SSLSocket
            if isinstance(self.request, ssl.SSLSocket):
                cert = self.request.getpeercert()
                if cert is None:  # no certificate was provided
                    sys.stderr.write('Webhook access without a certificate! Deny!\n')
                    self.send_response(403)  # 403 Forbidden
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Length', '0')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    return True
                if type(cert) == dict:
                    # If the certificate was not validated, the dict is empty
                    if len(cert) == 0:
                        sys.stderr.write('Webhook access with an invalid certificate! Deny!\n')
                        self.send_response(403)  # 403 Forbidden
                        self.send_header('Content-Type', 'application/json; charset=utf-8')
                        self.send_header('Content-Length', '0')
                        self.send_header('Connection', 'close')
                        self.end_headers()
                        return True
                print(cert)  # lol
            else:
                sys.stderr.write('Something is strange, self.rwquest is not an SSL Socket?!\n')
        #
        postdata_str = ''
        json_object = None
        #
        # first of all I want to log all requests
        with open('_cache/log_webhook.txt', mode='at', encoding='utf-8') as f:
            f.write('headers:\n')
            for hh1 in self.headers.keys():
                f.write('{0}: {1}\n'.format(hh1, self.headers[hh1]))
            f.write('\n')
            #
            content_length = -1
            if 'content-length' in self.headers:
                try:
                    content_length = int(self.headers['content-length'])
                except ValueError:
                    f.write('Failed to convert Content-Length header to int: ' + str(
                        self.headers['content-length']))
            if content_length == -1:
                f.write('Content length is unknown! Cannot dump POST data contents!\n')
            else:
                bytes_object = b''  # empty bytes array
                try:
                    bytes_object = self.rfile.read(content_length)
                    if type(bytes_object) == bytes:
                        postdata_str = bytes_object.decode(encoding='utf-8', errors='strict')
                        # try to parse JSON here
                        try:
                            json_object = json.loads(postdata_str, encoding='utf-8')
                        except json.JSONDecodeError as jde:
                            sys.stderr.write('Failed to decode JSON in POST data:\n')
                            sys.stderr.write(str(jde) + '\n')
                            json_object = None
                        # finally log what skype server has sent us
                        # if it is not JSON, log simple string
                        if json_object is None:
                            f.write(postdata_str)
                        else:
                            # if this is JSON, pretty print formatted JSON to log
                            f.write(json.dumps(json_object, sort_keys=True, indent=4) + '\n')
                        f.write('\n')
                    else:
                        f.write('Unexpected type of postdata received: {0}\n'.format(
                            str(type(bytes_object))))
                except IOError:
                    f.write('IOError occured while trying to read POST data!\n')
                except UnicodeDecodeError:
                    f.write('POST data cannot be represented as string, showing raw bytes:\n')
                    f.write('<' + str(bytes_object) + '>\n')
            f.write('--------------------------------------------------\n')
        #
        # after loggigng, process the request
        if (postdata_str != '') and (json_object is not None):
            # All webhooks are called with JSON - formatted bodies (array
            # or JSON objects). Every JSON object indicates some update
            # and has the set of common fields.
            # Convert possible sinle object to a list of objects
            if type(json_object) == dict:
                json_object = [json_object]
            if type(json_object) == list:
                for event_dict in json_object:
                    # common attributes for all events: from, to, time, activity
                    a_from = ''
                    a_to = ''
                    a_time = ''
                    a_activity = ''
                    if 'from' in event_dict:
                        a_from = event_dict['from']
                    if 'to' in event_dict:
                        a_to = event_dict['to']
                    if 'time' in event_dict:
                        a_time = utils.parse_skype_datetime(event_dict['time'])
                    if 'activity' in event_dict:
                        a_activity = event_dict['activity']
                    # output to console!
                    print('{0}: activity={1}, from:{2} => to:{3}\n'.format(
                        a_time, a_activity, a_from, a_to))
                    pass
            else:
                # unexpected type for a json object received! it should be a list (JSON Array)
                sys.stderr.write('Unexpected type on JSON object was received: ' +
                                 str(type(json_object)))
        #
        # default reply to skype API server - 201 Created.
        # This indicates that callback URL was successfully executed
        self._201_created()
        return True


# First, inherit from ThreadingMixIn, so that its threaded process_request()
# method overrides default synchronous from HTTPServer (TCPServer)
class MovieBotService(socketserver.ThreadingMixIn, http.server.HTTPServer, threading.Thread):
    def __init__(self):
        #
        # first of all, load config
        self._cfg = configparser.ConfigParser()
        self.config = dict()
        self.load_config()
        self._server_address = (self.config['BIND_ADDRESS'], self.config['BIND_PORT'])
        self._is_shutting_down = False
        #
        # Now, explicitly initialize both parent classes
        http.server.HTTPServer.__init__(self, self._server_address, MovieBotRequestHandler)
        threading.Thread.__init__(self, daemon=False)
        #
        # wrap server socket to SSL, if HTTPS was enabled
        if self.config['USE_HTTPS'] and (self.config['SSL_CERT'] != '') \
                and (self.config['SSL_KEY'] != ''):
            self.socket = ssl.wrap_socket(self.socket,
                                          keyfile=self.config['SSL_KEY'],
                                          certfile=self.config['SSL_CERT'],
                                          server_side=True)
        #
        self.server_version = 'MovieBot/1.0'
        self.user_shutdown_request = False
        self.name = 'MovieBotService'
        self.daemon = False
        #
        if len(self.server_address) == 2:
            proto = 'http'
            if self.config['USE_HTTPS']:
                proto = 'https'
            print('{0} listening at {1}://{2}:{3}'.format(
                self.server_version, proto, self.config['BIND_ADDRESS'], self.config['BIND_PORT']))
        #
        self.authservice = AuthService(self.config)

    def load_config(self):
        # fill in the defaults
        self.config['BIND_ADDRESS'] = '0.0.0.0'
        self.config['BIND_PORT'] = 8000
        self.config['USE_HTTPS'] = False
        self.config['SSL_CERT'] = ''
        self.config['SSL_KEY'] = ''
        self.config['TEMPLATE_DIR'] = 'html'
        self.config['TEMPLATE_CACHE_DIR'] = '_cache/html'
        self.config['APP_ID'] = ''
        self.config['APP_SECRET'] = ''
        # read config
        success_list = self._cfg.read('conf/bot.conf', encoding='utf-8')
        if 'conf/bot.conf' not in success_list:
            sys.stderr.write('Failed to read config file: conf/bot.conf!\n')
        # get values from config
        if self._cfg.has_section('server'):
            if 'bind_address' in self._cfg['server']:
                self.config['BIND_ADDRESS'] = str(self._cfg['server']['bind_address'])
            if 'bind_port' in self._cfg['server']:
                self.config['BIND_PORT'] = int(self._cfg['server']['bind_port'])
            if 'https' in self._cfg['server']:
                iuse_https = int(self._cfg['server']['https'])
                if iuse_https != 0:
                    self.config['USE_HTTPS'] = True
            if 'ssl_cert' in self._cfg['server']:
                self.config['SSL_CERT'] = str(self._cfg['server']['ssl_cert'])
            if 'ssl_key' in self._cfg['server']:
                self.config['SSL_KEY'] = str(self._cfg['server']['ssl_key'])
        if self._cfg.has_section('html'):
            if 'templates_dir' in self._cfg['html']:
                self.config['TEMPLATE_DIR'] = self._cfg['html']['templates_dir']
            if 'templates_cache_dir' in self._cfg['html']:
                self.config['TEMPLATE_CACHE_DIR'] = self._cfg['html']['templates_cache_dir']
        if self._cfg.has_section('app'):
            if 'app_id' in self._cfg['app']:
                self.config['APP_ID'] = self._cfg['app']['app_id']
            if 'app_secret' in self._cfg['app']:
                self.config['APP_SECRET'] = self._cfg['app']['app_secret']

    def is_shutting_down(self):
        return self._is_shutting_down

    def get_template_engine_config(self) -> dict:
        ret = {
            'TEMPLATE_DIR': self.config['TEMPLATE_DIR'],
            'TEMPLATE_CACHE_DIR': self.config['TEMPLATE_CACHE_DIR'],
        }
        return ret

    # background thread function
    def run(self):
        print('BG Thread started')
        print('BG Thread: authorize to Microsoft services...')
        self.authservice.get_token()
        #
        # wait..
        while not self.user_shutdown_request:
            time.sleep(1)
        #
        # we've received shutdown request, so we must stop HTTP server now
        print('BG Thread: shutting down http server')
        self._is_shutting_down = True
        self.shutdown()
        print('BG Thread: ending')
        return


if __name__ == '__main__':
    srv = MovieBotService()

    # start BG thread
    srv.start()

    # start http server
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        # Ctrl+C was pressed, now HTTP server is stopped,
        # stop also BG Thread then
        srv.user_shutdown_request = True

    print('{0}: stopped.'.format(srv.name))
