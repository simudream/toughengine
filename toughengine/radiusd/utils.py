#!/usr/bin/env python
#coding=utf-8
from twisted.internet.defer import Deferred
from toughengine.radiusd.pyrad import tools
from toughengine.radiusd.pyrad.packet import AuthPacket
from toughengine.radiusd.pyrad.packet import AcctPacket
from toughengine.radiusd.pyrad.packet import CoAPacket
from toughengine.radiusd.pyrad.packet import AccessRequest
from toughengine.radiusd.pyrad.packet import AccessAccept
from toughengine.radiusd.pyrad.packet import AccountingRequest
from toughengine.radiusd.pyrad.packet import AccountingResponse
from toughengine.radiusd.pyrad.packet import CoARequest
from toughengine.radiusd.mschap import mschap,mppe
from Crypto.Cipher import AES
from Crypto import Random
import binascii
import base64
import datetime
import hashlib
import six
import json
import decimal

decimal.getcontext().prec = 11
decimal.getcontext().rounding = decimal.ROUND_UP

md5_constructor = hashlib.md5

PacketStatusTypeMap = {
    1 : 'AccessRequest',
    2 : 'AccessAccept',
    3 : 'AccessReject',
    4 : 'AccountingRequest',
    5 : 'AccountingResponse',
    40 : 'DisconnectRequest',
    41 : 'DisconnectACK',
    42 : 'DisconnectNAK',
    43 : 'CoARequest',
    44 : 'CoAACK',
    45 : 'CoANAK',
}

def is_expire(dstr):
    if not dstr:
        return False
    expire_date = datetime.datetime.strptime("%s 23:59:59"%dstr,"%Y-%m-%d %H:%M:%S")
    now = datetime.datetime.now()
    return expire_date < now

def safestr(val):
    if val is None:
        return ''
    elif isinstance(val, unicode):
        return val.encode('utf-8')
    elif isinstance(val, str):
        return val
    elif isinstance(val, int):
        return str(val)
    elif isinstance(val, float):
        return str(val)
    elif isinstance(val,dict):
        return json.dumps(val,ensure_ascii=False)
    return val

class AESCipher:

    def __init__(self,key=None):
        if key:self.setup(key)

    def setup(self, key): 
        self.bs = 32
        self.ori_key = key
        self.key = hashlib.sha256(key.encode()).digest()

    def encrypt(self, raw):
        raw = self._pad(raw)
        iv = Random.new().read(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return base64.b64encode(iv + cipher.encrypt(raw))

    def decrypt(self, enc):
        enc = base64.b64decode(enc)
        iv = enc[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return self._unpad(cipher.decrypt(enc[AES.block_size:])).decode('utf-8')
        
    def _pad(self, s):
        return s + (self.bs - len(s) % self.bs) * chr(self.bs - len(s) % self.bs)

    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s)-1:])]

aescipher = AESCipher()
encrypt = aescipher.encrypt
decrypt = aescipher.decrypt 


def mk_sign(args):
    args.sort()
    _argstr = aescipher.ori_key + ''.join(args)
    return hashlib.md5(_argstr).hexdigest()


def get_currtime():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Storage(dict):
    def __getattr__(self, key): 
        try:
            return self[key]
        except KeyError, k:
            raise AttributeError, k
    
    def __setattr__(self, key, value): 
        self[key] = value
    
    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError, k:
            raise AttributeError, k
    
    def __repr__(self):     
        return '<Storage ' + dict.__repr__(self) + '>'

class AuthDelay():
    
    def __init__(self,reject_delay=0):
        self.reject_delay = reject_delay
        self.rosters = {}
        self.delay_cache = []

    def delay_len(self):
        return len(self.delay_cache)

    def add_roster(self,mac_addr):
        if not mac_addr:
            return
        if mac_addr not in  self.rosters:
            self.rosters.setdefault(mac_addr,1)
        else:
            self.rosters[mac_addr] += 1

    def del_roster(self,mac_addr):
        if mac_addr in self.rosters:
            del self.rosters[mac_addr]

    def over_reject(self,mac_addr):
        return self.reject_delay>0 and self.rosters.get(mac_addr,0)>6

    def add_delay_reject(self,reject):
        self.delay_cache.append(reject)

    def get_delay_reject(self,idx):
        return self.delay_cache[idx]

    def pop_delay_reject(self):
        try:
            return self.delay_cache.pop(0)
        except:
            return None


