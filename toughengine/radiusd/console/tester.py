#!/usr/bin/env python
#coding=utf-8

from hashlib import md5
from twisted.python import log
from toughengine.radiusd.console.base import BaseHandler
from toughengine.radiusd.utils import safestr
import logging
import json

class AuthHandler(BaseHandler):
    """ authorize handler"""
    def post(self):
        """ authorize post
        :return: :rtype:
        """
        try:
            req_msg = json.loads(self.request.body)

            if not self.check_sign(self.settings.api_secret,req_msg):
                log.msg("[Radius] radius authorize request sign error")
                return self.render_json(code=1, msg='sign error')

        except Exception as err:
            import traceback
            traceback.print_exc()
            log.err('parse params error %s' % str(err))
            return self.render_json(code=1, msg='parse params error')

        result = dict(
            code=0,
            msg=u'success',
            username=req_msg['username'],
            passwd='123456',
            input_rate=4194304,
            output_rate=4194304,
            attrs={
                "Session-Timeout": 3600,
                "Acct-Interim-Interval": 300
            }
        )

        sign = self.make_sign(self.settings.api_secret,result.values())
        result['sign'] = sign
        self.render_json(**result)


class AcctHandler(BaseHandler):
    """ accounting handler"""

    def post(self):
        """ accounting post
        :return: :rtype:
        """
        try:
            req_msg = json.loads(self.request.body)
            if not self.check_sign(self.settings.api_secret,req_msg):
                return self.render_json(code=1, msg='sign error')

        except Exception as err:
            import traceback
            traceback.print_exc()
            log.err('parse params error %s' % str(err))
            return self.render_json(code=1, msg='parse params error')

        result = dict(
            code=0,
            msg=u'success',
            username=req_msg['username']
        )

        sign = self.make_sign(self.settings.api_secret,result.values())
        result['sign'] = sign
        self.render_json(**result)










