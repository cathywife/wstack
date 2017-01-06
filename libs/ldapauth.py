#-*- coding: utf-8 -*-

import ldap
import sys
import base64
import hashlib
import binascii


from settings import LDAP_HOST, LDAP_DN, LDAP_USER


class Auth(object):

    def __init__(self, ldap_host=LDAP_HOST):
        self.ldap_host = ldap_host

    def auth(self, user, passwd):
        self.dn = 'uid=%s,ou=People,dc=DOMAIN,dc=com' % user
        self.ldapconn = ldap.initialize('ldap://%s' % self.ldap_host)
        try:
            self.ldapconn.simple_bind_s(self.dn, passwd)
            self.ldapconn.unbind()
            return True
        except Exception, e:
            self.ldapconn.unbind()
            return False
