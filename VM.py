import sys
from typing import Union
import libvirt
from libvirt import virDomain, libvirtError
from pydantic import BaseModel
import xml.dom.minidom

from exceptions import APIError, ConnectionFailed, DomainAlreadyRunning, DomainNotRunning, RessourceNotFound

class DomainObj(BaseModel):
    name: Union[str, None] = None
    memory: int
    vcpu: int
    source_file: str
    emulator: str
    
    class Config:
            schema_extra = {
                "example": {
                    "name": "vm1",
                    "memory": 500000,
                    "vcpu": 1,
                    "source_file": "/var/lib/libvirt/isos/debian-11.6.0-amd64-netinst.iso",
                    "emulator": "/usr/bin/qemu-system-x86_64"
                }
            }

class VM():   
    def libvirtConnect(self):
        try:
            conn = libvirt.open('qemu:///system')
            return conn
        except libvirt.libvirtError:
            raise ConnectionFailed()

    def getDomainByUUID(self, id):
        conn = self.libvirtConnect()
        domains = conn.listAllDomains()
        for dom in domains:
            uuid = dom.UUIDString()
            if uuid == id:
                return dom
        raise RessourceNotFound()
            
    def listDomains(self):
        conn = self.libvirtConnect()
        try:
            domains = {}
            domains = conn.listAllDomains()
            res = []
            for dom in domains:
                uuid = dom.UUIDString()
                res.append({"uuid": uuid,
                                "name": dom.name(),
                                #"hostname": domain.hostname(),
                                "isActive": dom.isActive(),
                                "status": self.getDomStatus(dom).get("desc"),
                                "isPersistent": dom.isPersistent()
                                })
            return res
        except libvirtError as e:
            res = repr(e)
            return res

    def getDomainStats(self, id):
        conn = self.libvirtConnect()
        dom = self.getDomainByUUID(id)
        state, maxmem, mem, cpus, cput = dom.info()
        return {"uuid": dom.UUIDString(),
                "name": dom.name(),
                #"hostname": dom.hostname(),
                "isActive": dom.isActive(),
                "status": self.getDomStatus(dom).get("desc"),
                "isPersistent": dom.isPersistent(),
                "OSType": dom.OSType(),
                "hasCurrentSnapshot": dom.hasCurrentSnapshot(),
                "hardware_info": {
                    "state": str(state),
                    "maxMemory": str(maxmem),
                    "memory": str(mem),
                    "cpuNum": str(cpus),
                    "cpuTime": str(cput)
                }
                }
    

