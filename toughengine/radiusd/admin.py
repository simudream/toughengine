#!/usr/bin/env python
#coding=utf-8
import os
import cyclone.web
from beaker.cache import CacheManager
from beaker.util import parse_cache_config_options
from mako.lookup import TemplateLookup
from toughengine.radiusd.console import handlers
from toughengine.radiusd import store
from twisted.python import log
from twisted.internet import reactor
import time
import sys


###############################################################################
# web application
###############################################################################
class Application(cyclone.web.Application):
    def __init__(self, config=None, **kwargs):
        self.config = config

        try:
            if 'TZ' not in os.environ:
                os.environ["TZ"] = config.defaults.tz
            time.tzset()
        except:pass

        settings = dict(
            cookie_secret=os.environ.get('cookie_secret', "12oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo="),
            login_url="/",
            template_path=os.path.join(os.path.dirname(__file__), "console/views"),
            static_path=os.path.join(os.path.dirname(__file__), "console/static"),
            xsrf_cookies=True,
            api_secret=config.defaults.secret,
            debug=config.defaults.debug,
            xheaders=True,
        )

        self.cache = CacheManager(**parse_cache_config_options({
            'cache.type': 'file',
            'cache.data_dir': '/tmp/cache/data',
            'cache.lock_dir': '/tmp/cache/lock'
        }))

        self.tp_lookup = TemplateLookup(directories=[settings['template_path']],
                                        default_filters=['decode.utf8'],
                                        input_encoding='utf-8',
                                        output_encoding='utf-8',
                                        encoding_errors='replace',
                                        module_directory="/tmp/toughengine")

        all_handlers = [
            (r"/", handlers.HomeHandler),
            (r"/api/v1", handlers.HomeHandler),
            (r"/api/v1/nas/add", handlers.NasAddHandler),
            (r"/test/authorize", handlers.AuthHandler),
            (r"/test/acctounting", handlers.AcctHandler),
            (r"/test/logger", handlers.LoggerHandler),
        ]

        self.redb = store.RedisStore(self.config)
        self.redb.connect().addCallback(self.on_redis_connect)

        cyclone.web.Application.__init__(self, all_handlers,  **settings)

    def on_redis_connect(self, resp):
        log.msg("redis connect done {0}".format(resp))


def run_admin(config):
    log.startLogging(sys.stdout)
    app = Application(config)
    reactor.listenTCP(int(config.admin.port), app, interface=config.admin.host)
    reactor.run()