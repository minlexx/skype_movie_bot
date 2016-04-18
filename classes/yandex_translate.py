# -*- coding: utf-8 -*-
import sys
import collections
# external libraries
import requests
import requests.exceptions


class YandexTranslate:
    def __init__(self, yandex_api_key: str):
        self._apikey = yandex_api_key
        self._yt_url = 'https://translate.yandex.net/api/v1.5/tr.json/translate'

    def translate(self, q: str, src_lang: str, dst_lang: str, fmt: str = 'plain') -> str:
        """
        Translates string using Yandex translation service
        :param q:         strint to translate
        :param src_lang:  source lang code ('jp')
        :param dst_lang:  dest lang code ('en')
        :param fmt:       text format: 'plain' or 'html'
        :return:          translated string
        """

        retval = ''

        if fmt not in ['plain', 'html']:
            raise ValueError('fmt must be plain or html!')

        params = collections.OrderedDict()
        params['key'] = self._apikey
        params['text'] = q
        params['lang'] = src_lang + '-' + dst_lang
        params['format'] = fmt

        try:
            r = requests.get(self._yt_url, params=params)
            r.raise_for_status()
            response = r.json()
            if type(response) == dict:
                if 'text' in response:
                    retval = response['text']
        except requests.exceptions.RequestException as re:
            sys.stderr.write('Network error: {0}'.format(str(re)))

        return retval


def test_yandextranslate(yandex_api_key: str):
    yt = YandexTranslate(yandex_api_key)

    res = yt.translate('はい', 'ja', 'en')
    print(res)

    res = yt.translate('少女', 'ja', 'en')
    print(res)

    res = yt.translate('カグラ使われが送るワイバーン生活　0日目(テスト動画)', 'ja', 'en')
    print(res)


def yandex_translate_jp_en(text: str) -> str:
    yt = YandexTranslate('trnsl.1.1.20160418T102823Z.888167e74b48bd0b.1c6431f34c3e545d654a8f77054d609de0a87ce3')
    return yt.translate(text, 'jp', 'en')


if __name__ == '__main__':
    api = 'trnsl.1.1.20160418T102823Z.888167e74b48bd0b.1c6431f34c3e545d654a8f77054d609de0a87ce3'
    test_yandextranslate(api)
