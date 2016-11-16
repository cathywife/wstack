#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import socket
import signal
import time

import ujson as json

import tornado.ioloop
import tornado.web
import tornado.httpserver
import tornado.escape
import tornado.netutil

from libs import ldapauth, redisoj, utils
from web.const import BIND_IP, BIND_PORT

from pm.web import service as pm_service
from vmmaster.web import service as vmmaster_service


class LdapauthapiHandler(tornado.web.RequestHandler):

    def post(self):
        username = self.get_argument('username')
        if username.endswith("@nosa.me"):
            username = username.strip("@nosa.me")
        password = self.get_argument("password")

        ret_dict = dict() 
        demo = ldapauth.Auth()
        if demo.auth(username, password):
            email = username + "@nosa.me"
            self.set_secure_cookie("user", email, expires_days=30)
            ret_dict["result"] = "success"
        else:
            ret_dict["result"] = "error"
        self.write(json.dumps(ret_dict))


def get_postcustom(key):
    """ 获取 post custom 脚本内容.

    """
    from libs import redisoj
    from web.const import REDIS_DB_COMMON

    # REDIS_DB_COMMON 专门用于存储 user_data 信息.
    client = redisoj.RedisClient().get(REDIS_DB_COMMON)
    if client.exists(key):
        return json.loads(client.get(key))
    else:
        return None


class PostCustomHandler(tornado.web.RequestHandler):

    def get(self):
        key = self.get_argument('key')
        self.write(json.dumps(get_postcustom(key)))


HANDLERS = [
    # Ldap 认证.
    (r"/api/v1/ldapauth", LdapauthapiHandler), 
    # 物理机装机 API, 不是 RESTful API.
    (r"/api/v1/pm/check/?", pm_service.CheckHandler), 
    (r"/api/v1/pm/create/?", pm_service.CreateHandler),
    (r"/api/v1/pm/create_man/?", pm_service.CreateManHandler),
    (r"/api/v1/pm/message/?", pm_service.MessageHandler),
    # 虚拟机 master API.
    (r"/api/v1/vm/instances/?", vmmaster_service.InstancesHandler),
    (r"/api/v1/vm/instance/?", vmmaster_service.InstanceHandler),
    (r"/api/v1/vm/wmis/?", vmmaster_service.WmisHandler),
    (r"/api/v1/vm/wmi/([^/]+)/?", vmmaster_service.WmiHandler),
    (r"/api/v1/vm/query/?", vmmaster_service.QueryHandler),
    (r"/api/v1/vm/vmhs/?", vmmaster_service.VmhsHandler),
    (r"/api/v1/vm/ignores/?", vmmaster_service.IgnoresHandler),            
    (r"/api/v1/vm/ignores/([^/]+)/?", vmmaster_service.IgnoreHandler),
    # (r"/api/v1/vm/switches/?", vmmaster_service.SwitchesHandler),          
    (r"/api/v1/vm/resources/?", vmmaster_service.ResourcesHandler),
    # 用于获取装机之后的自定义脚本, 适用于物理机和虚拟机.
    (r"/api/v1/postcustom/?", PostCustomHandler)
]

SETTINGS = {
    "debug": False, 
    "cookie_secret": "z1DAVh+WTvy23pWGmOtJCQLETQYUznEuYskSF062J0To"
}

class Application(tornado.web.Application):

    def __init__(self):
        handlers = HANDLERS
        settings = SETTINGS

        tornado.web.Application.__init__(self, handlers, **settings)


from libs import log
logger = log.LogHandler().logger

MAX_WAIT_SECONDS_BEFORE_SHUTDOWN = 3600 * 2

def sig_handler(sig, frame):
    logger.info('Caught signal: %s', sig)
    tornado.ioloop.IOLoop.instance().add_callback(shutdown)

def shutdown():
    logger.info('Stopping http server')
    http_server.stop()

    logger.info('Will shutdown in %s seconds ...', MAX_WAIT_SECONDS_BEFORE_SHUTDOWN)
    io_loop = tornado.ioloop.IOLoop.instance()

    deadline = time.time() + MAX_WAIT_SECONDS_BEFORE_SHUTDOWN

    def stop_loop():
        now = time.time()
        if now < deadline and (io_loop._callbacks or io_loop._timeouts):
            io_loop.add_timeout(now + 1, stop_loop)
        else:
            io_loop.stop()
            logger.info('Shutdown')
    stop_loop()


def main():
    from tornado.options import define, options
    define("fd", default=None, help="File Descriptor given by circus", type=int)    
    tornado.options.parse_command_line()

    # 如果有 fd 选项, 表示使用 circus 启动.
    if options.fd is not None:
        sock = socket.fromfd(options.fd, 
            socket.AF_INET, socket.SOCK_STREAM)
    else:
        sockets = tornado.netutil.bind_sockets(BIND_PORT, 
            address=BIND_IP, family=socket.AF_INET)

    # 此处启动 8 个进程, 虽然对某些请求用了线程池(futures), 但是我在某些任务里也用了
    # 线程池(multiprocessing.dummy.Pool), 两处不能同时使用, 对于使用 multiprocessing
    # 而且处理时间很长(创建虚拟机)的任务, 就多开几个进程吧.
    # 如果不使用 circus, 创建8个进程.
    if options.fd is None:
        tornado.process.fork_processes(8)

    global http_server
    application = Application()
    http_server = tornado.httpserver.HTTPServer(application, xheaders=True)

    if options.fd is not None:
        http_server.add_socket(sock)
    else:
        http_server.add_sockets(sockets)

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
