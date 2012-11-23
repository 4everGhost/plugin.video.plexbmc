import select
import socket
import sys
import pybonjour

#global mDNSresult
#mDNSresult=[]

class bonjourFind:

    def query_record_callback(self, sdRef, flags, interfaceIndex, errorCode, fullname,
                              rrtype, rrclass, rdata, ttl):
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            #print '  IP         =', socket.inet_ntoa(rdata)
            self.queried.append(True)
            self.bonjourIP.append(socket.inet_ntoa(rdata))
            self.complete = True


    def resolve_callback(self, sdRef, flags, interfaceIndex, errorCode, fullname,
                         hosttarget, port, txtRecord):
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            return

        #print 'Resolved service:'
        #print '  fullname   =', fullname.encode('utf-8')
        #print '  hosttarget =', hosttarget.encode('utf-8')
        #print '  port       =', port

        self.bonjourName.append(fullname)
        self.bonjourPort.append(str(port))
        
        query_sdRef = \
            pybonjour.DNSServiceQueryRecord(interfaceIndex = interfaceIndex,
                                            fullname = hosttarget,
                                            rrtype = pybonjour.kDNSServiceType_A,
                                            callBack = self.query_record_callback)

        try:
            while not self.queried:
                ready = select.select([query_sdRef], [], [], self.timeout)
                if query_sdRef not in ready[0]:
                    print "PleXBMC -> pyBonjour -> Query record timed out"
                    break
                pybonjour.DNSServiceProcessResult(query_sdRef)
            else:
                self.queried.pop()
        finally:
            query_sdRef.close()

        self.resolved.append(True)


    def browse_callback(self, sdRef, flags, interfaceIndex, errorCode, serviceName,
                        regtype, replyDomain):
        if errorCode != pybonjour.kDNSServiceErr_NoError:
            return

        if not (flags & pybonjour.kDNSServiceFlagsAdd):
            print 'Service removed'
            return

        #print 'Service added; resolving'

        resolve_sdRef = pybonjour.DNSServiceResolve(0,
                                                    interfaceIndex,
                                                    serviceName,
                                                    regtype,
                                                    replyDomain,
                                                    self.resolve_callback)

        try:
            while not self.resolved:
                ready = select.select([resolve_sdRef], [], [], self.timeout)
                if resolve_sdRef not in ready[0]:
                    print "PleXBMC -> pyBonjour -> Query timed out"
                    break
                pybonjour.DNSServiceProcessResult(resolve_sdRef)
            else:
                self.resolved.pop()
        finally:
            resolve_sdRef.close()

    def __init__(self, type, timeout=3):   
            
        regtype  = type
        self.complete = False
        self.bonjourName = []
        self.bonjourPort = []
        self.bonjourIP = []
        self.timeout  = timeout
        self.queried  = []
        self.resolved = []
                
        print "PleXBMC -> pyBonjour -> timeout set to %s" % timeout
                
        browse_sdRef = pybonjour.DNSServiceBrowse(regtype = regtype,
                                                  callBack = self.browse_callback)

        try:
            try:
                while True:
                    ready = select.select([browse_sdRef], [], [], self.timeout)
                    if browse_sdRef in ready[0]:
                        pybonjour.DNSServiceProcessResult(browse_sdRef)
                        break
                    else:
                        print "PleXBMC -> pyBonjour -> Resolve timed out"
                        break
            except:             
                pass
        finally:
            browse_sdRef.close()
            

