#!/usr/bin/env python
#coding:utf-8
from toughengine.radiusd.console.base import BaseHandler

class HomeHandler(BaseHandler):
    def get(self):
        self.render_json(code=0,msg="ok")



