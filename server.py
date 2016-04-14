#!/usr/bin/python3-utf8
import sys
import time
import ssl
import http.server
import threading
import configparser
import socketserver

# check if all 3rd party libraries are installed
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

try:
    import certifi
except ImportError:
    sys.stderr.write('ImportError: certifi not found!\n')
    sys.stderr.write('Try the foolowing: pip3 install certifi, or equivalent\n')


from classes.skype_api import SkypeApi
from classes.request_handler import MovieBotRequestHandler


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
            cert_requirement = ssl.CERT_NONE  # do not require cert from peer
            ca_certificates = None            # no CA certs
            if self.config['VALIDATE_PEER_CERT']:
                cert_requirement = ssl.CERT_REQUIRED  # require cert from peer
                ca_certificates = certifi.where()     # look for CA certs here
            self.socket = ssl.wrap_socket(self.socket,
                                          keyfile=self.config['SSL_KEY'],
                                          certfile=self.config['SSL_CERT'],
                                          cert_reqs=cert_requirement,  # require cert from peer or not
                                          ca_certs=ca_certificates,    # where to look for CA certs
                                          server_side=True)
        #
        self.server_version = 'MovieBot/1.0'
        self.user_shutdown_request = False
        self.name = 'MovieBotService'
        self.daemon = False  # self's run() method is not daemon
        # ThreadingMixIn's request handler threads - daemons
        # we do not want child threads with HTTP/1.1 keep-alive connections
        # to prevent server from stopping
        self.daemon_threads = True
        #
        if len(self.server_address) == 2:
            proto = 'http'
            if self.config['USE_HTTPS']:
                proto = 'https'
            print('{0} listening at {1}://{2}:{3}'.format(
                self.server_version, proto, self.config['BIND_ADDRESS'], self.config['BIND_PORT']))
            print('  My Bot ID: {0}'.format(self.get_my_skype_full_bot_id()))
        #
        self.skype = SkypeApi(self.config)

    def load_config(self):
        # fill in the defaults
        self.config['BIND_ADDRESS'] = '0.0.0.0'
        self.config['BIND_PORT'] = 8000
        self.config['USE_HTTPS'] = False
        self.config['SSL_CERT'] = ''
        self.config['SSL_KEY'] = ''
        self.config['VALIDATE_PEER_CERT'] = False
        self.config['TEMPLATE_DIR'] = 'html'
        self.config['TEMPLATE_CACHE_DIR'] = '_cache/html'
        self.config['APP_ID'] = ''
        self.config['APP_SECRET'] = ''
        self.config['BOT_ID'] = ''
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
            if 'validate_peer_cert' in self._cfg['server']:
                ivalidate_peer_cert = int(self._cfg['server']['validate_peer_cert'])
                if ivalidate_peer_cert != 0:
                    self.config['VALIDATE_PEER_CERT'] = True
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
            if 'bot_id' in self._cfg['app']:
                self.config['BOT_ID'] = self._cfg['app']['bot_id']

    def is_shutting_down(self):
        return self._is_shutting_down

    def get_template_engine_config(self) -> dict:
        ret = {
            'TEMPLATE_DIR': self.config['TEMPLATE_DIR'],
            'TEMPLATE_CACHE_DIR': self.config['TEMPLATE_CACHE_DIR'],
        }
        return ret

    def get_my_skype_full_bot_id(self):
        return '28:' + self.config['BOT_ID']

    # background thread function
    def run(self):
        print('BG Thread started')
        print('BG Thread: authorize to Microsoft services...')
        self.skype.refresh_token()
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
