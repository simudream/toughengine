#!/usr/bin/env python
# coding=utf-8

from cyclone import redis
from twisted.internet import defer
from twisted.internet import reactor

class RedisKey():

    def __init__(self):
        self.dbname = 'toughengine'

    def nas_pkey(self,ipaddr):
        return "{0}:{1}:{2}".format(self.dbname,'nas',ipaddr)

    def oss_pkey(self,oss_code):
        return "{0}:{1}:{2}".format(self.dbname, 'oss', oss_code)

    def stat_all_key(self):
        return "{0}:{1}:{2}".format(self.dbname, 'stat','all')

    def nas_all_key(self):
        return "{0}:{1}:{2}".format(self.dbname, 'nas','all')

    def oss_all_key(self):
        return "{0}:{1}:{2}".format(self.dbname, 'oss', 'all')


class RedisStore(RedisKey):
    """
    RedisStore
    """

    def __init__(self, config):
        RedisKey.__init__(self)
        self.config = config

    @defer.inlineCallbacks
    def connect(self):
        self.rdb = yield redis.ConnectionPool(
            host=self.config.store.host,
            port=int(self.config.store.port),
            dbid=int(self.config.store.dbid),
            poolsize=int(self.config.store.poolsize),
        )
        defer.returnValue(self.rdb)

    def delete(self,*keys):
        return self.rdb.delete(*keys)

    def get_nas(self,ipaddr):
        return self.rdb.hgetall(self.nas_pkey(ipaddr))

    @defer.inlineCallbacks
    def set_nas(self,ipaddr,nas_dict):
        trans = yield self.rdb.multi()
        yield self.rdb.hmset(self.nas_pkey(ipaddr), nas_dict)
        yield self.rdb.sadd(self.nas_all_key(), ipaddr)
        result = yield trans.commit()
        defer.returnValue(result)

    def list_nas(self):
        return self.rdb.smembers(self.nas_all_key())

    def get_oss(self, oss_code):
        return self.rdb.hgetall(self.oss_pkey(oss_code))

    @defer.inlineCallbacks
    def set_oss(self, oss_code, oss_dict):
        trans = yield self.rdb.multi()
        yield self.rdb.hmset(self.oss_pkey(oss_code), oss_dict)
        yield self.rdb.sadd(self.oss_all_key(),oss_code)
        result = yield trans.commit()
        defer.returnValue(result)

    def list_oss(self):
        return self.rdb.smembers(self.oss_all_key())

    def get_stat_data(self):
        return self.rdb.hmget(self.stat_all_key())

    def stat_incr(self,key):
        return self.rdb.hincr(self.stat_all_key(),key)

    def stat_incrby(self, key,value=1):
        return self.rdb.hincrby(self.stat_all_key(), key,value)

