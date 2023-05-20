import sys
import libvirt
from libvirt import virDomain, libvirtError
from pydantic import BaseModel


class VM():
    def __init__(self):
        try:
            self.conn=libvirt.open("qemu:///system")
        except libvirtError as e:
            print(repr(e), file = sys.stderr)
            exit(1)

    def checkConnection(self):
        return 0

    def listDomains(self):
        domains = {}
        try:
            domains = self.conn.listAllDomains()
            res = []
            for dom in domains:
                uuid = dom.UUIDString()
                res.append({"uuid": uuid,
                                "name": dom.name(),
                                #"hostname": domain.hostname(),
                                "isActive": dom.isActive(),
                                "isPersistent": dom.isPersistent()
                                })
            return res
        except libvirtError as e:
            res = repr(e)
        return res

    def getDomainStats(self, id):
        dom = self.getDomainByUUID(id)
        state, maxmem, mem, cpus, cput = dom.info()
        return {"uuid": dom.UUIDString(),
                "name": dom.name(),
                #"hostname": dom.hostname(),
                "isActive": dom.isActive(),
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
    


    def startVM(self, id):
        domain = self.getDomainByUUID(id)
        #stream=self.conn.newStream(libvirt.VIR_STREAM_NONBLOCK)
        #domain.openConsole(None,stream, 0)
        try:
            res = domain.create()   #virDomainRestore /virDomainResume
        except libvirtError as e:
            raise RuntimeError("VM is already running")
    #domain.reboot() 
    
    def stopVM(self, id):
        domain = self.getDomainByUUID(id)
    
        return domain.suspend() #suspend- speichert das persistente Image nicht 
        #.managedSave()

    def shutdownVM(self, id):
        domain = self.getDomainByUUID(id)
        return domain.destroy() #Erzwingt das Herunterfahren

    def runVM(self, obj: BaseModel):
        dict = obj.dict() 
        xmlconfig = f'''<domain type='kvm'>
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
        ​    <emulator>/usr/bin/qemu-system-x86_64</emulator>
        ​    <disk type='file' device='disk'>
        ​      <source file='{dict.get("source_file")}'/>
        ​      <driver name='qemu' type='raw'/>
        ​      <target dev='hda'/>
        ​    </disk>
        <!--
        ​    <interface type='bridge'>
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
            dom = self.conn.defineXMLFlags(xmlconfig, 0)
        except libvirt.libvirtError as e:
            return e
        if dom.create() < 0:
            return "Can not boot guest domain"

        return "Guest "+ dom.name() + "has booted"

    def getDomainByUUID(self, id):
        domains = self.conn.listAllDomains()
        for dom in domains:
            uuid = dom.UUIDString()
            if uuid == id:
                return dom



