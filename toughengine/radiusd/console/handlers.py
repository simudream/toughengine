#!/usr/bin/env python
#coding:utf-8
from toughengine.radiusd.console.base import BaseHandler
from toughengine.radiusd.console.tester import (AuthHandler,AcctHandler)
from toughengine.radiusd.console.nasapi import (NasSetHandler,NasGetHandler,NasListHandler,NasDelHandler)

class HomeHandler(BaseHandler):

    def get(self):
        self.post()

    def post(self):
        self.render_json(code=0,msg="ok")


class LoggerHandler(BaseHandler):

    def get(self):
        self.post()

    def post(self):
        self.render_json(code=0, msg="ok")




