#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#   Author  :   cold
#   E-mail  :   wh_linux@126.com
#   Date    :   14/04/18 15:57:35
#   Desc    :   演示程序
#
""" 可以像如下方式开启此程序
"""
import logging
from magpie import client

QQ_NUM = 123456                     # QQ号
QQ_PWD = "qq pwd"                   # QQ 密码

XMPP_ACCOUNT = "xmpp@jabber.org"            # XMPP 账号
XMPP_PASSWD = "xmpppasswd"                  # XMPP 密码
XMPP_CONTROL = "controlofxmpp@jabber.org"   # XMPP 控制账号

DEBUG = True                # 是否开启调试

if __name__ == "__main__":

    # 输出日志
    handler = logging.StreamHandler()

    # 如果你需要更加详细的 PyXMPP 日志, 可以将日志级别调为 logging.DEBUG
    handler.setLevel(logging.INFO)

    for logger in ("pyxmpp2.IN", "pyxmpp2.OUT", "twqq", "magpie"):
        logger = logging.getLogger(logger)

        # 如果你需要更加详细的 PyXMPP 日志, 可以将日志级别调为 logging.DEBUG
        logger.setLevel(logging.INFO)

        logger.addHandler(handler)
        logger.propagate = False

    cli = client.MagpieClient(QQ_NUM, QQ_PWD, XMPP_ACCOUNT, XMPP_PASSWD,
                              XMPP_CONTROL, DEBUG)

    cli.run()
