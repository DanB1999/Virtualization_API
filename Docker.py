import docker
from docker import errors
from pydantic import BaseModel, Extra
from exceptions import APIError, ArgumentNotFound, ImageNotFound, ResourceNotFound, ResourceAlreadyRunning, ResourceNotRunning, ResourceRunning

class ContainerObj(BaseModel):
    name: str | None = None
    ports: object | None = None
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
        extra = Extra.allow

class Docker():
    def __init__(self):
        self.client = docker.from_env()

    def list_containers(self):
        list = self.client.containers.list(all=True)
        jsonList = []
        for i in range(0 , list.__len__()):
            jsonList.append({"Id" : list[i].short_id,
                            "Name": list[i].attrs['Name'],
                            "Image": list[i].attrs['Config']['Image'],
                            "Status": list[i].attrs['State']['Status']})
        return jsonList
    
    def list_images(self):
        list = self.client.images.list(all=True)
        jsonList = []
        for i in range(0 , list.__len__()):
            jsonList.append({"Name": list[i].attrs["RepoTags"][0],
                            "Id" : list[i].attrs["Id"],
                            "Created": list[i].attrs["Created"],
                            "Container": list[i].attrs["ContainerConfig"]["Hostname"]
                            })
        return jsonList

    def get_container_info(self, id):
        container = self.client.containers.get(id)
        return container.attrs

    def start_container(self, id):
        container = self.client.containers.get(id)
        try:
            state = container.attrs["State"]["Status"]
            if state != "running":
                container.start()
                return "Container sucessfully started"
            else:
                raise ResourceAlreadyRunning()
        except errors.APIError as e:
            raise APIError(str(e.explanation))

    def stop_container(self, id):
        container = self.client.containers.get(id)
        try:
            state = container.attrs["State"]["Status"]
            if state == "running":
                container.stop()
                return "Container sucessfully stopped"
            else: 
                raise ResourceNotRunning()
        except errors.APIError as e:
            raise APIError(str(e.explanation))
            
    def restart_container(self, id):
        container = self.client.containers.get(id)
        try:
            state = container.attrs["State"]["Status"]
            if state == "running":
                container.restart()
                return "Container sucessfully restarted"
            else: 
                raise ResourceNotRunning()
        except errors.APIError as e:
            raise APIError(str(e.explanation))

    def remove_container(self, id):
        container = self.client.containers.get(id)
        try:
            state = container.attrs["State"]["Status"]
            if state != "running":
                container.remove()
                return "Container sucessfully removed"
            else:
                raise ResourceRunning()
        except errors.APIError as e:
            raise APIError(str(e.explanation))
        
    def prune_containers(self):
        try:
            res = self.client.containers.prune()
            return {"Following containers sucessfully removed":res}
        except errors.APIError as e:
            raise APIError(str(e.explanation))
        
    def run_container(self, image, attr):
        try:
            obj = self.client.containers.run(image, **attr.dict())
            return {"Following container sucessfully created": {"Id" : obj.attrs.get('Id'), "Name": obj.attrs.get('Name')},
                    "info": "For further parameters visit: https://docker-py.readthedocs.io/en/stable/containers.html"}
        except errors.APIError as e1:
            if e1.status_code == 404:
                raise ImageNotFound()
            elif e1.status_code >= 409:
                raise APIError(str(e1.explanation))
        except TypeError as e2: 
            raise ArgumentNotFound(e2.args[0])
    
    def get_container(self, id):
        try: 
            return self.client.containers.get(id)
        except errors.NotFound:
            raise ResourceNotFound()
