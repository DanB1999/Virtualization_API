import docker 
from docker import errors
import json


class Docker():
    def __init__(self):
        self.client = docker.from_env()

########List all running container instances########
    def getContainerList(self, showAll):
        list = self.client.containers.list(all=showAll)
        jsonList = []
        for i in range(0 , list.__len__()):
            x = { 
                "Id" : list[i].short_id,
                "Name": list[i].attrs['Name'],
                "Image": list[i].attrs['Config']['Image'],
                "Status": list[i].attrs['State']['Status'],
                }
            jsonList.append(x)
        return jsonList

########Get container attributes by ID#############
    def getContainerStats(self, id):
        container = self.client.containers.get(id)
        return container.attrs  #Modify with stats()

########Start Container by ID######################
    def startContainer(self, id):
        try:
            container = self.client.containers.get(id)
        except errors.NotFound as es:
            raise RuntimeError("Container not found")
        else:
            return container.start()

########Stop Container by ID######################
    def stopContainer(self, id):
        try:
            container = self.client.containers.get(id)
        except errors.NotFound as es:
            raise RuntimeError("Container not found")
        else:
            return container.stop()

########Remove Container by ID######################
    def removeContainer(self, id):
        try:
            container = self.client.containers.get(id)
        except errors.NotFound as es:
            raise RuntimeError("Container not found")
        else:
            return container.remove(force = True)
        
########Remove Container by ID######################
    def pruneContainers(self):
        try:
            return {"Response": "Folgende Container wurden erfolgreich gelöscht",
                    "obj":self.client.containers.prune()}
        except Exception as e:
            return {"Error": "002", "Message": "Beim Löschen des Container ist ein Fehler aufgetreten"}

        

    
########Create container by Image#############
    def createContainer(self, image, attr):
        
        try:
            obj = self.client.containers.create(image, detach = attr.detach, ports = {'5000/tcp':attr.ports} )
            res = {"Id" : obj.attrs.get('Id'), "Name": obj.attrs.get('Name')}
            return res
        except: 
            res = {"Error": "003", "Message": "Beim Erstellen des Container ist ein Fehler aufgetreten"}
            return res
        
########Run container by Image#############
    def runContainer(self, image, attr):
        
        try:
            obj = self.client.containers.run(image, detach = attr.detach, ports = {'5000/tcp':attr.ports} )
            res = {"Id" : obj.attrs.get('Id'), "Name": obj.attrs.get('Name')}
            return res
        except: 
            res = {"Error": "004", "Message": "Beim Starten des Container ist ein Fehler aufgetreten"}
            return res