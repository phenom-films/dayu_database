#!/usr/bin/env python
# -*- encoding: utf-8 -*-

__author__ = 'andyguo'

__doc__ = '''
    利用message 库实现的event center。
    用户可以对任何函数在运行前、运行后发射事件。然后通过将某些函数注册为监听函数，来监听发射的事件

'''

import message
import functools


def emit(event, **user_kwargs):
    '''
    发射事件的装饰函数。
    示例用法：
    @emit('event.name.before')
    def some_func():
        pass

    这样表示的是，在运行some_func() 之前，会发射before 的事件，
    如果有函数对这个事件进行了监听，那么就会被调用。

    如果想要在运行函数之前发射事件，那么事件的名称务必用 .before 进行结尾。
    如果想要在运行函数之后发射时间，那么事件的名称务必用 .after 进行结尾。
    其他的字符会忽略发射事件的行为。

    一个函数可以发射多个事件：
    @emit('event.first.before')
    @emit('event.second.after')
    def some_func():
        pass

    :param event: string，推荐的命名规范是 event.xxx.xxx.xxx.before / after
    :param user_kwargs: 目前没有使用
    :return:
    '''
    assert isinstance(event, basestring)

    def outter_wrapper(func):
        @functools.wraps(func)
        def inner_wrapper(*args, **kwargs):
            pub_event = tuple(event.split('.'))
            if pub_event[-1] == 'before':
                message.pub(pub_event, *args, **kwargs)
            result = func(*args, **kwargs)
            if pub_event[-1] == 'after':
                message.pub(pub_event, *args, **kwargs)
            return result

        return inner_wrapper

    return outter_wrapper


def listen(event, op='append'):
    '''
    注册监听函数的装饰器函数。

    用法：
    @listen('event.name.before')
    def callback(*args, **kwargs):
        pass

    被注册为监听函数的函数，会监听发射出的事件。如果某个函数发射了自己监听的事件时，函数就会运行。
    这里需要注意的是，监听函数会自动获取发射事件函数的全部参数。
    如果传递的参数是同一个内存地址的，那么对于参数的修改也会反映到原有的变量上。（注意！）

    可以让某个函数监听多个事件：
    @listen('event.first.before')
    @listen('event.second.after')
    def callback(*args, **kwargs):
        pass

    op 有三个选项 append、first、only。
    * append 表示把装饰的函数添加到监听列表的尾部。如果某个时间有多个监听函数存在，那么他们会根据添加的先后顺序执行
    * first 表示把装饰的函数添加到监听列表的头部。可以保证事件发射的的时候，当前函数被第一个调用（但是可能会被其他人使用first 推后）
    * only 表示清空之前对于该事件的所有监听列表，只保留当前的函数。

    推荐使用append，因为first 和only 都可能被其他调用者二次使用，而导致自己的监听函数出现问题。

    :param event: string, 对应需要监听的事件
    :param op: string，有三个选项append、first、only
    :return: function object
    '''
    assert isinstance(event, basestring)

    def outter_wrapper(func):
        listen_event = tuple(event.split('.'))
        if op == 'append':
            message.sub(listen_event, func)
        if op == 'first':
            message.sub(listen_event, func, front=True)
        if op == 'only':
            reset(event)
            message.sub(listen_event, func)

        return func

    return outter_wrapper


def events():
    '''
    返回当前所有的监听事件，以及对应的监听回调函数
    :return: dict
    '''
    return message.message._broker._router


def reset(event, func=None):
    '''
    清空某个事件的监听函数。
    用法：

    reset('event.name.before')

    这表示清空了 event.name.before 这个事件所有的监听函数。（事件本身依然会被发射）
    如果func 中指定了某个回调函数，那么只会删除指定的回调函数。如果func 不存在，那么忽略。

    :param event: string
    :param func: function object。表示回调的函数，如果是None，那么清空所有的监听函数
    :return:
    '''
    assert isinstance(event, basestring)
    listen_event = tuple(event.split('.'))
    if func:
        message.unsub(listen_event, func)
    else:
        if listen_event in message.message._broker._router:
            message.message._broker._router.pop(listen_event)

#
# @emit('event.ab_ttt.hello.before')
# @emit('event.ab_ttt.hello.after')
# def ab_ttt_func(value):
#     print value
#     value['ab_ttt'] += 1
#     return value
#
#
# @listen('event.ab_ttt.hello.before')
# def callback(value):
#     print 'event listen'
#     print value
#
#
# @listen('event.ab_ttt.hello.after')
# def callback2(value):
#     print 'event listen2'
#     print value
#
#
# def deco(*args, **kwargs):
#     def outter_wrapper(func):
#         @functools.wraps(func)
#         def wrapper(*inner_args, **inner_kwargs):
#             return func(*inner_args, **inner_kwargs)
#
#         return wrapper
#
#     return outter_wrapper
#
#
# @listen('event.ab_ttt.hello', op='only')
# @deco('hahah')
# def ttt(value):
#     print 'ttt'
#     value['ab_ttt'] += 1
#
#
# if __name__ == '__main__':
#     print events()
#     vv = {'ab_ttt': 20}
#     ab_ttt_func(vv)
#     reset('event.ab_ttt.hello.after', func=ttt)
#     print events()
#
#     ab_ttt_func(vv)
#
#     print vv
