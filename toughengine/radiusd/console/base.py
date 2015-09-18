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


class BaseHandler(cyclone.web.RequestHandler):
    
    def __init__(self, *argc, **argkw):
        super(BaseHandler, self).__init__(*argc, **argkw)

    def check_xsrf_cookie(self):
        pass

    def initialize(self):
        self.tp_lookup = self.application.tp_lookup
        
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

    def mksign(self, params=[]):
        _params = [str(p) for p in params if p is not None]
        _params.sort()
        _params.insert(0, self.settings.api_secret)
        strs = ''.join(_params)
        if self.settings.debug:
            log.msg("sign_src = %s" % strs)
        return md5(strs.encode()).hexdigest().upper()
