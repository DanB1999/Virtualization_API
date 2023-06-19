from datetime import datetime
from typing import Union
import libvirt
from libvirt import libvirtError
from pydantic import BaseModel
import xml.dom.minidom    
from lxml import etree
from Exceptions import (
    APIError, ConnectionFailed, ResourceNotFound, 
    ResourceAlreadyRunning, ResourceNotRunning, ResourceRunning
)

class DomainObj(BaseModel):
    name: Union[str, None] = None
    memory: int
    vcpu: int
    source_file: str
    
    class Config:
            schema_extra = {
                "example": {
                    "name": "vm1",
                    "memory": 500000,
                    "vcpu": 1,
                    "source_file": "/var/lib/libvirt/isos/debian-11.6.0-amd64-netinst.iso"
                }
            }

class VM():   
    def list_vms(self):
        conn = self.libvirt_connect()
        domains = {}
        domains = conn.listAllDomains()
        jsonList = []
        for dom in domains:
            jsonList.append({"uuid": dom.UUIDString(),
                            "name": dom.name(),
                            "isActive": dom.isActive(),
                            "status": self.get_vm_status(dom).get("desc"),
                            "isPersistent": dom.isPersistent()})
        return jsonList
    
    def list_snapshots(self, id):
        conn = self.libvirt_connect()
        dom = self.get_vm(id)
        snapshots = dom.listAllSnapshots()
        jsonList = []
        for elem in snapshots:
            xmlDesc = etree.fromstring(elem.getXMLDesc())
            creationTime = datetime.fromtimestamp(int(xmlDesc.find("creationTime").text))
            jsonList.append({"name": elem.getName(),
                             "timestamp": creationTime,
                             "state": xmlDesc.find("state").text,
                             "isCurrent": elem.isCurrent(),
                             "memorySnapshot": xmlDesc.find("memory").get("snapshot")})                             
        return jsonList
    
    def list_storage_vol(self):
        conn = self.libvirt_connect()
        pool = conn.storagePoolLookupByName("default")
        if pool == None:
            raise APIError("Failed to locate any StoragePool objects")
        stgvols = pool.listVolumes()
        jsonList = []
        for stgvolname in stgvols:
            stgvol = pool.storageVolLookupByName(stgvolname)
            info = stgvol.info()
            jsonList.append({"name": stgvolname,
                             "path": stgvol.path(),
                             "Type": str(info[0]),
                             "Capacity": str(info[1]),
                             "Allocation": str(info[2])})
        return jsonList

    def get_vm_info(self, id):
        conn = self.libvirt_connect()
        dom = self.get_vm(id)
        state, maxmem, mem, cpus, cput = dom.info()
        return {"uuid": dom.UUIDString(),
                "name": dom.name(),
                "isActive": dom.isActive(),
                "status": self.get_vm_status(dom).get("desc"),
                "isPersistent": dom.isPersistent(),
                "OSType": dom.OSType(),
                "hasCurrentSnapshot": dom.hasCurrentSnapshot(),
                "hardware_info": {
                    "state": str(state),
                    "maxMemory": str(maxmem),
                    "memory": str(mem),
                    "cpuNum": str(cpus),
                    "cpuTime": str(cput)}}

    def start_vm(self, id, revertSnapshot):
        conn = self.libvirt_connect()
        dom = self.get_vm(id)
        try:
            if revertSnapshot:
                snapshot = dom.snapshotLookupByName(revertSnapshot)
                dom.revertToSnapshot(snapshot)
                return "Sucessfully reverted " + revertSnapshot
            state = self.get_vm_status(dom).get("state")
            if state == 3:
                dom.resume()
                return "VM sucessfully resumed"
            elif state == 5:
                dom.create()
                return "VM sucessfully restarted"
            elif state == 1:
                raise ResourceAlreadyRunning()
        except libvirtError as e:
            raise APIError(str(e))            
    
    def stop_vm(self, id):
        conn = self.libvirt_connect()
        dom = self.get_vm(id)
        try:
            state = self.get_vm_status(dom).get("state")
            if state == 1:
                dom.suspend()
                return "VM sucessfully stopped"
            else:
                raise ResourceNotRunning()
        except libvirtError as e:
            raise APIError(str(e))
            
    def reboot_vm(self, id):
        conn = self.libvirt_connect()
        dom = self.get_vm(id)
        try:
            state = self.get_vm_status(dom).get("state")
            if state == 1:
                dom.reboot()
                return "VM sucessfully rebooted"
            else:
                raise ResourceNotRunning()
        except libvirtError as e:
            raise APIError(str(e))
            
    def shutdown_vm(self, id, save, force):
        conn = self.libvirt_connect()
        dom = self.get_vm(id)
        try:
            state = self.get_vm_status(dom).get("state")      
            if state == 1:
                if save:
                    dom.managedSave()
                    return "VM sucessfully saved"
                elif force:
                    dom.destroy()
                    return "VM was forced to shutdown"
                else:    
                    dom.shutdown()
                    return "VM sucessfully shutdown"
            else:
                raise ResourceNotRunning()                    
        except libvirtError as e:
            raise APIError(str(e))  

    def delete_vm(self, id):
        conn = self.libvirt_connect()
        dom = self.get_vm(id)
        try:
            state = self.get_vm_status(dom).get("state")      
            if state != 1:
                dom.undefine()
                return "Requested Ressource was sucessfully deleted"
            else:
                raise ResourceRunning()
        except libvirtError as e:
            raise APIError(str(e))
    
    def delete_snapshot(self, id, name):
        conn = self.libvirt_connect()
        dom = self.get_vm(id)
        try:
            snapshot = dom.snapshotLookupByName(name)
            snapshot.delete()
            return "Snapshot " + name + " sucessfully deleted"
        except libvirtError as e:
            raise APIError(str(e))
    
    def delete_storage_vol(self, id):
        conn = self.libvirt_connect()
        dom = self.get_vm(id)
        try:
            pool = conn.storagePoolLookupByName("default")
            if pool == None:
                raise APIError("Failed to locate any StoragePool objects.")
            state = self.get_vm_status(dom).get("state")      
            if state != 1:
                stgvol = pool.storageVolLookupByName(dom.name()+".qcow2")
                stgvol.delete()
                return "Storage volume sucessfully created"
            else:
                raise ResourceRunning()
        except libvirtError as e:
            raise APIError(str(e))          
        
    def run_vm_xml(self, body):
        conn = self.libvirt_connect()
        xmlconfig = xml.dom.minidom.parseString(body)
        new_xml = xmlconfig.toprettyxml()
        try:
            dom = conn.defineXMLFlags(new_xml, 0)
            dom.create()
            return {"Following guest sucessfully booted": {"Id" : dom.UUIDString(), "Name": dom.name()},
                    "info": "For further parameters visit: https://libvirt.org/formatdomain.html"}
        except libvirtError as e:
            raise APIError(str(e))

    def run_vm_json(self, obj: BaseModel):
        conn = self.libvirt_connect()
        dict = obj.dict() 
        xmlconfig = f"""
            <domain type='kvm'>
            ​   <name>{dict.get("name")}</name>
            ​   <memory>{dict.get("memory")}</memory>
            ​   <vcpu>{dict.get("vcpu")}</vcpu>
            ​   <os>
            ​       <type>hvm</type>             
​                   <boot dev='hd'/>
                   <boot dev='cdrom'/>
               </os>
            ​   <clock offset='utc'/>
            ​   <on_poweroff>destroy</on_poweroff>
            ​   <on_reboot>restart</on_reboot>
            ​   <on_crash>destroy</on_crash>
            ​   <devices>
            ​       <emulator>/usr/bin/qemu-system-x86_64</emulator>
            ​       <disk type='file' device='cdrom'>
            ​          <source file='{dict.get("source_file")}'/>
            ​          <driver name='qemu' type='raw'/>          
            ​          <target dev='hda'/>
            ​        </disk>
                    <disk type='file' device='disk'>
                      <driver name='qemu' type='qcow2'/>
                      <source file='/var/lib/libvirt/images/{dict.get("name")}.qcow2'/>
                      <target dev='vda'/>
                    </disk>
                    <interface type='network'>
                        <source network='default'/>
                    </interface>
            ​        <input type='mouse' bus='ps2'/>
            ​        <graphics type='vnc' port='-1' listen='127.0.0.1'/>
            ​    </devices>
            ​</domain>"""
        try:
            dom = conn.defineXMLFlags(xmlconfig, 0)
            dom.create()
            if dom:
                return {"Following guest sucessfully booted": {"Id" : dom.UUIDString(), "Name": dom.name()},
                        "info": "For further parameters visit: https://libvirt.org/formatdomain.html"}
        except libvirtError as e:
            raise APIError(str(e))

    def create_snapshot(self, id, snapshot_name):
        conn = self.libvirt_connect()
        dom = self.get_vm(id)
        xmlconfig = f"""
            <domainsnapshot>
                <name>{snapshot_name}</name>
            </domainsnapshot>"""
        try:
            dom.snapshotCreateXML(
                xmlconfig.format(snapshot_name=snapshot_name),
                libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_ATOMIC
            )
            return "Snaphot of " + dom.name() + " was sucessfully created"
        except libvirtError as e:
            raise APIError(str(e))  

    def create_storage_vol(self, name):
        conn = self.libvirt_connect()
        xmlconfig = f"""
            <volume type='file'>
                <name>{name}.qcow2</name>
                <allocation>0</allocation>
                <capacity>0</capacity>
                <target>
                    <path>/var/lib/virt/images/{name}.qcow2</path>
                    <format type='qcow2'/>
                    <permissions>
                        <owner>107</owner>
                        <group>107</group>
                        <mode>0744</mode>
                        <label>vir_image_t</label>
                    </permissions>
                </target>
            </volume>"""
        try:
            pool = conn.storagePoolLookupByName("default")
            stgvol = pool.createXML(xmlconfig, 0)
            return "Storage volume sucessfully created "
        except libvirtError as e:
            raise APIError(str(e))
        
    def libvirt_connect(self):
        try:
            conn = libvirt.open('qemu:///system')
            return conn
        except libvirt.libvirtError:
            raise ConnectionFailed()
    
    def get_vm(self, id):
        conn = self.libvirt_connect()
        try:
            return conn.lookupByUUIDString(id)
        except libvirtError:
            raise ResourceNotFound()
    
    def get_vm_snapshots(self, id):
        conn = self.libvirt_connect()
        dom = self.get_vm(id)
        try:
            return dom.listAllSnapshots()
        except libvirtError as e:
            raise APIError(e.args[0])

    def get_vm_status(self, dom):
        state, maxmem, mem, cpus, cput = dom.info()
        str = ""
        if state == 1:
            str = "Running"
        elif state == 3:
            str = "Stopped(Paused)"
        elif state == 5:
            str = "Not Running"
        return {"state": state,
                "desc": str}
