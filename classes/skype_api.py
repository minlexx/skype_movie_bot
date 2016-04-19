import sys
import json
import datetime
import re
import threading

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
        self.contact_list = {}
        self.twitter = None
        # ^^ format: key: skype_id
        #  self.contact_list['alexey.min'] = {'skypeid': 'alexey.min', 'displayname': 'Alexey Min'}
        self.chatrooms = []
        self._savedata_fn = '_cache/skype_savedata.json'
        self.load_savedata()
        # internal vars to handle events
        self._evt_from = ''
        self._evt_to = ''
        self._evt_time = datetime.datetime.utcnow()
        self._evt_activity = ''
        self._evt_dict = {}
        #
        # lock to guard message sending
        self._msg_lock = threading.Lock()

    def save_data(self):
        try:
            with open(self._savedata_fn, mode='wt', encoding='utf-8') as f:
                json_obj = {
                    'contacts': self.contact_list,
                    'chats': self.chatrooms
                }
                f.write(json.dumps(json_obj, sort_keys=True, indent=4))
                print('SkypeAPI: saved savedata')
        except OSError:
            pass

    def load_savedata(self):
        try:
            with open(self._savedata_fn, mode='rt', encoding='utf-8') as f:
                s = f.read()
                json_obj = json.loads(s, encoding='utf-8')
                if type(json_obj) == dict:
                    self.contact_list = json_obj['contacts']
                    self.chatrooms = json_obj['chats']
                    print('SkypeAPI: loaded savedata OK')
                else:
                    sys.stderr.write('SkypeAPI: error reading savedata!\n')
        except OSError:
            pass

    def refresh_token(self):
        self.token = self.authservice.get_token()

    def get_my_skype_full_bot_id(self):
        return '28:' + self.config['BOT_ID']

    def is_skypeid_user(self, s: str):
        return s.startswith('8:')

    def is_skypeid_conversation(self, s: str):
        return s.startswith('19:') and s.endswith('@thread.skype')

    def is_skypeid_me(self, s: str):
        return s == self.get_my_skype_full_bot_id()

    def strip_skypeid(self, s: str):
        """
        Converts "8:alexey.min" to "alexey.min"
        :param s: full skype ID as received in API callback
        :return: stripped skype ID without "numbers:" in front
        """
        m = re.match(r'\d+:(.+)', s)
        if m is not None:
            return m.group(1)
        return s

    def get_user_display_name(self, skypeid: str) -> str:
        stripped_skypeid = self.strip_skypeid(skypeid)
        if stripped_skypeid in self.contact_list:
            contact = self.contact_list[stripped_skypeid]
            return contact['displayname']
        # not in contacts
        return stripped_skypeid

    def handle_webhook_event(self, event_dict: dict):
        """
        Main entry point that receives all skype even callbacks
        :param event_dict: json objct that was received in POST request from MS server
        :return: nothing
        """
        # common attributes for all events: from, to, time, activity
        self._evt_dict = event_dict
        if 'from' in event_dict:
            self._evt_from = event_dict['from']
        if 'to' in event_dict:
            self._evt_to = event_dict['to']
        if 'time' in event_dict:
            self._evt_time = utils.parse_skype_datetime(event_dict['time'])
        if 'activity' in event_dict:
            self._evt_activity = event_dict['activity']
        # output to console!
        print('{0}: activity={1}, from:{2} => to:{3}'.format(
            self._evt_time, self._evt_activity, self._evt_from, self._evt_to))
        # run appropriate handler for each event type
        if self._evt_activity == self.ACTIVITY_MESSAGE:
            self.handle_message()
        elif self._evt_activity == self.ACTIVITY_ATTACHMENT:
            self.handle_attachment()
        elif self._evt_activity == self.ACTIVITY_CONTACTRELATIONUPDATE:
            self.handle_contactRelationUpdate()
        elif self._evt_activity == self.ACTIVITY_CONVERSATIONUPDATE:
            self.handle_conversationUpdate()
        else:
            sys.stderr.write('SkypeAPI: unhandled activity event received: '
                             '[{0}]\n'.format(self._evt_activity))

    def handle_message(self):
        """
        "activity": "message",
        "content": "\u0442\u0430\u043a, ...",
        "from": "8:alexey.min",
        "id": "1460608477678",
        "time": "2016-04-14T04:34:37.672Z",
        "to": "19:fced243ae1de407a8cfaff338c8f03fd@thread.skype"
        """
        message = ''
        message_id = ''
        if 'content' in self._evt_dict:
            message = self._evt_dict['content']
        if 'id' in self._evt_dict:
            message_id = self._evt_dict['id']
        #
        # direct user-to-me conversation
        if self.is_skypeid_user(self._evt_from) and self.is_skypeid_me(self._evt_to):
            skypeid_from = self.strip_skypeid(self._evt_from)
            display_name = self.get_user_display_name(skypeid_from)
            #
            if message.startswith('!resend '):
                to_resend = message[8:]
                if len(self.chatrooms) > 0:
                    print('Resending message from {0} to {1} chatrooms'.format(
                        skypeid_from, len(self.chatrooms)))
                    for chatroom in self.chatrooms:
                        self.send_message(chatroom, to_resend)
            elif message.startswith('!get_videos'):
                self.reply_bbvids(self._evt_from)
            else:
                self.send_message(self._evt_from,
                                  'Чего надо, {0}? Я пока не общаюсь '
                                  'в личке...'.format(display_name))
        #
        # user-to-groupchat conversation
        if self.is_skypeid_user(self._evt_from) and self.is_skypeid_conversation(self._evt_to):
            # I can handle some commands here
            if message == '!help':
                help_message = 'Я пока что умею только одну команду:\n !help - справка :)'
                self.send_message(self._evt_to, help_message)
            elif message == '!get_videos':
                self.reply_bbvids(self._evt_to)

    def reply_bbvids(self, reply_to: str):
        reply = ''
        bbvids = self.twitter.get_bb_videos(10)
        if len(bbvids) > 0:
            reply += '{0} results:\n'.format(len(bbvids))
            for vid in bbvids:
                reply += '{0} - {1}\n'.format(vid['title'], vid['url'])
        if reply != '':
            self.send_message(reply_to, reply)

    def handle_contactRelationUpdate(self):
        """
        "action": "add",  // (may be "remove")
        "activity": "contactRelationUpdate",
        "from": "8:alexey.min",
        "fromDisplayName": "Alexey Min",
        "time": "2016-04-13T10:08:04.939Z",
        "to": "28:980d8ae3-6300-4c1f-b021-4c50b35b0c6a"
        """
        action = ''
        from_display_name = ''
        if 'action' in self._evt_dict:
            action = self._evt_dict['action']
        if 'fromDisplayName' in self._evt_dict:
            from_display_name = self._evt_dict['fromDisplayName']
        if action == 'add':
            # yay! we've been added as a contact!
            cskypeid = self.strip_skypeid(self._evt_from)
            contact = {'skypeid': cskypeid, 'displayname': from_display_name}
            self.contact_list[cskypeid] = contact
            self.save_data()
            print('Yay! {0} ({1}) added me as contact!'.format(
                from_display_name, cskypeid))
        elif action == 'remove':
            cskypeid = self.strip_skypeid(self._evt_from)
            print('=( {0} removed me from contacts :('.format(cskypeid))
            if cskypeid in self.contact_list:
                del self.contact_list[cskypeid]
                self.save_data()

    def handle_conversationUpdate(self):
        """
        Example, user added me (bot) to a skype chat
        "activity": "conversationUpdate",
        "from": "8:alexey.min",
        "membersAdded": [
            "28:980d8ae3-6300-4c1f-b021-4c50b35b0c6a"
        ],
        "time": "2016-04-14T04:32:18.464Z",
        "to": "19:fced243ae1de407a8cfaff338c8f03fd@thread.skype"
        """
        members_added = []
        members_removed = []
        my_bot_skypeid = self.get_my_skype_full_bot_id()
        room_skypeid = self._evt_to
        #
        if 'membersAdded' in self._evt_dict:
            members_added = self._evt_dict['membersAdded']
            if type(members_added) == list:
                if my_bot_skypeid in members_added:
                    # bot was added to a skype conference
                    if room_skypeid not in self.chatrooms:
                        print('I was added to a conversation [{0}] :)'.format(room_skypeid))
                        self.chatrooms.append(room_skypeid)
                        self.save_data()
        #
        if 'membersRemoved' in self._evt_dict:
            members_removed = self._evt_dict['membersRemoved']
            if type(members_removed) == list:
                if my_bot_skypeid in members_removed:
                    # bot was removed from a skype conference
                    # for some reason, this is never received for now.
                    # so we can never know if we were removed from a chatroom
                    # but maybe in future...
                    if room_skypeid in self.chatrooms:
                        print('I was removed from conversation [{0}] :('.format(room_skypeid))
                        self.chatrooms.remove(room_skypeid)
                        self.save_data()

    def handle_attachment(self):
        # we do not handle an attachment in any way
        pass

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

        # enter the lock
        self._msg_lock.acquire()
        try:
            r = requests.post(url, data=postdata_e, headers={'Authorization': 'Bearer ' + self.token})
            if r.status_code != 201:
                sys.stderr.write('ERROR: API response status code:\n'.format(r.status_code))
        finally:
            # release the lock
            self._msg_lock.release()

        return True
