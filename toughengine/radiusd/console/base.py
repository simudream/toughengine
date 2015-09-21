#!/usr/bin/env python
#coding:utf-8

import json
import cyclone.auth
import cyclone.escape
import cyclone.web
from mako.template import Template
from hashlib import md5
from twisted.python import log
from toughengine.radiusd import utils
import logging

class BaseHandler(cyclone.web.RequestHandler):
    
    def __init__(self, *argc, **argkw):
        super(BaseHandler, self).__init__(*argc, **argkw)

    def check_xsrf_cookie(self):
        pass

    def initialize(self):
        self.tp_lookup = self.application.tp_lookup
        if self.settings.debug:
            log.msg("[api debug] :::::::: %s request body: %s" % (self.request.path, self.request.body))
        
    def on_finish(self):
        pass
        
    def get_error_html(self, status_code=500, **kwargs):
        return self.render_json(code=1, msg=u"%s:server error" % status_code)

    def render(self, template_name, **template_vars):
        html = self.render_string(template_name, **template_vars)
        self.write(html)

    def render_error(self, **template_vars):
        tpl = "error.html"
        html = self.render_string(tpl, **template_vars)
        self.write(html)

    def render_json(self, **template_vars):
        if not template_vars.has_key("code"):
            template_vars["code"] = 0
        resp = json.dumps(template_vars, ensure_ascii=False)
        if self.settings.debug:
            log.msg("[api debug] :::::::: %s response body: %s" % (self.request.path, resp))
        self.write(resp)

    def render_string(self, template_name, **template_vars):
        template_vars["request"] = self.request
        template_vars["handler"] = self
        template_vars["utils"] = utils
        mytemplate = self.tp_lookup.get_template(template_name)
        return mytemplate.render(**template_vars)

    def render_from_string(self, template_string, **template_vars):
        template = Template(template_string)
        return template.render(**template_vars)

    def make_sign(self, secret, params=[]):
        """ make sign
        :param params: params list
        :return: :rtype:
        """
        _params = [utils.safestr(p) for p in params if p is not None]
        _params.sort()
        _params.insert(0, secret)
        strs = ''.join(_params)
        # if self.settings.debug:
        #     log.msg("sign_src = %s" % strs, level=logging.DEBUG)
        mds = md5(utils.safestr(strs)).hexdigest()
        return mds.upper()

    def check_sign(self, secret, msg):
        """ check message sign
        :param msg: dict type  data
        :return: :rtype: boolean
        """
        if "sign" not in msg:
            return False
        sign = msg['sign']
        params = [msg[k] for k in msg if k != 'sign']
        local_sign = self.make_sign(secret, params)
        if self.settings.debug:
            log.msg("[api debug] :::::::: remote_sign = %s ,local_sign = %s" % (sign, local_sign), level=logging.DEBUG)
        return sign == local_sign
