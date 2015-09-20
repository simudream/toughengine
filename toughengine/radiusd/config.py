#!/usr/bin/env python
# coding:utf-8
import os
import ConfigParser


class ConfigDict(dict):
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
        return '<ConfigDict ' + dict.__repr__(self) + '>'


class Config():
    """ Config Object """

    def __init__(self, conf_file=None, **kwargs):

        cfgs = [conf_file, '/etc/toughengine.conf']
        self.config = ConfigParser.ConfigParser()
        flag = False
        for c in cfgs:
            if c and os.path.exists(c):
                self.config.read(c)
                self.filename = c
                flag = True
                break
        if not flag:
            raise Exception("no config")

        self.defaults = ConfigDict(**{k: v for k, v in self.config.items("DEFAULT")})
        self.admin = ConfigDict(**{k: v for k, v in self.config.items("admin") if k not in self.defaults})
        self.store = ConfigDict(**{k: v for k, v in self.config.items("store") if k not in self.defaults})
        self.radiusd = ConfigDict(**{k: v for k, v in self.config.items("radiusd") if k not in self.defaults})

        self.defaults.debug = self.defaults.debug in ("1","true")

    def update(self):
        """ update config file"""
        for k,v in self.defaults.iteritems():
            self.config.set("DEFAULT", k, v)

        for k, v in self.admin.iteritems():
            if k not in self.defaults:
                self.config.set("admin", k, v)

        for k, v in self.store.iteritems():
            if k not in self.defaults:
                self.config.set("store", k, v)

        for k, v in self.radiusd.iteritems():
            if k not in self.defaults:
                self.config.set("radiusd", k, v)

        with open(self.filename, 'w') as cfs:
            self.config.write(cfs)


def add_test_data():
    config = Config("/Users/wangjuntao/toughstruct/toughengine/test.conf")
    import store
    nasdb = store.Store(config.store.nas_db)
    nasdb['127.0.0.1'] = dict(
        ipaddr='127.0.0.1',
        secret='123456',
        vendor_id=0,
        coa_port=3799,
        aaa_auth_url="http://192.168.31.153:1815/",
        aaa_acct_url="http://192.168.31.153:1815/",
        aaa_logger_url="http://192.168.31.153:1815/"
    )

    nasdb['192.168.31.153'] = dict(
        ipaddr='192.168.31.153',
        secret='123456',
        vendor_id=0,
        coa_port=3799,
        aaa_auth_url="http://192.168.31.153:1815/test/authorize",
        aaa_acct_url="http://192.168.31.153:1815/",
        aaa_logger_url="http://192.168.31.153:1815/"
    )
    nasdb.sync()

if __name__ == "__main__":
    add_test_data()