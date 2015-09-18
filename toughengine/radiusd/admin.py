#!/usr/bin/env python
#coding=utf-8
import os
import cyclone.web
from twisted.python.logfile import DailyLogFile
from beaker.cache import CacheManager
from beaker.util import parse_cache_config_options
from mako.lookup import TemplateLookup
from toughengine.radiusd.console import handlers
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
            os.environ["TZ"] = config.defaults.tz
            time.tzset()
        except:pass

        settings = dict(
            cookie_secret="12oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
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
        ]
        cyclone.web.Application.__init__(self, all_handlers,  **settings)


def run_admin(config):
    if config.defaults.debug:
        log.startLogging(sys.stdout)
    else:
        log.startLogging(DailyLogFile.fromFullPath(config.admin.logfile))
    app = Application(config)
    reactor.listenTCP(int(config.admin.port), app, interface=config.admin.host)
    reactor.run()