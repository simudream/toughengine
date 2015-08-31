#!/usr/bin/env python
#coding:utf-8
import os
import ConfigParser
from toughengine.tools.shell import shell as sh

def find_config(conf_file=None):
    cfgs = [
        conf_file,
        '/etc/toughengine.conf'
    ]
    config = ConfigParser.ConfigParser()
    flag = False
    for c in cfgs:
        if c and os.path.exists(c):
            config.read(c)
            config.set('DEFAULT', 'cfgfile', c)
            sh.info("use config:%s"%c)  
            flag = True
            break
   
    if not flag:
        return None
    else:    
        return config
    
