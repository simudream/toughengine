#!/usr/bin/env python
# coding=utf-8
import sys, os
from twisted.python.logfile import DailyLogFile
from twisted.python import log
from twisted.internet import task
from twisted.internet import protocol
from twisted.internet import reactor
from twisted.internet import defer
from toughengine.radiusd.pyrad import dictionary
from toughengine.radiusd.pyrad import host
from toughengine.radiusd.pyrad import packet
from toughengine.radiusd import utils,store
from toughengine.radiusd import client
from toughengine.radiusd.plugins import mac_parse,vlan_parse
from toughengine.radiusd.plugins import rate_process
import datetime
import logging
import time
import six
import os

__verson__ = '2.0'


class PacketError(Exception):
    """ packet exception"""
    pass

###############################################################################
# Basic RADIUS                                                            ####
###############################################################################

class RADIUS(host.Host, protocol.DatagramProtocol):
    def __init__(self, config):
        self.config = config
        self.dictfile = os.path.join(os.path.split(__file__)[0], 'dicts/dictionary')
        _dict = dictionary.Dictionary(self.dictfile)
        host.Host.__init__(self, dict=_dict)
        self.auth_delay = utils.AuthDelay(0)
        self.nasdb = store.Store(self.config.store.nas_db)
        self.statdb = store.Store(self.config.store.stat_db, writeback=True)
        task.LoopingCall(self.statdb.sync).start(10)
        self.radapi = client.HttpClient(self.config,self.nasdb)
        self.logapi = client.LoggerClient(self.config,self.nasdb)

    def processPacket(self, pkt):
        pass

    def createPacket(self, **kwargs):
        raise NotImplementedError('Attempted to use a pure base class')

    def datagramReceived(self, datagram, (host, port)):
        bas = self.nasdb.get(host)
        if not bas:
            log.msg('[Radiusd] :: Dropping packet from unknown host ' + host, level=logging.DEBUG)
            return

        secret, vendor_id = bas['secret'], bas['vendor_id']
        try:
            _packet = self.createPacket(packet=datagram, dict=self.dict, secret=six.b(str(secret)), vendor_id=vendor_id)
            _packet.deferred.addCallbacks(self.reply, self.on_exception)
            _packet.source = (host, port)
            log.msg("[Radiusd] :: Received radius request: %s" % (str(_packet)), level=logging.INFO)
            self.logapi.send(nasaddr=host, content=_packet.format_log())
            if self.config.defaults.debug:
                log.msg(_packet.format_str(), level=logging.DEBUG)
            proc_deferd = self.processPacket(_packet)
            proc_deferd.addCallbacks(self.on_process_done, self.on_exception)
        except packet.PacketError as err:
            errstr = 'RadiusError:Dropping invalid packet from {0} {1},{2}'.format(host, port, utils.safestr(err))
            self.logapi.send(content=errstr)

    def reply(self, reply):
        """
        send radius response
        :param reply:
        :type packet:
        :return None:
        :rtype:
        """
        log.msg("[Radiusd] :: Send radius response: %s" % (reply), level=logging.INFO)
        self.logapi.send(nasaddr=reply.source[0], content=reply.format_log())
        if self.config.defaults.debug:
            log.msg(reply.format_str(), level=logging.DEBUG)
        self.transport.write(reply.ReplyPacket(), reply.source)
        if reply.code == packet.AccessReject:
            self.statdb['auth_reject'] = self.statdb.get('auth_reject', 0) + 1
        elif reply.code == packet.AccessAccept:
            self.statdb['auth_accept'] = self.statdb.get('auth_accept', 0) + 1

    def on_process_done(self,resp):
        pass

    def on_exception(self, err):
        self.logapi.send(content=u'RadiusError:Packet process error,{0}'.format(utils.safestr(err)))


    def process_delay(self):
        while self.auth_delay.delay_len() > 0:
            try:
                reject = self.auth_delay.get_delay_reject(0)
                if (datetime.datetime.now() - reject.created).seconds < self.auth_delay.reject_delay:
                    return
                else:
                    self.reply(self.auth_delay.pop_delay_reject())
            except Exception as err:
                self.logapi.send(content=u'RadiusError:process_delay error,{0}'.format(utils.safestr(err)))


