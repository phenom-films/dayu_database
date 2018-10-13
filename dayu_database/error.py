#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'


class DayuDatabaseConfigNotExistError(ValueError):
    pass


class DayuDatabaseNotConnectError(ValueError):
    pass


class DayuDatabaseConfigChangedAfterConnect(ValueError):
    pass


class DayuStatusNotSetError(ValueError):
    pass


class DayuStatusInvalidateError(ValueError):
    pass
