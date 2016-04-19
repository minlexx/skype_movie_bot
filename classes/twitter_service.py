# -*- coding: utf-8 -*-

import sys

from tweepy import API
from tweepy import OAuthHandler
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

