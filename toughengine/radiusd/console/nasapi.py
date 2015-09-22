#!/usr/bin/env python
# coding=utf-8

from twisted.python import log
from toughengine.radiusd.console import validate
from toughengine.radiusd.console.base import BaseHandler
from toughengine.radiusd.utils import safestr
from twisted.internet import defer
import json


class NasAddHandler(BaseHandler):
    """ nas add handler"""

    @defer.inlineCallbacks
    def post(self):
        try:
            req_msg = json.loads(self.request.body)
            if not self.check_sign(self.settings.api_secret, req_msg):
                log.msg("[api debug] nas add request sign error")
                self.render_json(code=1, msg='sign error')
                return
        except Exception as err:
            log.err('parse params error %s' % safestr(err))
            self.render_json(code=1, msg='parse params error')
            return

        try:
            ipaddr = req_msg['ipaddr']
            dns_name = req_msg.get('dns_name','')
            secret = req_msg['secret']
            vendor_id = int(req_msg['vendor_id'])
            coa_port = int(req_msg.get("coa_port",3799))
            api_secret = req_msg["api_secret"]
            api_auth_url = req_msg["api_auth_url"]
            api_acct_url = req_msg["api_acct_url"]
            api_logger_url = req_msg["api_logger_url "]

            if validate.is_ip.valid(ipaddr):
                raise ValueError("ipaddr {0} format error,{1}".format(ipaddr,validate.is_ip.msg))

            if not validate.not_null.valid(secret):
                raise ValueError("secret {0} format error,{1}".format(secret, validate.not_null.msg))

            if not validate.not_null.valid(vendor_id):
                raise ValueError("vendor_id {0} format error,{1}".format(vendor_id, validate.not_null.msg))

            if not validate.is_number.valid(coa_port):
                raise ValueError("cao_port {0} format error,{1}".format(coa_port, validate.is_number.msg))

            if not validate.not_null.valid(api_secret):
                raise ValueError("api_secret {0} format error,{1}".format(api_secret, validate.not_null.msg))

            if not validate.is_url.valid(api_auth_url):
                raise ValueError("api_auth_url {0} format error,{1}".format(api_auth_url, validate.is_url.msg))

            if not validate.is_url.valid(api_acct_url):
                raise ValueError("api_acct_url {0} format error,{1}".format(api_acct_url, validate.is_url.msg))

            if api_logger_url and not validate.is_url.valid(api_logger_url):
                raise ValueError("api_logger_url {0} format error,{1}".format(api_logger_url, validate.is_url.msg))

        except Exception as err:
            log.err('verify params error %s' % safestr(err))
            self.render_json(code=1, msg='verify params error')
            return

        nasdata = dict(
            ipaddr=ipaddr,
            dns_name=dns_name,
            secret=secret,
            vendor_id=vendor_id,
            coa_port=coa_port,
            api_secret=api_secret,
            api_auth_url=api_auth_url,
            api_acct_url=api_acct_url,
            api_logger_url=api_logger_url
        )

        try:
            yield self.redb.set_nas(ipaddr,nasdata)
            result = dict(code=0,msg='success')
        except Exception as err:
            log.err('insert nasdata to database error  %s' % safestr(err))
            result = dict(code=1, msg='insert nasdata to database error')

        self.render_json(**result)
