#!/usr/bin/env python
#coding=utf-8

from hashlib import md5
from twisted.python import log
from toughengine.radiusd.console.base import BaseHandler
from toughengine.radiusd.utils import safestr
import logging
import json

class ApiHandler(BaseHandler):

    def make_sign(self, params=[]):
        """ make sign
        :param params: params list
        :return: :rtype:
        """
        _params = [safestr(p) for p in params if p is not None]
        _params.sort()
        _params.insert(0, self.settings.api_secret)
        strs = ''.join(_params)
        if self.settings.debug:
            log.msg("sign_src = %s" % strs, level=logging.DEBUG)
        mds = md5(safestr(strs)).hexdigest()
        return mds.upper()

    def check_sign(self, msg):
        """ check message sign
        :param msg: dict type  data
        :return: :rtype: boolean
        """
        if "sign" not in msg:
            return False
        sign = msg['sign']
        params = [msg[k] for k in msg if k != 'sign']
        local_sign = self.make_sign(params)
        if self.settings.debug:
            log.msg("local_sign = %s" % local_sign, level=logging.DEBUG)
        return sign == local_sign


class AuthHandler(ApiHandler):
    """ authorize handler"""
    def post(self):
        """ authorize post
        :return: :rtype:
        """
        try:
            req_msg = json.loads(self.request.body)

            if self.settings.debug:
                log.msg("radius authorize request: %s" % req_msg)

            if not self.check_sign(req_msg):
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

        sign = self.make_sign(result.values())
        result['sign'] = sign
        self.render_json(**result)


class AcctHandler(ApiHandler):
    """ accounting handler"""

    def post(self):
        """ accounting post
        :return: :rtype:
        """
        try:
            req_msg = json.loads(self.request.body)

            if self.settings.debug:
                log.msg("radius accounting request: %s" % req_msg)

            if not self.check_sign(req_msg):
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

        sign = self.make_sign(result.values())
        result['sign'] = sign
        self.render_json(**result)










