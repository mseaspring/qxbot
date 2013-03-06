#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#   Author  :   cold
#   E-mail  :   wh_linux@126.com
#   Date    :   13/03/01 11:44:05
#   Desc    :   消息调度
#
import tempfile
from utils import get_logger, upload_file

class MessageDispatch(object):
    """ 消息调度器 """
    def __init__(self, qxbot, webqq, bridges):
        self.logger = get_logger()
        self.qxbot = qxbot
        self.webqq = webqq
        self.uin_qid_map = {}
        self.qid_uin_map = {}
        self.bridges = bridges
        self._maped = False

    def get_map(self):
        uins = [key for key, value in self.webqq.group_map.items()]
        for uin in uins:
            qid = self.get_qid_with_uin(uin)
            self.uin_qid_map[uin] = qid
            self.qid_uin_map[qid] = uin
        self._maped = True

    def get_xmpp_account(self, uin):
        """ 根据uin获取桥接的XMPP帐号 """
        qid = self.get_qid_with_uin(uin)
        xmpps = []
        for q, xmpp in self.bridges:
            if q == qid:
                xmpps.append(xmpp)

        return xmpps

    def get_uin_account(self, xmpp):
        """ 根据xmpp帐号获取桥接的qq号的uin """
        qids = []
        for qid, x in self.bridges:
            if x == xmpp:
                qids.append(self.qid_uin_map.get(qid))

        return qids

    def get_qid_with_uin(self, uin):
        qid = self.uin_qid_map.get(uin)
        if not qid:
            qid = self.webqq.get_qid_with_uin(uin)
            self.uin_qid_map[uin] = qid
        return qid

    def get_group_msg_img(self, uin, info):
        res = self.webqq.get_group_msg_img(uin, info)
        path = tempfile.mktemp()
        fp = open(path, 'wb')
        fp.write(res.read())
        fp.close()
        res = upload_file(info.get("name"), path)
        return res.geturl()

    def handle_qq_group_contents(self, uin, contents):
        result = []
        content = ""
        face = False
        for row in contents:
            if isinstance(row, (str, unicode)):
                content += row
            else:
                if len(row) == 2:
                    key, value = row
                    if key == "face":
                        face = True
                    if key == "cface":
                        result.append(self.get_group_msg_img(uin, value))

        if not result and not content.strip() and face:
            return u"(T T 只有QQ表情,暂时解析不鸟)"
        else:
            body = "\n".join(result) + content
            if face:
                body += "(QQ表情未解析)"
            return body

    def handle_qq_group_msg(self, message):
        """ 处理组消息 """
        value = message.get("value", {})
        gcode = value.get("group_code")
        uin = value.get("send_uin")
        contents = value.get("content", [])
        content = self.handle_qq_group_contents(uin, contents)
        gname = self.webqq.get_group_name(gcode)
        uname = self.webqq.get_group_member_nick(gcode, uin)
        body = u"[{0}][{1}] {2}".format(gname, uname, content)
        tos = self.get_xmpp_account(gcode)
        [self.qxbot.send_msg(to, body) for to in tos]

    def dispatch_qq(self, qq_source):
        if not self._maped: self.get_map()
        if qq_source.get("retcode") == 0:
            messages = qq_source.get("result")
            for m in messages:
                if m.get("poll_type") == "group_message":
                    self.handle_qq_group_msg(m)

    def dispatch_xmpp(self, stanza):
        if not self._maped: self.get_map()
        body = stanza.body
        frm = stanza.from_jid.bare().as_string()
        tos = self.get_uin_account(frm)
        [self.webqq.send_group_msg(to, body) for to in tos]
