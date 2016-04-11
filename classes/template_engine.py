# -*- coding: utf-8 -*-

# Site template engine
# Uses Mako template engine ( http://www.makotemplates.org/ )
#  Python IO encoding must be set to utf-8! see
#     https://docs.python.org/3.4/using/cmdline.html#envvar-PYTHONIOENCODING
#     or in Linux, export LC_ALL to UTF-8 locale (ru_RU.UTF-8, en_US.UTF-8)
#  for linux: !/usr/bin/python3-utf8
#  for Windows: !Y:/bin/Python34/python.exe or
#               !y:/bin/python34/python3-utf8.exe (!)
#  in template files: ## -*- coding: utf-8 -*-  (as a first line)

from mako.lookup import TemplateLookup
from mako import exceptions


class TemplateEngine:
    def __init__(self, config: dict):
        """
        Constructor
        :param config: dict with keys:
         'TEMPLATE_DIR' - directory where to read template html files from
         'TEMPLATE_CACHE_DIR' - dir to store compiled templates in
        :return: None
        """
        if 'TEMPLATE_DIR' not in config:
            config['TEMPLATE_DIR'] = '.'
        if 'TEMPLATE_CACHE_DIR' not in config:
            config['TEMPLATE_CACHE_DIR'] = '.'
        params = {
            'directories':      config['TEMPLATE_DIR'],
            'module_directory': config['TEMPLATE_CACHE_DIR'],
            # 'input_encoding':   'utf-8',
            # 'output_encoding':   'utf-8',
            # 'encoding_errors':  'replace',
            'strict_undefined': True
        }
        self._lookup = TemplateLookup(**params)
        self._args = dict()

    def assign(self, vname, vvalue):
        """
        Assign template variable value
        :param vname: - variable name
        :param vvalue: - variable value
        :return: None
        """
        self._args[vname] = vvalue

    def unassign(self, vname):
        """
        Unset template variablr
        :param vname: - variable name
        :return: None
        """
        if vname in self._args:
            self._args.pop(vname)

    def render(self, tname: str, expose_errors=True) -> str:
        """
        Renders specified template file
        and returns result as string, ready to be sent to browser.
        :param tname: - template file name
        :param expose_errors: - if true, any exception will be returned in result string
        :return: rendered template text
        """
        ret = ''
        try:
            tmpl = self._lookup.get_template(tname)
            ret = tmpl.render(**self._args)
        except exceptions.MakoException:
            if expose_errors:
                ret = exceptions.html_error_template().render()
            else:
                ret = 'Error rendering template: [' + tname + ']'
        return ret
