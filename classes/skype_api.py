import sys
import json

import requests

from classes.auth_service import AuthService
from classes import utils


class SkypeApi:

    ACTIVITY_MESSAGE = 'message'
    ACTIVITY_ATTACHMENT = 'attachment'
    ACTIVITY_CONTACTRELATIONUPDATE = 'contactRelationUpdate'
    ACTIVITY_CONVERSATIONUPDATE = 'conversationUpdate'

    def __init__(self, config: dict):
        self.config = config
        self.token = ''
        self.authservice = AuthService(config)
        self.contact_list = []
        self.chatrooms = []
        self._savedata_fn = '_cache/skype_savedata.json'
        self.load_savedata()

    def save_data(self):
        with open(self._savedata_fn, mode='wt', encoding='utf-8') as f:
            json_obj = {
                'contacts': self.contact_list,
                'chats': self.chatrooms
            }
            f.write(json.dumps(json_obj, sort_keys=True, indent=4))
            print('SkypeAPI: saved savedata')

    def load_savedata(self):
        with open(self._savedata_fn, mode='rt', encoding='utf-8') as f:
            s = f.read()
            json_obj = json.loads(s, encoding='utf-8')
            if type(json_obj) == dict:
                self.contact_list = json_obj['contacts']
                self.chatrooms = json_obj['chats']
                print('SkypeAPI: loaded savedata OK')
            else:
                sys.stderr.write('SkypeAPI: error reading savedata!\n')

    def refresh_token(self):
        self.token = self.authservice.get_token()

    def get_my_skype_full_bot_id(self):
        return '28:' + self.config['BOT_ID']

    def handle_webhook_event(self, event_dict: dict):
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
        print('{0}: activity={1}, from:{2} => to:{3}'.format(
            a_time, a_activity, a_from, a_to))
        if a_activity == self.ACTIVITY_MESSAGE:
            self.send_message(a_from, 'Well, hello there!')

    def send_message(self, to: str, message: str):
        self.token = self.authservice.get_token()
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
