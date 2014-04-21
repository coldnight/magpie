#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#   Author  :   cold
#   E-mail  :   wh_linux@126.com
#   Date    :   14/04/17 14:59:52
#   Desc    :   客户端
#
import re
import os
import logging
import traceback

from functools import partial

from pyxmpp2.jid import JID
from pyxmpp2.presence import Presence
from pyxmpp2.message import Message
from pyxmpp2.client import Client
from pyxmpp2.settings import XMPPSettings
from pyxmpp2.interfaces import EventHandler, event_handler, QUIT
from pyxmpp2.streamevents import DisconnectedEvent, ConnectedEvent
from pyxmpp2.roster import RosterReceivedEvent, RosterUpdatedEvent
from pyxmpp2.interfaces import XMPPFeatureHandler
from pyxmpp2.interfaces import presence_stanza_handler, message_stanza_handler
from pyxmpp2.ext.version import VersionProvider
from pyxmpp2.mainloop.tornado import TornadoMainLoop

from twqq.client import WebQQClient
from twqq.requests import kick_message_handler, PollMessageRequest
from twqq.requests import system_message_handler, group_message_handler
from twqq.requests import buddy_message_handler, BeforeLoginRequest
from twqq.requests import file_message_handler
from twqq.requests import register_request_handler
from twqq.requests import Login2Request, FriendInfoRequest
from twqq.requests import sess_message_handler, discu_message_handler
from twqq.objects import UniqueIds

from magpie import __version__
from magpie.queue import InputQueue
from magpie.command import Command

logger = logging.getLogger("magpie")


AT_MSG_P = re.compile(r'^@(\d+)(.*)')


class MagpieClient(EventHandler, XMPPFeatureHandler):

    """ 启动并分别连接登录 XMPP 和 WebQQ
    """

    def __init__(self, QQ, QQ_PWD, xmpp_account, xmpp_pwd, control_account,
                 debug=True, command=None):
        self.input_queue = InputQueue(self.send_control_msg)
        self.qq = QQClient(QQ, QQ_PWD, debug)
        self.qq.set_control_msg(self.send_control_msg, self)
        self.command = command or Command(self, self.qq)
        self.jid = JID(xmpp_account + '/Bridge')
        self.control_account = control_account

        settings = XMPPSettings(
            {"software_name": "Magpie",
             "software_version": ".".join(str(x) for x in __version__),
             "software_os": "Linux",
             "tls_verify_peer": False,
             "starttls": True,
             "ipv6": False,
             "password": xmpp_pwd,
             "poll_interval": 10})

        version_provider = VersionProvider(settings)
        mainloop = TornadoMainLoop(settings)
        self.client = Client(self.jid, [self, version_provider],
                             settings, mainloop)

    def run(self, timeout=None):
        self.client.connect()
        self.client.run()

    def disconnect(self):
        self.client.disconnect()

    @presence_stanza_handler("subscribe")
    def handle_presence_subscribe(self, stanza):
        logger.info(u"{0} join us".format(stanza.from_jid))
        frm = stanza.from_jid
        presence = Presence(to_jid=frm, stanza_type="subscribe")
        r = [stanza.make_accept_response(), presence]
        return r

    @presence_stanza_handler("subscribed")
    def handle_presence_subscribed(self, stanza):
        logger.info(u"{0!r} accepted our subscription request"
                         .format(stanza.from_jid))
        frm = stanza.from_jid
        presence = Presence(to_jid=frm, stanza_type="subscribe")
        r = [stanza.make_accept_response(), presence]
        return r

    @presence_stanza_handler("unsubscribe")
    def handle_presence_unsubscribe(self, stanza):
        logger.info(u"{0} canceled presence subscription"
                         .format(stanza.from_jid))
        presence = Presence(to_jid=stanza.from_jid.bare(),
                            stanza_type="unsubscribe")
        r = [stanza.make_accept_response(), presence]
        return r

    def make_message(self, to, typ, body):
        """ 构造消息
            `to` - 接收人 JID
            `typ` - 消息类型
            `body` - 消息主体
        """
        if typ not in ['normal', 'chat', 'groupchat', 'headline']:
            typ = 'chat'
        m = Message(from_jid=self.jid, to_jid=to, stanza_type=typ, body=body)
        return m

    def send_control_msg(self, msg):
        logger.info(u"Send message {0} to {1}"
                    .format(msg, self.control_account))
        m = self.make_message(JID(self.control_account), "chat", msg)
        self.stream.send(m)

    def send_status(self, statustext):
        to_jid = JID(self.control_account)
        p = Presence(status=statustext, to_jid=to_jid)
        self.stream.send(p)

    @presence_stanza_handler("unsubscribed")
    def handle_presence_unsubscribed(self, stanza):
        logger.info(u"{0!r} acknowledged our subscrption cancelation"
                                                    .format(stanza.from_jid))
        return True

    @presence_stanza_handler(None)
    def handle_presence_available(self, stanza):
        logger.info(r"{0} has been online".format(stanza.from_jid))

    @presence_stanza_handler("unavailable")
    def handle_presence_unavailable(self, stanza):
        logger.info(r"{0} has been offline".format(stanza.from_jid))

    @message_stanza_handler()
    def handle_message(self, stanza):
        body = stanza.body
        frm = stanza.from_jid.bare().as_string()
        if frm == self.control_account:
            try:
                if self.input_queue.need_input:
                    if not body:
                        self.input_queue.send_tip()
                        return True
                    self.input_queue.input(body)
                else:
                    self.command.parse(body)
            except:
                self.send_control_msg(u"处理消息时发生错误:\n{0}"
                                      .format(traceback.format_exc()))
        logger.info("receive message '{0}' from {1}"
                         .format(body, stanza.from_jid))
        return True

    @event_handler(DisconnectedEvent)
    def handle_disconnected(self, event):
        return QUIT

    @event_handler(ConnectedEvent)
    def handle_connected(self, event):
        pass

    @property
    def roster(self):
        return self.client.roster

    @property
    def stream(self):
        return self.client.stream

    def invite_member(self, jid):
        logger.info('invite {0}'.format(jid))
        p1 = Presence(from_jid=self.my_jid, to_jid=jid,
                      stanza_type='subscribe')
        p = Presence(from_jid=self.my_jid, to_jid=jid,
                     stanza_type='subscribed')
        self.stream.send(p)
        self.stream.send(p1)

    @event_handler(RosterUpdatedEvent)
    def handle_roster_update(self, event):
        pass

    @event_handler(RosterReceivedEvent)
    def handle_roster_received(self, event):
        # 登陆 WebQQ
        logger.info("-- Connected, start connect WebQQ..")
        self.qq.connect()

    @event_handler()
    def handle_all(self, event):
        logger.info(u"-- {0}".format(event))


