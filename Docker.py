import docker
from docker import errors
from pydantic import BaseModel, Extra
from exceptions import APIError, ArgumentNotFound, ImageNotFound, RessourceNotFound

class ContainerObj(BaseModel):
    name: str | None = None #Wenn kein key im request vorhanden setzt der den Wert auf NULL
    ports: object | None = None#Assign random host port 
    volumes: list[str | None ]= None
    detach: bool = True

    class Config:
        schema_extra = {
            "example": {
                "name": "Container1",
                "ports": {'5000/tcp':1000 },
                "volumes": ["/home/user1/:/mnt/vol2"],
                "detach": True
            }
        }
        extra = Extra.allow     #Erlaubt das Hinzufügen zusätzlicher Felder



class Docker():
    def __init__(self):
        self.client = docker.from_env()

########List all running container instances#######
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
        try:
            container = self.client.containers.get(id)
            return container.attrs  #Modify with stats()
        except errors.NotFound:
            raise RessourceNotFound() 


########Start Container by ID######################
    def startContainer(self, id):
        try:
            container = self.client.containers.get(id)
            container.start()
            return "Container sucessfully started"
        except errors.NotFound:
            raise RessourceNotFound()

########Stop Container by ID#######################
    def stopContainer(self, id):
        try:
            container = self.client.containers.get(id)
            container.stop()
            return "Container sucessfully stopped"
        except errors.NotFound:
            raise RessourceNotFound()

########Remove Container by ID######################
    def removeContainer(self, id, forceBool):
        try:
            container = self.client.containers.get(id)
            container.remove(force = forceBool)
            return "Container sucessfully removed"
        except errors.NotFound as e1:
            raise RessourceNotFound()
        except errors.APIError as e2:
            raise APIError(str(e2.explanation))
        
########Remove Container by ID######################
    def pruneContainers(self):
        try:
            res = self.client.containers.prune()
            return {"Following containers sucessfully removed":res}
        except Exception as e:
            raise e
        
########Run container by Image######################
    def runContainer(self, image, attr):
        try:
            obj = self.client.containers.run(image, **attr.dict())
            return {"Following container sucessfully created": {"Id" : obj.attrs.get('Id'), "Name": obj.attrs.get('Name')},
                    "info": "For further parameters visit: https://docker-py.readthedocs.io/en/stable/containers.html"}
        except errors.APIError as e1:
            if e1.status_code == 404:
                raise ImageNotFound()
            elif e1.status_code >= 409:
                raise APIError(str(e1))
        except TypeError as e2: 
            raise ArgumentNotFound(e2.args[0])
