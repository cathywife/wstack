#!/bin/env python
#-*- coding: utf-8 -*-

import SocketServer
from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler

from libs import resource, instance, wmi


class ThreadXMLRPCServer(SocketServer.ThreadingMixIn, SimpleXMLRPCServer): pass


class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ('/vmagent',)


def main():
    server = ThreadXMLRPCServer(("0.0.0.0", 8000),
                                requestHandler=RequestHandler,
                                allow_none=True)
        
    server.register_function(resource.vmlist, "resource_vmlist")
    server.register_function(resource.vcpu, "resource_vcpu")
    server.register_function(resource.mem, "resource_mem")
    server.register_function(resource.space, "resource_space")
    server.register_function(resource._type, "resource_type")

    server.register_function(instance.create, 'instance_create')
    server.register_function(instance.delete, 'instance_delete')
    server.register_function(instance.shutdown, 'instance_shutdown')
    server.register_function(instance.reboot, 'instance_reboot') 

    server.register_function(wmi.create, "wmi_create")

    server.serve_forever()


if __name__ == '__main__':
    main()