import sys
import json

import requests


class SkypeApi:
    def __init__(self):
        self.token = ''

    def set_token(self, t: str):
        self.token = t

    def skype_send_message(self, to: str, message: str):
        # token = self.authservice.get_token()
        if self.token == '':
            sys.stderr.write('MovieBotService: cannot send message without OAuth2 token!\n')
            return False
        api_host = 'apis.skype.com'
        url = 'https://{0}/v2/conversations/{1}/activities'.format(api_host, to)
        postdata = {
            'message': {
                'content': message
            }
        }
        postdata_e = json.dumps(postdata)
        r = requests.post(url, data=postdata_e, headers={'Authorization': 'Bearer ' + self.token})
        print('API response status code:', r.status_code)
        return True