def format_packet_str(pkt):
    attr_keys = pkt.keys()
    _str = "\nRadius Packet:%s"%PacketStatusTypeMap[pkt.code]
    _str += "\nhost:(%s,%s)" % pkt.source
    _str += "\nid:%s" % pkt.id
    _str += "\ncode:%s" % pkt.code
    _str += "\nAttributes: "     
    for attr in attr_keys:
        try:
            _type = pkt.dict[attr].type
            if _type == 'octets':
                _str += "\n\t%s: %s " % (attr, ",".join([ binascii.hexlify(_a) for _a in pkt[attr] ]))   
            else:
                _str += "\n\t%s: %s " % (attr, ",".join(pkt[attr]))   
        except:
            try:_str += "\n\t%s: %s" % (attr, pkt[attr])
            except:pass
    return _str


def format_packet_log(pkt):
    attr_keys = pkt.keys()
    _str = "RadiusPacket:%s;" % PacketStatusTypeMap[pkt.code]
    _str += "host:(%s,%s);" % pkt.source
    _str += "id:%s;" % pkt.id
    _str += "code:%s;" % pkt.code
    for attr in attr_keys:
        try:
            _type = pkt.dict[attr].type
            if _type == 'octets':
                _str += "%s:%s;" % (attr, ",".join([binascii.hexlify(_a) for _a in pkt[attr]]))
            else:
                _str += "%s:%s;" % (attr, ",".join(pkt[attr]))
        except:
            try:
                _str += "%s:%s;" % (attr, pkt[attr])
            except:
                pass
    return _str


class CoAPacket2(CoAPacket):
    def __init__(self, code=CoARequest, id=None, secret=six.b(''),
            authenticator=None, **attributes):
        CoAPacket.__init__(self, code, id, secret, authenticator, **attributes)
        self.deferred = Deferred()
        self.source_user = None
        self.vendor_id = 0
        self.client_macaddr = None
        self.created = datetime.datetime.now()

    def format_str(self):
        return format_packet_str(self)    