class QQClient(WebQQClient):

    def handle_verify_code(self, path, r, uin):
        self.verify_img_path = path
        cb = partial(self.enter_verify_code, r=r, uin=uin)
        self.input_queue.append(u"[S] 需要验证码, 请输入位于: {0} 位置的验证码"
                                .format(path), cb)

    @register_request_handler(BeforeLoginRequest)
    def handle_verify_check(self, request, resp, data):
        if not data:
            self.send_control_msg("[S] 没有数据返回验证失败, 尝试重新登录")
            return

        args = request.get_back_args(data)
        scode = int(args[0])
        if scode != 0:
            self.send_control_msg(args[4])

    @register_request_handler(Login2Request)
    def handle_login_errorcode(self, request, resp, data):
        if not resp.body:
            self.send_control_msg(u"[S] WebQQ 没有数据返回, 尝试重新登录")
            return

        if data.get("retcode") != 0:
            self.send_control_msg(u"[S] WebQQ 登录失败: {0}"
                                  .format(data.get("retcode")))

    @register_request_handler(FriendInfoRequest)
    def handle_frind_info_erro(self, request, resp, data):
        if not resp.body:
            self.send_control_msg(u"[S] WebQQ 获取好友列表失败")
            return

        if data.get("retcode") != 0:
            self.send_control_msg(u"[S] WebQQ 获取好友列表失败"
                                  .format(data.get("retcode")))
            return
        self.send_control_msg(u"[S] WebQQ 登录成功, 你可以发送 -help 查看帮助.")

    @kick_message_handler
    def handle_kick(self, message):
        self.send_control_msg(u"[S] QQ 在别处登录")
        # TODO
        # self.hub.relogin()

    @system_message_handler
    def handle_friend_add(self, mtype, from_uin, account, message):
        if mtype == "verify_required":
            #TODO
            self.hub.accept_verify(from_uin, account, str(account))

    @group_message_handler
    def handle_group_message(self, member_nick, content, group_code,
                             send_uin, source):
        groupname = self.hub.get_groups().get_group_name(group_code)
        self.send_control_msg(u"[Q][{0}({1})][{2}({3})] {4}"
                              .format(groupname, UniqueIds.get_id(group_code),
                                      member_nick, UniqueIds.get_id(send_uin),
                                      content))

    def send_message_with_aid(self, _id, content):
        self.xmpp_client.send_status(content)
        uin, _type = UniqueIds.get(int(_id))
        if uin is None or _type is None:
            logger.info(UniqueIds._map)
            self.send_control_msg(u"[S] 没有到 @{0} 的映射".format(_id))
            return
        if _type == UniqueIds.T_GRP:
            self.hub.send_group_msg(uin, content)
        elif _type == UniqueIds.T_FRI:
            self.hub.send_buddy_msg(uin, content)
        elif _type == UniqueIds.T_DIS:
            self.hub.send_discu_msg(uin, content)
        # elif _type == UniqueIds.T_TMP:
        #     self.hub.send_sess_msg(uin, content)

    @sess_message_handler
    def handle_sess_message(self, qid, from_uin, content, source):
        pass

    @file_message_handler
    def handle_file_message(self, from_uin, to_uin, lcid, guid, is_cancel,
                            source):
        name = self.hub.get_friends().get_show_name(from_uin)
        if is_cancel:
            tip = u"[S] {0} 取消了发送文件 {1}".format(name, guid)
            self.send_control_msg(tip)
            return

        tip = u"[S] {0} 发送文件 {1} 是否同意[Y/n]".format(name, guid)

        def callback(msg):
            if msg.strip().lower() == "y":
                self.hub.recv_file(guid, lcid, from_uin, self.store_file)
                return True, ""
            else:
                return True, u"[S] 你取消了接收 {0} 发送的文件 {1}".format(name, tip)

        self.xmpp_client.input_queue.append(tip, callback)

    def store_file(self, fname, data):
        path = os.path.join("/tmp", fname)
        with open(path, 'wb') as f:
            f.write(data)

        self.send_control_msg(u"[S] 文件已接收, 存放在: {0}".format(path))

    @discu_message_handler
    def handle_discu_message(self, did, from_uin, content, source):
        name = self.hub.get_discu().get_name(did)
        mname = self.hub.get_discu().get_mname(did, from_uin)
        msg = "[D][{0}({1})][{2}({3})] {4}".format(name, UniqueIds.get_id(did),
                                                   mname,
                                                   UniqueIds.get_id(from_uin),
                                                   content)
        self.send_control_msg(msg)

    def send_discu_with_nick(self, nick, did, content):
        content = u"{0}: {1}".format(nick, content)
        self.hub.send_discu_msg(did, content)

    def send_group_with_nick(self, nick, group_code, content):
        content = u"{0}: {1}".format(nick, content)
        self.hub.send_group_msg(group_code, content)

    @buddy_message_handler
    def handle_buddy_message(self, from_uin, content, source):
        name = self.hub.get_friends().get_show_name(from_uin)
        self.send_control_msg(u"[F][{0}({1})] {2}"
                              .format(name, UniqueIds.get_id(from_uin),
                                      content))

    @register_request_handler(PollMessageRequest)
    def handle_qq_errcode(self, request, resp, data):
        if data and data.get("retcode") in [100006]:
            logger.error(u"获取登出消息 {0!r}".format(data))
            self.hub.relogin()

        if data and data.get("retcode") in [103, 100002]:  # 103重新登陆不成功, 暂时退出
            logger.error(u"获取登出消息 {0!r}".format(data))
            exit()

    # def send_msg_with_markname(self, markname, message, callback=None):
    #     #TODO
    #     request = self.hub.send_msg_with_markname(markname, message)
    #     if request is None:
    #         callback(False, u"不存在该好友")

    #     self.message_requests[request] = callback

    # @register_request_handler(BuddyMsgRequest)
    # def markname_message_callback(self, request, resp, data):
    #     #TODO
    #     callback = self.message_requests.get(request)
    #     if not callback:
    #         return

    #     if not data:
    #         callback(False, u"服务端没有数据返回")
    #         return

    #     if data.get("retcode") != 0:
    #         callback(False, u"发送失败, 错误代码:".format(data.get("retcode")))
    #         return

    #     callback(True)

    def set_control_msg(self, cb, xmpp_client):
        self.send_control_msg = cb
        self.xmpp_client = xmpp_client
        self.input_queue = xmpp_client.input_queue
