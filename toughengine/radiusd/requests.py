#!/usr/bin/env python
#coding=utf-8

import treq
from twisted.internet import reactor
from twisted.internet import defer
from twisted.web.iweb import IBodyProducer
from zope.interface import implements
from twisted.web.client import HTTPConnectionPool
import json
import logging

pool = HTTPConnectionPool(reactor)


def safestr(val):
    if val is None:
        return ''
    elif isinstance(val, unicode):
        try:
            return val.encode('utf-8')
        except:
            return val.encode('GBK')
    elif isinstance(val, str):
        return val
    return val


class StringProducer(object):
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


def post(url,data=None,**kwargs):
    return treq.post(url, data=safestr(data), pool=pool,data_to_body_producer=StringProducer,**kwargs)