class AuthPacket2(AuthPacket):

    def __init__(self, code=AccessRequest, id=None, secret=six.b(''),
            authenticator=None, **attributes):
        AuthPacket.__init__(self, code, id, secret, authenticator, **attributes)
        self.deferred = Deferred()
        self.source_user = None
        self.vendor_id = 0
        self.vlanid = 0
        self.vlanid2 = 0
        self.client_macaddr = None
        self.created = datetime.datetime.now()
        self.ext_attrs = {}

    def format_str(self):
        return format_packet_str(self)

    def format_log(self):
        return format_packet_log(self)

    def __str__(self):
        _str = PacketStatusTypeMap[self.code]
        _str += " host=%s:%s" % self.source
        _str += ",id=%s"%self.id
        if self.code == 1:
            _str += ",username=%s,mac_addr=%s" % (self.get_user_name(),self.get_mac_addr())
        if 'Reply-Message' in self:
            _str += ',Reply-Message="%s"' % self['Reply-Message'][0]
        return _str   

    def CreateReply(self, msg=None,**attributes):
        reply = AuthPacket2(AccessAccept, self.id,
            self.secret, self.authenticator, dict=self.dict,
            **attributes)
        if msg:
            reply.set_reply_msg(tools.EncodeString(msg))
        reply.source_user = self.get_user_name()
        reply.vendor_id = self.vendor_id
        return reply
        
    def ChapEcrypt(self,password):
        if not self.authenticator:
            self.authenticator = self.CreateAuthenticator()
        if not self.id:
            self.id = self.CreateID()
        if isinstance(password, six.text_type):
            password = password.strip().encode('utf-8')

        result = six.b(chr(self.id))
        return md5_constructor("%s%s%s"%(chr(self.id),password,self.authenticator)).digest()


    def set_reply_msg(self,msg):
        if msg:self.AddAttribute(18,msg)

    def set_framed_ip_addr(self,ipaddr):
        if ipaddr:self.AddAttribute(8,tools.EncodeAddress(ipaddr))

    def set_session_timeout(self,timeout):
        if timeout:self.AddAttribute(27,tools.EncodeInteger(timeout))
   
    def get_nas_addr(self):
        _nas_addr = None
        try:
            _nas_addr = tools.DecodeAddress(self.get(4)[0])
        except:pass

        if not _nas_addr:
            _nas_addr = self.source[0]

        if _nas_addr != self.source[0]:
            _nas_addr = self.source[0]
        return _nas_addr

        
    def get_mac_addr(self):
        if self.client_macaddr:return self.client_macaddr
        try:return tools.DecodeString(self.get(31)[0]).replace("-",":")
        except:return None

    def get_user_name(self):
        try:
            user_name = tools.DecodeString(self.get(1)[0])
            if "@" in user_name:
                user_name = user_name[:user_name.index("@")]
            return user_name
        except:
            return None

    def get_domain(self):
        try:
            user_name = tools.DecodeString(self.get(1)[0])
            if "@" in user_name:
                return user_name[user_name.index("@")+1:]
        except:
            return None            
        
    def get_vlanids(self):
        return self.vlanid,self.vlanid2

    def get_passwd(self):
        try:return self.PwDecrypt(self.get(2)[0])
        except:return None        

    def get_chappwd(self):
        try:return tools.DecodeOctets(self.get(3)[0])
        except:return None  
        
    def verifyChapEcrypt(self,userpwd):
        if isinstance(userpwd, six.text_type):
            userpwd = userpwd.strip().encode('utf-8')   

        _password = self.get_chappwd()
        if len(_password) != 17:
            return False

        chapid = _password[0]
        password = _password[1:]

        if not self.authenticator:
            self.authenticator = self.CreateAuthenticator()

        challenge = self.authenticator
        if 'CHAP-Challenge' in self:
            challenge = self['CHAP-Challenge'][0] 

        _pwd =  md5_constructor("%s%s%s"%(chapid,userpwd,challenge)).digest()
        return password == _pwd
        
        
    def verifyMsChapV1(self,userpwd):
        ms_chap_response = self['MS-CHAP-Response'][0]
        authenticator_challenge = self['MS-CHAP-Challenge'][0]
        if len(ms_chap_response)!=50:
            raise Exception("Invalid MSCHAPV1-Response attribute length")
        
        flag = ms_chap_response[1]
        lm_password = None
        nt_password = None
        if flag == 0:
            lm_password = ms_chap_response[2:26]
        else:
            nt_password = ms_chap_response[26:50]
        
        resp = None
        auth_ok = False
        if nt_password:
            resp = mschap.generate_nt_response_mschap(authenticator_challenge,userpwd)
            auth_ok = (resp == nt_password)
        elif lm_password:
            resp = mschap.generate_lm_response_mschap(authenticator_challenge,userpwd)
            auth_ok = (resp == lm_password)
        if not auth_ok:return False
        
        nt_hash = mschap.nt_password_hash(userpwd)
        lm_hash = mschap.lm_password_hash(userpwd)
        _key = (nt_hash + lm_hash).ljust(32,'0')
        mppekey = mppe.radius_encrypt_keys(_key,self.secret,self.authenticator,mppe.create_salt())
        self.ext_attrs['MS-CHAP-MPPE-Keys'] = mppekey    
        return True
        
        
    def verifyMsChapV2(self,userpwd):
        ms_chap_response = self['MS-CHAP2-Response'][0]
        authenticator_challenge = self['MS-CHAP-Challenge'][0]
        if len(ms_chap_response)!=50:
            raise Exception("Invalid MSCHAPV2-Response attribute length")
        # if isinstance(userpwd, six.text_type):
        #     userpwd = userpwd.strip().encode('utf-8')
        
        nt_response = ms_chap_response[26:50]
        peer_challenge = ms_chap_response[2:18]
        _user_name = self.get(1)[0]
        nt_resp = mschap.generate_nt_response_mschap2(
            authenticator_challenge,
            peer_challenge,
            _user_name,
            userpwd,
        )
        if nt_resp == nt_response:
            auth_resp = mschap.generate_authenticator_response(
                userpwd,
                nt_response,
                peer_challenge,
                authenticator_challenge,
                _user_name
            )
            self.ext_attrs['MS-CHAP2-Success'] = auth_resp
            self.ext_attrs['MS-MPPE-Encryption-Policy'] = '\x00\x00\x00\x01'
            self.ext_attrs['MS-MPPE-Encryption-Type'] = '\x00\x00\x00\x06'
            nt_pwd_hash = mschap.nt_password_hash(userpwd)
            mppeSendKey,mppeRecvKey = mppe.mppe_chap2_gen_keys(userpwd,peer_challenge)
            self.ext_attrs['MS-MPPE-Send-Key'] = mppeSendKey
            self.ext_attrs['MS-MPPE-Recv-Key'] = mppeRecvKey
            return True
        else:
            return False
        
        
    def get_pwd_type(self):
        if 'MS-CHAP-Challenge' in self:
            if 'MS-CHAP-Response' in self:
                return 'mschapv1'
            elif 'MS-CHAP2-Response' in self:
                return 'mschapv2'
        elif 'CHAP-Password' in self:
            return 'chap'
        else:
            return 'pap'
            

    def is_valid_pwd(self,userpwd):
        pwd_type = self.get_pwd_type()
        try:
            if pwd_type == 'pap':
                return userpwd == self.get_passwd()
            elif pwd_type == 'chap':
                return self.verifyChapEcrypt(userpwd)
            elif pwd_type == 'mschapv1':
                return self.verifyMsChapV1(userpwd)
            elif pwd_type == 'mschapv2':
                return self.verifyMsChapV2(userpwd)
            else:
                return False
        except Exception as err:
            import traceback
            traceback.print_exc()
            return False


    def get_authorize_msg(self):
        return (self.get_user_name(),
                self.get_domain(),
                self.get_mac_addr(),
                self.get_nas_addr(),
                self.vlanid,
                self.vlanid2)

