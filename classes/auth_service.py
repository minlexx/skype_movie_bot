import sys
import datetime
import threading

import requests
import requests.exceptions


class AuthService:
    def __init__(self, config: dict):
        self._app_id = config['APP_ID']
        self._app_secret = config['APP_SECRET']
        self._valid_until = datetime.datetime.utcnow()
        #
        self._oAuthScope = 'https://graph.microsoft.com/.default'
        self._oAuthUrl = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
        #
        self._lock = threading.Lock()
        #
        self.token = ''

    def get_token(self) -> str:
        self._lock.acquire()
        self.maybe_refresh_token()
        self._lock.release()
        return self.token

    def get_valid_until(self) -> datetime.datetime:
        return self._valid_until

    def get_token_short(self) -> str:
        if len(self.token) < 25:
            return self.token
        return self.token[0:10] + '...' + self.token[-10:]

    def maybe_refresh_token(self):
        #
        # check that appId has incorrect default value
        if self._app_id == '11111111-2222-3333-4444-666666666666':
            # this is a default value from default config
            # ignore it
            sys.stderr.write('AuthService: I cannot refresh token with '
                             'incorrect default app_id!\n')
            self.token = ''
            return
        #
        dt_unow = datetime.datetime.utcnow()
        if self._valid_until <= dt_unow:
            # time to refresh!
            print('AuthService: Time to refresh token!')
            self.do_refresh_token()
        else:
            print('AuthService: Token is still valid...')

    def do_refresh_token(self):
        try:
            sess = requests.session()
            postdata = {
                'client_id': self._app_id,
                'client_secret': self._app_secret,
                'grant_type': 'client_credentials',
                'scope': self._oAuthScope
            }
            r = sess.post(self._oAuthUrl, data=postdata)
            if r.status_code == 200:
                # save token response as json
                with open('_cache/token_response.json', mode='wt', encoding='utf-8') as f:
                    f.write(r.text)
                r_json = r.json()
                self.token = r_json['access_token']
                #
                print('AuthService: Got access token: ' + self.get_token_short())
                #
                expires_in = int(r_json['expires_in'])  # usually server gives 3600 seconds
                tdelta = datetime.timedelta(seconds=expires_in)
                self._valid_until = datetime.datetime.utcnow() + tdelta
                #
                print('AuthService:     Expires in: ' + str(expires_in))
                print('AuthService:     Valid until: ' + str(self._valid_until))
                #
                return True
            return False
        except requests.exceptions.RequestException:
            sys.stderr.write('AuthService: Error happened during refreshing token!\n')
            return False
