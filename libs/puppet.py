# -*- coding: utf-8 -*-

from requests import Request, Session

from settings import PUPPET_CA_HOST, PUPPET_DOMAIN


def check_puppet_cert(hostname):
    hostnames = [
        hostname,
        hostname + PUPPET_DOMAIN,
        hostname.split(".")[0],
        hostname.split(".")[0] + PUPPET_DOMAIN
    ]
    for h in hostnames:
        if get_puppet_cert(h) == 200:
            if delete_puppet_cert(h) != 200:
                raise Exception("{0} cert delete fail".format(h))


def get_puppet_cert(hostname):
    """ 查看给定机器的证书信息.

    curl 命令格式如下:
        curl -k -H 'Accept: pson' https://PUPPET_CA_HOST/production/certificate_status/hostname

    """
    url = "https://{puppet_ca_host}/production/certificate_status/{hostname}".format(
        puppet_ca_host=PUPPET_CA_HOST, hostname=hostname)
    s = Session()
    req = Request('GET', url,
        headers={"Accept": "pson"}
    )
    prepped = req.prepare()
    r = s.send(prepped,
        verify=False,
    )
    return r.status_code


def delete_puppet_cert(hostname):
    """ 删除给定机器的证书.

    curl 命令格式如下:
        curl -k -X DELETE -H 'Accept: pson' https://PUPPET_CA_HOST/production/certificate_status/hostname

    """
    url = "https://{puppet_ca_host}/production/certificate_status/{hostname}".format(
        puppet_ca_host=PUPPET_CA_HOST, hostname=hostname)
    s = Session()
    req = Request('DELETE', url,
        headers={"Accept": "pson"}
    )
    prepped = req.prepare()
    r = s.send(prepped,
        verify=False,
    )
    return r.status_code
