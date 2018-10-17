#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'

from functools import wraps

class DayuDatabaseStatusNotConnect(object):
    pass


class DayuDatabaseStatusConnected(object):
    pass



def validate_status(status):
    def outter_wrapper(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            current_status = getattr(self, 'status', None)
            if current_status is None:
                from dayu_database.error import DayuStatusNotSetError
                raise DayuStatusNotSetError('{} status not set or without status'.format(self))

            if not isinstance(current_status, status):
                from dayu_database.error import DayuStatusInvalidateError
                raise DayuStatusInvalidateError('{} not match {}'.format(current_status, status))

            return func(self, *args, **kwargs)

        return wrapper
    return outter_wrapper