###############################################################################
# Auth Server                                                              ####
###############################################################################
class RADIUSAccess(RADIUS):
    """ Radius Access Handler
    """

    def createPacket(self, **kwargs):
        """parse radius packet
        :param kwargs:
        :return: :rtype:
        """
        vendor_id = kwargs.pop('vendor_id',0)
        pkt = utils.AuthPacket2(**kwargs)
        pkt.vendor_id = vendor_id
        mac_parse.process(pkt)
        vlan_parse.process(pkt)
        return pkt

    @defer.inlineCallbacks
    def processPacket(self, req):
        """process radius packet
        :param req:
        :return: :rtype:
        :raise PacketError:
        """
        self.statdb['auth_all'] = self.statdb.get('auth_all', 0) + 1
        if req.code != packet.AccessRequest:
            self.statdb['auth_drop'] = self.statdb.get('auth_drop', 0) + 1
            raise PacketError('non-AccessRequest packet on authentication socket')

        reply = req.CreateReply()
        reply.source = req.source

        aaa_resp = yield self.radapi.authorize(*req.get_authorize_msg())

        if aaa_resp['code'] > 0:
            self.send_reject(req, reply, aaa_resp['msg'])
            return

        if 'bypass' in aaa_resp and aaa_resp['bypass'] == 1:
            is_pwd_ok = True
        else:
            is_pwd_ok = req.is_valid_pwd(aaa_resp.get('passwd'))

        if not is_pwd_ok:
            self.send_reject(req, reply, aaa_resp['msg'])
        else:
            if "input_rate" in aaa_resp and 'output_rate' in aaa_resp:
                rate_process.process(reply, input_rate=aaa_resp['input_rate'], output_rate=aaa_resp['output_rate'])

            attrs = aaa_resp.get("attrs") or {}
            for attr_name in attrs:
                try:
                    reply.AddAttribute(utils.safestr(attr_name),attrs[attr_name])
                except Exception as err:
                    errstr = "RadiusError:current radius cannot support attribute {0},{1}".format(
                        attr_name,utils.safestr(err.message))
                    self.logapi.send(content=errstr)

            self.send_accept(req, reply)


    def send_accept(self, req, reply):
        """send accept reply
        :param req:
        :param reply:
        """
        reply['Reply-Message'] = 'success!'
        reply.code = packet.AccessAccept
        self.auth_delay.del_roster(req.get_mac_addr())
        req.deferred.callback(reply)

    def send_reject(self, req, reply, message):
        """send reject reply
        :param req:
        :param reply:
        :param message:
        """
        self.auth_delay.add_roster(req.get_mac_addr())
        reply['Reply-Message'] = message
        reply.code = packet.AccessReject
        if self.auth_delay.over_reject(req.get_mac_addr()):
            self.auth_delay.add_delay_reject(reply)
        else:
            req.deferred.callback(reply)

###############################################################################
# Acct Server                                                              ####
############################################################################### 

class RADIUSAccounting(RADIUS):
    """ Radius Accounting Handler
    """
    def createPacket(self, **kwargs):
        """parse radius packet
        :param kwargs:
        :type kwargs:
        :return:
        :rtype:
        """
        vendor_id = 0
        if 'vendor_id' in kwargs:
            vendor_id = kwargs.pop('vendor_id')
        pkt = utils.AcctPacket2(**kwargs)
        pkt.vendor_id = vendor_id
        mac_parse.process(pkt)
        vlan_parse.process(pkt)
        return pkt

    @defer.inlineCallbacks
    def processPacket(self, req):
        """process radius accounting
        :param req:
        :type req:
        :return:
        :rtype:
        """
        self.statdb['acct_all'] = self.statdb.get('acct_all', 0) + 1
        if req.code != packet.AccountingRequest:
            self.statdb['acct_drop'] = self.statdb.get('acct_drop', 0) + 1
            raise PacketError('non-AccountingRequest packet on authentication socket')

        reply = req.CreateReply()
        reply.source = req.source
        req.deferred.callback(reply)

        aaa_resp = yield self.radapi.accounting(*req.get_accounting_msg())
        self.logapi.send(nasaddr=req.source[0], content=aaa_resp['msg'])




###############################################################################
# Radius  Server                                                           ####
###############################################################################    

class RadiusServer(object):
    """ Radiuse Server
    :param config:
    :type config:
    """
    def __init__(self, config):
        self.config = config

    def init_config(self):
        """ init config
        """
        utils.aescipher.setup(self.config.defaults.secret)
        self.encrypt = utils.aescipher.encrypt
        self.decrypt = utils.aescipher.decrypt
        try:
            os.environ["TZ"] = self.config.defaults.tz
            time.tzset()
        except:pass

    def run_auth(self):
        """run auth
        """
        auth_protocol = RADIUSAccess(self.config)
        task.LoopingCall(auth_protocol.process_delay).start(2.7)
        reactor.listenUDP(int(self.config.radiusd.auth_port), auth_protocol, interface=self.config.radiusd.host)
        reactor.run()

    def run_acct(self):
        """run acct
        """
        acct_protocol = RADIUSAccounting(self.config)
        reactor.listenUDP(int(self.config.radiusd.acct_port), acct_protocol, interface=self.config.radiusd.host)
        reactor.run()


###############################################################################
# Radius  Run                                                              ####
###############################################################################

def run_auth(config):
    """run auth service
    :param config:
    """
    log.startLogging(sys.stdout)
    RadiusServer(config).run_auth()

def run_acct(config):
    """run acct service
    :param config:
    """
    log.startLogging(sys.stdout)
    RadiusServer(config).run_acct()

