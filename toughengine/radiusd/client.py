#!/usr/bin/env python
# coding=utf-8

from twisted.python import log
from toughengine.radiusd import requests
from toughengine.radiusd.utils import safestr,get_currtime
from hashlib import md5
from twisted.internet import defer
import json
import time
import logging


class HttpClient():
    """
    RestFull Client
    :param config:
    :type config:
    """

    def __init__(self, config, redb):
        self.config = config
        self.redb = redb

    def make_sign(self, secret, params=[]):
        """ make sign
        :param secret:
        :param params: params list
        :return: :rtype:
        """
        _params = [safestr(p) for p in params if p is not None]
        _params.sort()
        _params.insert(0, secret)
        strs = safestr(''.join(_params))
        # if self.config.defaults.debug:
        #     log.msg("[HttpClient] ::::::: sign_src = %s" % strs, level=logging.DEBUG)
        mds = md5(strs).hexdigest()
        return mds.upper()

    def check_sign(self, secret, msg):
        """ check message sign
        :param secret:
        :param msg: dict type  data
        :return: :rtype: boolean
        """
        if "sign" not in msg:
            return False
        sign = msg['sign']
        params = [msg[k] for k in msg if k != 'sign' ]
        local_sign = self.make_sign(secret, params)
        if self.config.defaults.debug:
            log.msg("[HttpClient] ::::::: remote_sign = %s ,local_sign = %s" % (sign, local_sign), level=logging.DEBUG)
        return sign == local_sign


    @defer.inlineCallbacks
    def send(self,apiurl,reqdata,secret):
        """ send radius request
        :param apiurl: oss server api
        :param reqdata: json data
        """
        try:
            if self.config.defaults.debug:
                log.msg("[HttpClient] ::::::: Send http request to {0}, {1}".format(safestr(apiurl),safestr(reqdata)))

            headers = {"Content-Type": ["application/json;charset=utf-8"]}
            resp = yield requests.post(safestr(apiurl), data=reqdata, headers=headers)
            resp_json = yield resp.json()

            if self.config.defaults.debug:
                log.msg("[HttpClient] ::::::: Received http response from {0}, {1}".format(safestr(apiurl), safestr(resp_json)))

            if resp.code != 200:
                defer.returnValue(dict(code=1, msg=u'server return error http status code {0}'.format(resp.code)))
            else:
                result = resp_json
                if not self.check_sign(secret, result):
                    defer.returnValue(dict(code=1, msg=u"sign error"))
                else:
                    defer.returnValue(result)
        except Exception as err:
            import traceback
            traceback.print_exc()
            defer.returnValue(dict(code=1, msg=u'server error'))


    @defer.inlineCallbacks
    def authorize(self, username, domain, macaddr, nasaddr, vlanid1, vlanid2, textinfo=None):
        """send radius auth request
        :param username: not contain @doamin
        :param domain:
        :param macaddr:
        :param nasaddr:
        :param vlanid1:
        :param vlanid2:
        :param textinfo:
        """
        try:
            nas = yield self.redb.get_nas(nasaddr)
            nonce = str(time.time()),
            sign = self.make_sign([username, domain, macaddr, nasaddr, vlanid1, vlanid2, textinfo, nonce],nas.get("api_secret"))
            apiurl = nas and nas.get("api_auth_url") or None
            reqdata = json.dumps(dict(
                username=username,
                domain=safestr(domain),
                macaddr=safestr(macaddr),
                nasaddr=nasaddr,
                vlanid1=vlanid1,
                vlanid2=vlanid2,
                textinfo=safestr(textinfo),
                nonce=nonce,
                sign=sign
            ), ensure_ascii=False)
            resp = yield self.send(apiurl, reqdata, nas.get("api_secret"))
            defer.returnValue(resp)
        except Exception as err:
            log.msg(u"[HttpClient] ::::::: authorize failure,%s" % safestr(err.message))
            defer.returnValue(dict(code=1, msg=u"authorize error, please see log detail"))

    @defer.inlineCallbacks
    def accounting(self,req_type,username, session_id, session_time,session_timeout,macaddr,nasaddr,ipaddr,
                   input_octets,output_octets,input_pkts,output_pkts):
        """send radius accounting request
        :param req_type: 1 Start 2 Stop 3 Alive
        :param username:
        :param session_id:
        :param session_time:
        :param session_timeout:
        :param macaddr:
        :param nasaddr:
        :param ipaddr:
        :param input_octets:
        :param output_octets:
        :param input_pkts:
        :param output_pkts:
        """
        try:
            nas = yield self.redb.get_nas(nasaddr)
            nonce = str(time.time()),
            sign = self.make_sign([username, session_id, session_time, session_timeout, macaddr, nasaddr, ipaddr,
                                input_octets, output_octets, input_pkts, output_pkts,nonce], nas.get("api_secret"))

            apiurl = nas and nas.get("api_acct_url") or None
            reqdata = json.dumps(dict(
                req_type=req_type,
                username=username,
                session_id=session_id,
                session_time=session_time,
                session_timeout=session_timeout,
                macaddr=macaddr,
                nasaddr=nasaddr,
                ipaddr=ipaddr,
                input_octets=input_octets,
                output_octets=output_octets,
                input_pkts=input_pkts,
                output_pkts=output_pkts,
                nonce=nonce,
                sign=sign
            ), ensure_ascii=False)
            resp = yield self.send(apiurl, reqdata, nas.get("api_secret"))
            defer.returnValue(resp)
        except Exception as err:
            log.msg(u"[HttpClient] ::::::: accounting failure,%s" % safestr(err.message))
            defer.returnValue(dict(code=1, msg=u"accounting error, please see log detail"))


    @defer.inlineCallbacks
    def logger(self, nasaddr=None, content=None, level='info'):
        """
        send logger to logserver
        :param nasaddr:
        :param content:
        """
        nas = yield self.redb.get_nas(nasaddr)
        apiurl = nas and nas.get("api_logger_url") or self.config.defaults.get("log_server")
        if apiurl:
            if self.config.defaults.debug:
                log.msg("[HttpClient] ::::::: Send log Request to {0}, {1}".format(safestr(apiurl), safestr(content)))

            content = safestr(content)
            nonce = str(time.time())
            _datetime = get_currtime()
            sign = self.make_sign([nasaddr, content, _datetime, nonce], nas.get("api_secret"))
            reqdata = json.dumps(dict(
                nasaddr=nasaddr,
                content=content,
                datetime=_datetime,
                nonce=nonce,
                sign=sign
            ), ensure_ascii=False)

            headers = {"Content-Type": ["text/plain;charset=utf-8"]}
            resp = yield requests.post(safestr(apiurl), data=reqdata, headers=headers)
            log.msg("[HttpClient] ::::::: Received Resp {0}, Send log done".format(resp.code))
        else:
            log.msg("[HttpClient] ::::::: Not send, {0}".format(safestr(content)))

