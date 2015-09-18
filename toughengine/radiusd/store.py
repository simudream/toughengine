#!/usr/bin/env python
# coding=utf-8

import shelve

class Store(shelve.DbfilenameShelf):
    """
    Store
    :param dbfile:
    :type dbfile:
    :param kwargs:
    :type kwargs:
    """

    def __init__(self, dbfile, **kwargs):
        shelve.DbfilenameShelf.__init__(self, dbfile, **kwargs)

    def save(self):
        self.sync()