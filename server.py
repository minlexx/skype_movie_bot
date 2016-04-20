#!/usr/bin/python3-utf8
import sys
import time
import ssl
import http.server
import threading
import configparser
import socketserver
import signal
import json
import time

# check if all 3rd party libraries are installed
try:
    import mako
except ImportError:
    sys.stderr.write('Error: python library "mako" template engine not found!\n')
    sys.stderr.write('Try the foolowing: pip3 install mako, or equivalent\n')
    sys.exit(1)

try:
    import requests
except ImportError:
    sys.stderr.write('Error: python library "requests" not found!\n')
    sys.stderr.write('Try the foolowing: pip3 install requests, or equivalent\n')
    sys.exit(1)

try:
    import certifi
except ImportError:
    sys.stderr.write('Error: python library "certifi" not found!\n')
    sys.stderr.write('Try the foolowing: pip3 install certifi, or equivalent\n')
    sys.exit(1)

try:
    import tweepy
except ImportError:
    sys.stderr.write('Error: python library "tweepy" not found!\n')
    sys.stderr.write('Try the foolowing: pip3 install tweepy, or equivalent\n')
    sys.exit(1)


from classes.skype_api import SkypeApi
from classes.request_handler import MovieBotRequestHandler
from classes.twitter_service import TwitterService


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
        self.twitter = TwitterService(self.config)
        self.skype.twitter = self.twitter
        #
        # twitter saved state
        self._twitter_check_timeout_sec = 15 * 60  # 15 mins
        self._twitter_savedata_fn = '_cache/twitter_savedata.json'
        self._posted_tweets = []
        self._skype_send_queue = []
        self.load_posted_tweets()

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
        self.config['TWITTER_CONSUMER_KEY'] = ''
        self.config['TWITTER_CONSUMER_SECRET'] = ''
        self.config['TWITTER_ACCESS_TOKEN'] = ''
        self.config['TWITTER_ACCESS_TOKEN_SECRET'] = ''
        self.config['TWITTER_USER_TIMELINE'] = ''
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
        if self._cfg.has_section('twitter'):
            if 'app_consumer_key' in self._cfg['twitter']:
                self.config['TWITTER_CONSUMER_KEY'] = self._cfg['twitter']['app_consumer_key']
            if 'app_consumer_secret' in self._cfg['twitter']:
                self.config['TWITTER_CONSUMER_SECRET'] = self._cfg['twitter']['app_consumer_secret']
            if 'app_access_token' in self._cfg['twitter']:
                self.config['TWITTER_ACCESS_TOKEN'] = self._cfg['twitter']['app_access_token']
            if 'app_access_token_secret' in self._cfg['twitter']:
                self.config['TWITTER_ACCESS_TOKEN_SECRET'] = self._cfg['twitter']['app_access_token_secret']
            if 'user_timeline' in self._cfg['twitter']:
                self.config['TWITTER_USER_TIMELINE'] = self._cfg['twitter']['user_timeline']

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

    def load_posted_tweets(self):
        try:
            with open(self._twitter_savedata_fn, mode='rt', encoding='utf-8') as f:
                s = f.read()
                json_object = json.loads(s, encoding='utf-8')
                self._posted_tweets = json_object['posted_tweets']
                print('Loaded {0} posted tweets.'.format(len(self._posted_tweets)))
        except OSError:
            pass

    def save_posted_tweets(self):
        try:
            with open(self._twitter_savedata_fn, mode='wt', encoding='utf-8') as f:
                f.write(json.dumps({'posted_tweets': self._posted_tweets}, sort_keys=True, indent=4))
        except OSError:
            pass

    def get_bb_videos_from_twitter(self):
        bbvids = self.twitter.get_bb_videos(25)
        if len(bbvids) < 1:
            return
        for bbv in bbvids:
            if bbv['tweet_id'] not in self._posted_tweets:
                self._skype_send_queue.append(bbv)
        print('{0} new vids to be sent of {1} loaded tweets.'.format(
            len(self._skype_send_queue), len(bbvids)))

    def post_videos_to_skype(self):
        if len(self._skype_send_queue) < 1:
            return
        # merge all new videos tweets into one skype message
        # to avoid flooding
        message = ''
        for bbv in self._skype_send_queue:
            self._posted_tweets.append(bbv['tweet_id'])  # remember posted tweet
            message += '{0} - {1}\n'.format(bbv['title'], bbv['url'])
        if len(message) > 0:
            # remove trailing newline
            message = message[:-1]
            self.skype.broadcast_to_chatrooms(message)
        # clear send queue and save posted tweets
        self._skype_send_queue = []
        self.save_posted_tweets()

    def SIGTERM_received(self):
        self.skype.save_data()
        self.save_posted_tweets()

    # background thread function
    def run(self):
        print('BG Thread started')
        print('BG Thread: authorize to Microsoft services...')
        self.skype.refresh_token()
        #
        last_action_time = int(time.time())
        # wait 5 seconds before checking twitter and posting to skype
        last_action_time -= self._twitter_check_timeout_sec + 5
        #
        while not self.user_shutdown_request:
            time.sleep(1)
            # maybe do some work...?
            cur_time = int(time.time())
            if (cur_time - last_action_time) >= self._twitter_check_timeout_sec:
                print('...time to check twitter...')
                last_action_time = cur_time
                self.get_bb_videos_from_twitter()
                self.post_videos_to_skype()
        #
        # we've received shutdown request, so we must stop HTTP server now
        print('BG Thread: shutting down http server')
        self._is_shutting_down = True
        self.shutdown()
        print('BG Thread: ending')
        return


if __name__ == '__main__':
    srv = MovieBotService()


    def sighandler_SIGTERM(sig, frame_object):
        print('Got termination signal, saving and stopping')
        srv.SIGTERM_received()
        sys.exit(0)

    if sys.platform == 'linux':
        signal.signal(signal.SIGTERM, sighandler_SIGTERM)

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
