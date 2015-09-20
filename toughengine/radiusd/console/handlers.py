#!/usr/bin/env python
#coding:utf-8
from toughengine.radiusd.console.base import BaseHandler
from toughengine.radiusd.console.tester import AuthHandler

class HomeHandler(BaseHandler):
    def post(self):
        self.render_json(code=0,msg="ok")


class LoggerHandler(BaseHandler):
    def post(self):
        self.render_json(code=0, msg="ok")




