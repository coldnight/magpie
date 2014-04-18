#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#   Author  :   cold
#   E-mail  :   wh_linux@126.com
#   Date    :   14/04/17 15:28:50
#   Desc    :   实现一个先入先出的栈
#
from collections import deque


class InputQueue(object):
    """ 一个获取输入队列, 用于管理用户的输入, 按以下方式工作:

    压入一个问题, 等待输入, 如输入正确则将此问题弹出, 处理下一个问题.

    压入问题, 则调用方法给控制账号发送一个问题, 并传入一个函数用于判断,
    输入, xmpp 账号获得消息时, 应首先判断是否有在等待输入, 如在等待,
    则将获得的消息传递给此栈, 然后由栈处理. 栈处理函数返回 True, 则表示
    此输入合法, 此问题则弹出栈, 继续处理下一个问题.

        :param send_cb: 发送xmpp消息的callback
    """

    def __init__(self, send_cb):
        self._queue = deque()
        self._send_cb = send_cb
        self.current_cb = None
        self.current_tip = None
        self.need_input = False

    def append(self, tip, callback):
        """ 将要求输入的压入队列

        :param tip: 提示信息
        :param callback: 接收输入的函数, 函数应返回一个元组, 元组第一个元素标识
                    是否成功, 第二个元素是提示信息.
        """
        if self.is_idle():
            self.current_tip, self.current_cb = tip, callback
            self.need_input = True
            self.send_tip()
        else:
            self._queue.append((tip, callback))

    def send_tip(self):
        if self.current_tip is not None:
            self._send_cb(self.current_tip)

    def input(self, content):
        r, msg = self.current_cb(content)
        if msg.strip():
            self._send_cb(msg)
        if r:
            if self.is_empty:
                self.need_input = False
                self.current_cb, self.current_tip = None, None
            else:
                self.consum()

    def consum(self):
        """ 消费一个输入
        """
        self.current_tip, self.current_cb = self._queue.popleft()
        self.send_tip()

    def is_empty(self):
        return not bool(self._queue)

    def is_idle(self):
        """ 是否是空闲时间
        """
        if not self._queue and self.current_cb is None:
            return True
        return False
