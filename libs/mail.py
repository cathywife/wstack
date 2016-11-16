# -*- coding: utf-8 -*-

import email
import smtplib
import mimetypes
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage
from email.header import Header

# from prettytable import PrettyTable
from jinja2 import Environment


SMTP_HOST = 'mx.hy01.nosa.me'
SMTP_PORT = 25
CONT_MAIL_LIST = [
    'liningning@nosa.me',
    'sre-team@nosa.me'
]

"""
 table 模板, google gmail 只支持 inline css.
 首先通过 PrettyTable 生成 table 结构, 再通过 http://www.csstablegenerator.com 
 生成外部 css, 两者放在一起即是 html, 最后通过 https://inlinestyler.torchbox.com/styler/convert/ 
 把 html 转化成包含 inline css 的 html, 再改造成此处的模板.

 此处模板在 google gmail 中有部分效果损失, 但是够用了.

"""
TABLE_TEMPLATE = '''<html>
  <head/>
  <body>
    <table class="CSSTableGenerator" style="margin: 0;padding: 0;width: 100%;border: 1px solid #000;-moz-border-radius-bottomleft: 0;-webkit-border-bottom-left-radius: 0;border-bottom-left-radius: 0;-moz-border-radius-bottomright: 0;-webkit-border-bottom-right-radius: 0;border-bottom-right-radius: 0;-moz-border-radius-topright: 0;-webkit-border-top-right-radius: 0;border-top-right-radius: 0;-moz-border-radius-topleft: 0;-webkit-border-top-left-radius: 0;border-top-left-radius: 0">
      <tr style="background-color: #aad4ff">
        {% for key in keys %}
          <th>{{ key }}</th>
        {% endfor %}
      </tr>

      {% for _data in data %}
        <tr style="background-color: #fff">
          {% for d in _data %}
            <td style="vertical-align: middle;border: 1px solid #000;border-width: 0 1px 1px 0;text-align: left;padding: 7px;font-size: 10px;font-family: Arial;font-weight: normal;color: #000">{{d}}</td>
          {% endfor %}
        </tr>
      {% endfor %}
    </table>
  </body>
</html>
'''


def sanitize_subject(subject):
    try:
        subject.decode('ascii')
    except UnicodeEncodeError:
        pass
    except UnicodeDecodeError:
        subject = Header(subject, 'utf-8')
    return subject

# Assuming send_mail() is intended for scripting usage, only Subject is sanitzed here.
# Also, the sanitzation procedure for other Headers is far too complicated.


def mail(mailto, subject, content):
    mail_from = 'noreply@nosa.me'
    mail_cc = None
    mail_body_type = 'html'

    msg = MIMEMultipart('alternative')
    msg['Subject'] = sanitize_subject(subject)
    msg['From'] = mail_from
    # assert(isinstance(mailto, list))

    if isinstance(mailto, list):
        mailto.extend(CONT_MAIL_LIST)
        msg['To'] = ', '.join(mailto)
    elif mailto is None or mailto == "None":
        mailto = CONT_MAIL_LIST
        msg['To'] = ", ".join(CONT_MAIL_LIST)
    elif isinstance(mailto, str) or isinstance(mailto, unicode):
        msg['To'] = ", ".join(CONT_MAIL_LIST) + ", " + mailto
    else:
        mailto = CONT_MAIL_LIST
        msg['To'] = ", ".join(CONT_MAIL_LIST)

    if mail_cc is not None:
        assert(isinstance(mail_cc, list))
        msg['Cc'] = ', '.join(mail_cc)
    body = MIMEText(content, mail_body_type, 'utf-8')
    msg.attach(body)
    smtp = smtplib.SMTP()
    smtp.connect(SMTP_HOST, SMTP_PORT)
    smtp.sendmail(mail_from, mailto, msg.as_string())


def content_format(data=None, main=None):
    """ data 里面是 dict, dict 元素需要是一样.

    如果指定了 main, main 这个 list 指定的 key 会按顺序放在左侧.

    """
    if data is None:
        return

    KEYS = [
        'wmi_id',
        "area",
        "idc", 
        "type", 
        "version",
        "device",
        "vcpu",
        "mem",
        "space",
        "data_size",
        "vmhs",
        "num",
        "vmh",
        "vmname",
        "usage", 
        "sn", 
        "hostname",
        "ip", 
        "code",
        "message",
        "error_message",
        "ignored"
    ]

    keys = set()
    for d in data:
        for k in KEYS:
            if k in d:
                keys.add(k)
    keys = list(keys)
    keys.sort()

    if isinstance(main, list):
        main = filter(lambda x: x in keys, main)
        for value in main[::-1]:
            keys.remove(value)
            keys.insert(0, value)

    def func(_data):
        x = list()
        for key in keys:
            try:
                x.append(_data[key])
            except Exception, e:
                x.append(str(e))
        return x
    data = map(func, data)

    return Environment().from_string(TABLE_TEMPLATE).render(keys=keys, data=data)


def send(mailto, subject, content):
    if not isinstance(content, list):
        mail(mailto, subject, content)
        return

    try:
        content = content_format(content)
    except Exception, e:
        # raise e
        mail(mailto, subject, content)
        return
    mail(mailto, subject, content)


if __name__ == '__main__':
    send(None, "物理机创建完毕", "美丽的宝贝, 这只是一个测试而已, 你感动了么？")
    send(["tawateer@gmail.com"], "虚拟机创建完毕", "美丽的宝贝, 这只是一个测试而已, 你感动了么？")
    send("tawateer@gmail.com", "虚拟机删除完毕", "美丽的宝贝,这只是一个测试而已,你感动了么？")
    send("tawateer@gmail.com, 468032221@qq.com", "虚拟机删除完毕", "美丽的宝贝,这只是一个测试而已,你感动了么？")
