# -*- coding: utf-8 -*-

import sys
import threading

from tweepy import API
from tweepy import OAuthHandler
from tweepy import Status
from tweepy.error import TweepError


class TwitterService:
    def __init__(self, config: dict):
        #
        # Twitter related
        self._consumer_key = config['TWITTER_CONSUMER_KEY']
        self._consumer_secret = config['TWITTER_CONSUMER_SECRET']
        self._access_token = config['TWITTER_ACCESS_TOKEN']
        self._access_token_secret = config['TWITTER_ACCESS_TOKEN_SECRET']
        self._user_timeline = config['TWITTER_USER_TIMELINE']
        #
        self._tweepy_oauth = OAuthHandler(self._consumer_key, self._consumer_secret)
        self._tweepy_oauth.set_access_token(self._access_token, self._access_token_secret)
        self._tweepy_api = API(auth_handler=self._tweepy_oauth)
        self._api_lock = threading.Lock()

    def get_timeline(self, cnt=10):
        timeline = []
        self._api_lock.acquire()
        try:
            timeline = self._tweepy_api.user_timeline(self._user_timeline, count=cnt)
        except TweepError as te:
            sys.stderr.write('Twitter error: {0}\n'.format(str(te)))
        finally:
            self._api_lock.release()
        return timeline

    def get_bb_videos(self, cnt=10):
        """
        Return format: list of dicts, each with format:
        {'tweet_id': ..., 'title': ..., 'url': ...}
        :param cnt: number of tweets to receive from timeline
        :return: list of bb videos
        """
        timeline = self.get_timeline(cnt)
        ret = []
        if len(timeline) > 0:
            for tu in timeline:
                if type(tu) == Status:
                    tweet_id = tu.id_str
                    nico_url = ''
                    #
                    if type(tu.entities) == dict:
                        if 'urls' in tu.entities:
                            for url_info in tu.entities['urls']:
                                url = url_info['expanded_url']
                                # be sure that we fetch only urls to nicovideo.jp videos!
                                if url.startswith('http://www.nicovideo.jp/watch/sm'):
                                    nico_url = url
                    #
                    if nico_url != '':
                        nico_title = self.get_niconico_title_from_text(tu.text)
                        # print('- bbvideo: {0} / {1} / {2}'.format(tweet_id, nico_title, nico_url))
                        bbvideo = {
                            'tweet_id': tweet_id,
                            'title': nico_title,
                            'url': nico_url
                        }
                        ret.append(bbvideo)
        return ret

    @classmethod
    def get_niconico_title_from_text(cls, text: str) -> str:
        """
        Gets only video title from movie bot tweet, strip url ender
        '"4月9日　セントラル八王子　BBCF　ランダム3on3大会　part3" - https://t.co/bYhEAC0J2x #sm28668357'
        =>
        '4月9日　セントラル八王子　BBCF　ランダム3on3大会　part3'
        :param text:
        :return:
        """
        pos = text.find(' - https://t.co/')
        if pos == -1:
            return text
        ret = text[:pos]
        if ret[0] == '"':
            ret = ret[1:]
        if ret[-1] == '"':
            ret = ret[:-1]
        return ret
