import sys
from typing import Union
import libvirt
from libvirt import virDomain, libvirtError
from pydantic import BaseModel
import xml.dom.minidom

from exceptions import APIError, ConnectionFailed, DomainAlreadyRunning, DomainNotRunning, RessourceNotFound, RessourceRunning

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
    def listDomains(self):
        conn = self.libvirtConnect()
        domains = {}
        domains = conn.listAllDomains()
        jsonList = []
        for dom in domains:
            jsonList.append({"uuid": dom.UUIDString(),
                            "name": dom.name(),
                            #"hostname": domain.hostname(),
                            "isActive": dom.isActive(),
                            "status": self.getDomStatus(dom).get("desc"),
                            "isPersistent": dom.isPersistent()
                            })
        return jsonList

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

    def startVM(self, id, revertSnapshot):
        conn = self.libvirtConnect()
        dom = self.getDomainByUUID(id)
        #stream=self.conn.newStream(libvirt.VIR_STREAM_NONBLOCK)
        #domain.openConsole(None,stream, 0)
        try:
            if revertSnapshot:
                snapshot = dom.snapshotLookupByName(revertSnapshot)
                dom.revertToSnapshot(snapshot)
                return "Sucessfully reverted " + revertSnapshot
            state = self.getDomStatus(dom).get("state")
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
            state = self.getDomStatus(dom).get("state")
            if state == 1:
                dom.suspend() #suspend- speichert das persistente Image nicht 
                return "VM sucessfully stopped"
            else:
                raise DomainNotRunning()
        except libvirtError as e:
            return e
        
    def createSnapshot(self, id, snapshot_name):
        conn = self.libvirtConnect()
        dom = self.getDomainByUUID(id)
        SNAPSHOT_XML_TEMPLATE = """
                                <domainsnapshot>
                                    <name>{snapshot_name}</name>
                                    <!--
                                    <disks>
                                        <disk name='vda'>
                                        <driver type='raw'/>
                                        <source file='/var/lib/libvirt/snapshots'/>
                                        </disk>
                                        
                                        <disk name='vdb' snapshot='no'/>
                                        <disk name='vdc'>
                                        <source file='/path/to/newc'>
                                            <seclabel model='dac' relabel='no'/>
                                        </source>
                                        </disk>
                                        
                                    </disks>
                                    -->
                                </domainsnapshot>
                                """
        try:
            dom.snapshotCreateXML(
                SNAPSHOT_XML_TEMPLATE.format(snapshot_name=snapshot_name),
                libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_ATOMIC
            )
        except Exception as e:
            return e

            
    def shutdownVM(self, id, save):
        conn = self.libvirtConnect()
        dom = self.getDomainByUUID(id)
        try:
            state = self.getDomStatus(dom).get("state")      
            if state == 1:
                if save:
                    dom.managedSave()
                    return "VM sucessfully saved"
                else:
                    dom.destroy() #Erzwingt das Herunterfahren
                    return "VM sucessfully shutdown"
            else:
                raise DomainNotRunning()                    
        except libvirtError as e:
            return e    
        #Requested Domain is not runnning

        #Wenn die Vm gelöscht werden soll:  "Requested operation is not valid: cannot undefine transient domain" --> Herunterfahren nicht möglich


    def deleteVM(self, id):
        conn = self.libvirtConnect()
        dom = self.getDomainByUUID(id)
        try:
            #Aktive Vm wird lediglich pausiert
            state = self.getDomStatus(dom).get("state")      
            if state != 1:
                dom.undefine()
                return "Requested Ressource was sucessfully deleted"
            else:
                raise RessourceRunning()
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
        ​  <type>hvm</type>             <!--arch='x86_64' machine='pc'-->
        ​  <boot dev='hd'/>
            <boot dev='cdrom'/>
        ​</os>
        ​  <clock offset='utc'/>
        ​  <on_poweroff>destroy</on_poweroff>
        ​  <on_reboot>restart</on_reboot>
        ​  <on_crash>destroy</on_crash>
        ​  <devices>
        ​    <emulator>{dict.get("emulator")}</emulator>
        ​    <disk type='file' device='cdrom'>
        ​      <source file='{dict.get("source_file")}'/>
        ​      <driver name='qemu' type='raw'/>                 <!--qcow2????-->
        ​      <target dev='hda'/>
        ​    </disk>
            <disk type='file' device='disk'>
                <driver name='qemu' type='qcow2'/>
                <source file='/var/lib/libvirt/images/{dict.get("name")}.qcow2'/>           <!-- qemu-img create -f qcow2 vm4.qcow2 10G -->
                <target dev='vda'/>
            </disk>
            <interface type='network'>
                <source network='default'/>
            </interface>
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
    
    def editDomain(self):
        conn = self.libvirtConnect()
        dom = self.getDomainByUUID(id)


    
    def getHardwareSpecs(self, part: str | None = None):
        if part:
            hardwareSpecs = part
        else: 
            hardwareSpecs = "Hello World"
        return hardwareSpecs

    def libvirtConnect(self):
        try:
            conn = libvirt.open('qemu:///system')
            return conn
        except libvirt.libvirtError:
            raise ConnectionFailed()
    
    def getDomainByUUID(self, id):
        conn = self.libvirtConnect()
        try:
            return conn.lookupByUUIDString(id)
        except:
            raise RessourceNotFound()

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