#VM nach start immernoch pausiert (im virt-manager)

    def startVM(self, id):
        conn = self.libvirtConnect()
        dom = self.getDomainByUUID(id)
        #stream=self.conn.newStream(libvirt.VIR_STREAM_NONBLOCK)
        #domain.openConsole(None,stream, 0)
        try:
            state = self.getDomStatus(dom)
            #dom.create()   #virDomainRestore /virDomainResume
            if state == 3:
                dom.resume()   #virDomainRestore /virDomainResume
                return "VM sucessfully resumed"
            elif state == 5:
                dom.create()
                return "VM sucessfully restarted"
            elif state == 1:
                raise DomainAlreadyRunning()

        except libvirtError as e: #Except: Domain is already running
            return e                
        #domain.reboot() 
    
    def stopVM(self, id):
        conn = self.libvirtConnect()
        dom = self.getDomainByUUID(id)
        try:
            state = self.getDomStatus(dom)
            if state == 1:
                dom.suspend() #suspend- speichert das persistente Image nicht 
                return "VM sucessfully stopped"
            else:
                raise DomainNotRunning()
        except libvirtError as e:
            return e
            
    def shutdownVM(self, id, save):
        conn = self.libvirtConnect()
        dom = self.getDomainByUUID(id)
        try:
            if save:
                dom.managedSave()
                return "VM sucessfully saved"
            else:
                dom.destroy() #Erzwingt das Herunterfahren
            return "VM sucessfully shutdown"
        except libvirtError as e:
            if e.get_error_code() == 55:
                raise DomainNotRunning()

    def deleteVM(self, id):
        conn = self.libvirtConnect()
        dom = self.getDomainByUUID(id)
        try:
            dom.undefine()
            #Aktive Vm wird lediglich pausiert
            if dom.isActive == False:
                return "VM was paused, not deleted" 
            return "VM was sucessfully deleted"
        except libvirtError as e:
            raise APIError(str(e)) ## Error: Cannot undefine transient domain -> Wenn VM am laufen ist?
        
    def runVM_xml(self, body):
            conn = self.libvirtConnect()
            xmlconfig = xml.dom.minidom.parseString(body)
            new_xml = xmlconfig.toprettyxml()
            dom = None
            try:
                dom = self.conn.defineXMLFlags(new_xml, 0)
                dom.create()
                return {"Following guest sucessfully booted": {"Id" : dom.UUIDString(), "Name": dom.name()},
                        "info": "For further parameters visit: https://libvirt.org/formatdomain.html"}
            except libvirtError as e:
                raise APIError(str(e))

    def runVM_json(self, obj: BaseModel):
        conn = self.libvirtConnect()
        dict = obj.dict() 
        xmlconfig = f'''
          <domain type='kvm'>
        ​  <name>{dict.get("name")}</name>
        <!--
        ​  <uuid>c7a5fdbd-cdaf-9455-926a-d65c16db1809</uuid>
        500000 memory
        -->
        ​  <memory>{dict.get("memory")}</memory>
        
        ​  <vcpu>{dict.get("vcpu")}</vcpu>
        ​  <os>
        ​  <type arch='x86_64' machine='pc'>hvm</type>
        ​  <boot dev='hd'/>
        ​  <boot dev='cdrom'/>
        ​</os>
        ​  <clock offset='utc'/>
        ​  <on_poweroff>destroy</on_poweroff>
        ​  <on_reboot>restart</on_reboot>
        ​  <on_crash>destroy</on_crash>
        ​  <devices>
        ​    <emulator>{dict.get("emulator")}</emulator>
        ​    <disk type='file' device='disk'>
        ​      <source file='{dict.get("source_file")}'/>
        ​      <driver name='qemu' type='raw'/>
        ​      <target dev='hda'/>
        ​    </disk>
        <!--
           <interface type='bridge'>
        ​      <mac address='52:54:00:d8:65:c9'/>
        ​      <source bridge='br0'/>
        ​    </interface>
        -->
        ​    <input type='mouse' bus='ps2'/>
        ​    <graphics type='vnc' port='-1' listen='127.0.0.1'/>
        ​  </devices>
        ​</domain>'''
        
        dom = None
        try:
            dom = conn.defineXMLFlags(xmlconfig, 0)
            dom.create()
            return {"Following guest sucessfully booted": {"Id" : dom.UUIDString(), "Name": dom.name()},
                    "info": "For further parameters visit: https://libvirt.org/formatdomain.html"}
            #dom.openGraphics()
            #dom.openConsole()
        except libvirtError as e:
            raise APIError(str(e))
        
    def getXMLConfig(self, part: str | None = None):
        xmlConfig = ""
        return xmlConfig
    
    def getHardwareSpecs(self, part: str | None = None):
        if part:
            hardwareSpecs = part
        else: 
            hardwareSpecs = "Hello World"
        return hardwareSpecs
    
    def getDomStatus(self, dom):
        state, maxmem, mem, cpus, cput = dom.info()
        str = ""
        if state == 1:
            str = "Running"
        elif state == 3:
            str = "Stopped(Paused)"
        elif state == 5:
            str = "Not Running"
        return {"state": state,
                "desc": str
                }#1 = Running, 3 = paused, 5 = saved, shutoff






