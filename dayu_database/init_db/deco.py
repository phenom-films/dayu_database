#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'


class lazy(object):
    '''
    惰性求值的装饰器。
    在任意函数之前使用，就可以保证第二次调用的时候不再计算。
    被装饰的函数最好不要有参数。
    '''

    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            value = self.func(instance)
            setattr(instance, self.func.__name__, value)
            return value
