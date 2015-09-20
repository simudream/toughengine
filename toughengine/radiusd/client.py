#!/usr/bin/env python
# coding=utf-8

from twisted.python import log
from toughengine.radiusd import requests
from hashlib import md5
from twisted.internet import defer
import json
import logging


class HttpClient():
    """
    RestFull Client
    :param config:
    :type config:
    """

    def __init__(self, config, nasdb):
        self.config = config
        self.nasdb = nasdb

    def make_sign(self, params=[]):
        """ make sign
        :param params: params list
        :return: :rtype:
        """
        _params = [requests.safestr(p) for p in params if p is not None]
        _params.sort()
        _params.insert(0, self.config.defaults.secret)
        strs = requests.safestr(''.join(_params))
        if self.config.defaults.debug:
            log.msg("[HttpClient] :: sign_src = %s" % strs, level=logging.DEBUG)
        mds = md5(strs).hexdigest()
        return mds.upper()

    def check_sign(self,msg):
        """ check message sign
        :param msg: dict type  data
        :return: :rtype: boolean
        """
        if "sign" not in msg:
            return False
        sign = msg['sign']
        params = [msg[k] for k in msg if k != 'sign' ]
        return sign == self.make_sign(params)


    @defer.inlineCallbacks
    def send(self,apiurl,reqdata):
        """ send radius request
        :param apiurl: oss server api
        :param reqdata: json data
        """
        try:
            if self.config.defaults.debug:
                log.msg("[HttpClient] :: Send http request to {0}, {1}".format(apiurl,requests.safestr(reqdata)))

            headers = {"Content-Type": ["application/json;charset=utf-8"]}
            resp = yield requests.post(apiurl, data=reqdata, headers=headers)
            resp_json = yield resp.json()

            if self.config.defaults.debug:
                log.msg("[HttpClient] :: Received http response from {0}, {1}".format(apiurl, requests.safestr(resp_json)))

            if resp.code != 200:
                defer.returnValue(dict(code=1, msg=u'server return error http status code {0}'.format(resp.code)))
            else:
                result = resp_json
                if self.check_sign(result):
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
            sign = self.make_sign([username, domain, macaddr, nasaddr, vlanid1, vlanid2, textinfo])
            nas = self.nasdb.get(nasaddr)
            apiurl = nas and nas.get("aaa_auth_url") or None
            reqdata = json.dumps(dict(
                username=username,
                domain=domain,
                macaddr=macaddr,
                nasaddr=nasaddr,
                vlanid1=vlanid1,
                vlanid2=vlanid2,
                textinfo=textinfo,
                sign=sign
            ), ensure_ascii=False)
            resp = yield self.send(apiurl, reqdata)
            defer.returnValue(resp)
        except Exception as err:
            log.msg(u"[HttpClient] :: authorize failure,%s" % requests.safestr(err.message))
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
            sign = self.make_sign([username, session_id, session_time, session_timeout, macaddr, nasaddr, ipaddr,
                                input_octets, output_octets, input_pkts, output_pkts])
            nas = self.nasdb.get(nasaddr)
            apiurl = nas and nas.get("aaa_acct_url") or None
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
                sign=sign
            ), ensure_ascii=False)
            resp = yield self.send(apiurl, reqdata)
            defer.returnValue(resp)
        except Exception as err:
            log.msg(u"[HttpClient] :: accounting failure,%s" % requests.safestr(err.message))
            defer.returnValue(dict(code=1, msg=u"accounting error, please see log detail"))


class LoggerClient():

    def __init__(self,config,nasdb):
        self.config = config
        self.nasdb = nasdb

    def on_resp(self,resp):
        log.msg("[LoggerClient] :: Resp {0}, Send log done".format(resp.code))

    def send(self,nasaddr=None,content=None):
        nas = self.nasdb.get(nasaddr)
        apiurl = nas and nas.get("aaa_logger_url") or self.config.defaults.get("log_server")
        if apiurl:
            if self.config.defaults.debug:
                log.msg("[LoggerClient] :: Send http log request to {0}, {1}".format(apiurl, requests.safestr(content)))

            headers = {"Content-Type": ["text/plain;charset=utf-8"]}
            deferd = requests.post(apiurl, data=content, headers=headers)
            deferd.addCallbacks(self.on_resp,self.on_resp)
        else:
            log.msg("[LoggerClient] :: Not send, {0}".format(requests.safestr(content)))

