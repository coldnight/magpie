#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#   Author  :   cold
#   E-mail  :   wh_linux@126.com
#   Date    :   14/04/21 09:43:21
#   Desc    :   命令解析
#
import re
import inspect

from twqq.objects import UniqueIds


def register(command, replace=None):
    """ 将函数注册为命令

    :param command: 命令正则匹配模式
    :param replace: 替代命令
    """
    def wrapper(func):
        func._command = command
        func._replace = replace
        return func
    return wrapper


class Command(object):
    def __init__(self, xmpp_client, qq_client):
        self.xmpp_client = xmpp_client
        self.qq_client = qq_client
        self._command_map = {}
        self._load_commands()

    def _load_commands(self):
        for _, handler in inspect.getmembers(self, callable):
            if not hasattr(handler, "_command"):
                continue

            self._command_map[handler._command] = (
                re.compile(handler._command), handler, handler._replace
            )

    def parse(self, command):
        for pattern, handler, _ in self._command_map.values():
            sre = pattern.match(command)
            if sre:
                handler(*sre.groups(), **sre.groupdict())

    @register(r'-help')
    def help_info(self):
        """ 显示帮助信息
        """
        info = [u"命令列表"]
        for command, (_, handler, replace) in self._command_map.items():
            command = command if replace is None else replace
            doc = handler.__doc__.decode("utf-8") if handler.__doc__ else u""
            info.append(u"{0}    {1}".format(command, doc.strip()))

        self.xmpp_client.send_control_msg("\n".join(info))

    @register("-list")
    def list_online_friends(self):
        """ 获取在线好友
        """
        friends = self.qq_client.hub.get_friends()
        cate_map = {}
        for cate in friends.categories:
            cate_map[cate.index - 1] = {"name": cate.name, "sort":  cate.sort,
                                        "list": []}

        for item in friends.info:
            if item.status in ["online", "away"]:
                cate_map[item.categories]["list"].append(item)

        lst = [(x.get("sort"), x.get("name"), x.get("list"))
               for x in cate_map.values()]

        lst = sorted(lst, key=lambda x: x[0])
        info = [u"在线好友列表"]
        for _, name, _list in lst:
            info.append(u"== {0} ==".format(name))
            for item in _list:
                if item.markname:
                    nick = u"{0}({1})".format(item.markname, item.nick)
                else:
                    nick = item.nick

                info.append(u"({1}){0}[{2}]".format(nick, item._id,
                                                    item.status))

        self.xmpp_client.send_control_msg("\n".join(info))

    @register("-glist")
    def list_groups(self):
        """ 获取群列表
        """
        info = [u"群列表"]
        groups = self.qq_client.hub.get_groups()
        if groups:
            for item in groups.groups:
                info.append(u"({0}) {1}".format(item._id, item.name))
        self.xmpp_client.send_control_msg("\n".join(info))

    @register("-dlist")
    def list_discu(self):
        """ 获取讨论组列表
        """
        info = [u"讨论组列表"]
        discu = self.qq_client.hub.get_discu()
        if discu:
            for item in discu.discus:
                info.append(u"({0}) {1}".format(item._id, item.name))
        self.xmpp_client.send_control_msg("\n".join(info))

    @register(r'^#(\d+)(.*)', "#id content")
    def send_at_message(self, _id, content):
        """ 给id发送消息, id 是对象的唯一id, content 是发送的内容
        """
        self.qq_client.send_message_with_aid(_id, content)

    @register(r"-qn (\d+)", "-qn id")
    def get_qq_account(self, _id):
        """ 获取QQ号码/群号码
        """
        uin, _type = UniqueIds.get(int(_id))

        if _type == UniqueIds.T_FRI:
            tys = u"QQ号码"
            friends = self.qq_client.hub.get_friends()
            name = friends.get_show_name(uin)
        elif _type == UniqueIds.T_GRP:
            tys = u"群号"
            groups = self.qq_client.hub.get_groups()
            name = groups.get_group_name(uin)
        else:
            self.xmpp_client.send_control_msg(u"{0} 不是群或者好友".format(_id))
            return

        account = self.qq_client.hub.get_account(uin, _type)
        if account:
            msg = u"{0} 的{2}是 {1}".format(name, account, tys)
        else:
            msg = u"获取{0}的{1}失败".format(name, tys)
        self.xmpp_client.send_control_msg(msg)
