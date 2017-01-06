# -*- coding: utf-8 -*-

import urllib2
import cookielib
import urllib
import ujson as json


from settings import (DNS_HOST, DNS_AUTH_API, 
                       DNS_AUTH_USERNAME, DNS_AUTH_PASSWD)


class DnsApi(object):
    def __init__(self, host_url=DNS_HOST, username=DNS_AUTH_USERNAME, 
                 password=DNS_AUTH_PASSWD, auth_uri=DNS_AUTH_API):
        self.is_login = False
        self.host_url = host_url
        self.username = username
        self.password = password
        self.auth_uri = auth_uri

        self.login()
        if not self.is_login:
            raise Exception("asset auth fail")

    def login(self):
        auth_url = r"http://" + self.host_url + r"/" + self.auth_uri
        cookie = cookielib.CookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie))
        urllib2.install_opener(opener)
        data = urllib.urlencode({"username": self.username, 'password': self.password})
        login_response = urllib2.urlopen(auth_url, data)
        response = login_response.read()

        ret_dict = json.loads(response)

        if ret_dict["result"] == "success":
            self.is_login = True
        else:
            self.is_login = False

    def post_wrapper(self, url, data_dict):
        data = urllib.urlencode(data_dict)
        visit_url = r"http://" + self.host_url + r"/" + url
        login_response = urllib2.urlopen(visit_url, data)
        response = login_response.read()
        ret_dict = json.loads(response)

        return ret_dict

    def get_wrapper(self, url, data_dict):
        data = urllib.urlencode(data_dict)
        visit_url = r"http://" + self.host_url + r"/" + url
        login_response = urllib2.urlopen(visit_url + "?" + data)
        response = login_response.read()
        ret_dict = json.loads(response)

        return ret_dict


def record_exist(hostname):
    uri = "api/v1/query"
    data_dict = {
        "key": "hostname",
        "dnslist": json.dumps([hostname])
    }

    _object = DnsApi()
    ret = _object.get_wrapper(uri, data_dict)
    if ret["status"] == "success":
        if ret["result"][0]["ip"] != []:
            return True
    return False


def record_delete(hostname):
    uri = "api/v1/delete"
    data_dict = {
        "key": "hostname",
        "dnslist": json.dumps([hostname])
    }
    _object = DnsApi()
    ret = _object.post_wrapper(uri, data_dict)
    if ret["status"] != "success":
        raise Exception("delete dns of {hostname} fail".format(hostname=hostname))


def record_add(hostname, ip):
    uri = "api/v1/add"
    data_dict = {
        "dnslist": json.dumps([{"hostname": hostname, "ip": ip}])
    }
    _object = DnsApi()
    ret = _object.post_wrapper(uri, data_dict)
    if ret["status"] != "success":
        raise Exception("add dns of {hostname},{ip} fail".format(hostname=hostname, ip=ip))