class AcctPacket2(AcctPacket):
    def __init__(self, code=AccountingRequest, id=None, secret=six.b(''),
            authenticator=None, **attributes):
        AcctPacket.__init__(self, code, id, secret, authenticator, **attributes)
        self.deferred = Deferred()
        self.source_user = None
        self.vendor_id = 0
        self.client_macaddr = None
        self.ticket = {}
        self.created = datetime.datetime.now()

    def format_str(self):
        return format_packet_str(self)

    def format_log(self):
        return format_packet_log(self)

    def __str__(self):
        _str = PacketStatusTypeMap[self.code]
        _str += " host=%s:%s" % self.source
        _str += ",id=%s"%self.id
        if self.code == 4:
            _str += ",username=%s,mac_addr=%s" % (self.get_user_name(),self.get_mac_addr())
        return _str   

    def CreateReply(self,**attributes):
        reply = AcctPacket2(AccountingResponse, self.id,
            self.secret, self.authenticator, dict=self.dict,
            **attributes)
        reply.source_user = self.get_user_name()
        return reply        

    def get_user_name(self):
        try:
            user_name = tools.DecodeString(self.get(1)[0])
            if "@" in user_name:
                return user_name[:user_name.index("@")]
            else:
                return user_name
        except:
            return None
 

    def get_mac_addr(self):
        if self.client_macaddr:return self.client_macaddr
        try:return tools.DecodeString(self.get(31)[0]).replace("-",":")
        except:return None

    def get_nas_addr(self):
        _nas_addr = None
        try:
            _nas_addr = tools.DecodeAddress(self.get(4)[0])
        except:pass

        if not _nas_addr:
            _nas_addr =  self.source[0]

        if _nas_addr != self.source[0]:
            _nas_addr =  self.source[0]
        return _nas_addr

    def get_nas_port(self):
        try:return tools.DecodeInteger(self.get(5)[0]) or 0
        except:return 0

    def get_service_type(self):
        try:return tools.DecodeInteger(self.get(0)[0]) or 0
        except:return 0
        
    def get_framed_ipaddr(self):
        try:return tools.DecodeAddress(self.get(8)[0])
        except:return None

    def get_framed_netmask(self):
        try:return tools.DecodeAddress(self.get(9)[0])
        except:return None

    def get_nas_class(self):
        try:return tools.DecodeString(self.get(25)[0])
        except:return None   

    def get_session_timeout(self):
        try:return tools.DecodeInteger(self.get(27)[0]) or 0
        except:return 0

    def get_calling_stationid(self):
        try:return tools.DecodeString(self.get(31)[0])
        except:return None   

    def get_acct_status_type(self):
        try:return tools.DecodeInteger(self.get(40)[0])
        except:return None

    def get_acct_input_octets(self):
        try:return tools.DecodeInteger(self.get(42)[0]) or 0
        except:return 0

    def get_acct_output_octets(self):
        try:return tools.DecodeInteger(self.get(43)[0]) or 0
        except:return 0

    def get_acct_sessionid(self):
        try:return tools.DecodeString(self.get(44)[0])
        except:return None                                                         

    def get_acct_sessiontime(self):
        try:return tools.DecodeInteger(self.get(46)[0]) or 0
        except:return 0                                                             

    def get_acct_input_packets(self):
        try:return tools.DecodeInteger(self.get(47)[0]) or 0
        except:return 0                                                       

    def get_acct_output_packets(self):
        try:return tools.DecodeInteger(self.get(48)[0]) or 0
        except:return 0           

    def get_acct_terminate_cause(self):
        try:return tools.DecodeInteger(self.get(49)[0]) or 0
        except:return 0           

    def get_acct_input_gigawords(self):
        try:return tools.DecodeInteger(self.get(52)[0]) or 0
        except:return 0       

    def get_acct_output_gigawords(self):
        try:return tools.DecodeInteger(self.get(53)[0]) or 0
        except:return 0                                                         

    def get_event_timestamp(self,timetype=0):
        try:
            _time = tools.DecodeDate(self.get(55)[0])
            if timetype == 0:
                return datetime.datetime.fromtimestamp(_time).strftime("%Y-%m-%d %H:%M:%S")
            else:
                return datetime.datetime.fromtimestamp(_time-(8*3600)).strftime("%Y-%m-%d %H:%M:%S")
        except:
            return None

    def get_nas_port_type(self):
        try:return tools.DecodeInteger(self.get(61)[0]) or 0
        except:return 0   

    def get_nas_portid(self):
        try:return tools.DecodeString(self.get(87)[0])
        except:return None    
        
    def get_input_total(self):
        bl = decimal.Decimal(self.get_acct_input_octets())/decimal.Decimal(1024)
        gl = decimal.Decimal(self.get_acct_input_gigawords())*decimal.Decimal(4*1024*1024)
        tl = bl + gl
        return int(tl.to_integral_value())   
        
    def get_output_total(self):
        bl = decimal.Decimal(self.get_acct_output_octets())/decimal.Decimal(1024)
        gl = decimal.Decimal(self.get_acct_output_gigawords())*decimal.Decimal(4*1024*1024)
        tl = bl + gl
        return int(tl.to_integral_value())   

    def get_ticket(self):
        if self.ticket:return self.ticket
        self.ticket = Storage(
            account_number = self.get_user_name(),
            mac_addr = self.get_mac_addr(),
            nas_addr = self.get_nas_addr(),
            nas_port = self.get_nas_port(),
            service_type = self.get_service_type(),
            framed_ipaddr = self.get_framed_ipaddr(),
            framed_netmask = self.get_framed_netmask(),
            nas_class = self.get_nas_class(),
            session_timeout = self.get_session_timeout(),
            calling_stationid = self.get_calling_stationid(),
            acct_status_type = self.get_acct_status_type(),
            acct_input_octets = self.get_acct_input_octets(),
            acct_output_octets = self.get_acct_output_octets(),
            acct_session_id = self.get_acct_sessionid(),
            acct_session_time = self.get_acct_sessiontime(),
            acct_input_packets = self.get_acct_input_packets(),
            acct_output_packets = self.get_acct_output_packets(),
            acct_terminate_cause = self.get_acct_terminate_cause(),
            acct_input_gigawords = self.get_acct_input_gigawords(),
            acct_output_gigawords = self.get_acct_output_gigawords(),
            event_timestamp = self.get_event_timestamp(),
            nas_port_type=self.get_nas_port_type(),
            nas_port_id=self.get_nas_portid()
        )
        return self.ticket


    def get_accounting_msg(self):
        return (
            self.get_acct_status_type(),
            self.get_user_name(),
            self.get_acct_sessionid(),
            self.get_acct_sessiontime(),
            self.get_session_timeout(),
            self.get_mac_addr(),
            self.get_nas_addr(),
            self.get_framed_ipaddr(),
            self.get_input_total(),
            self.get_output_total(),
            self.get_acct_input_packets(),
            self.get_acct_output_packets()
        )


if __name__ == "__main__":
    print safestr({"sdsd":"sdfsf"})