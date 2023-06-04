from datetime import  timedelta
from typing import List, Annotated
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from Docker import Docker, ContainerObj
from VM import VM, DomainObj
from Security import User, Token, fake_users_db, authenticate_user, create_access_token, get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
from fastapi.middleware.cors import CORSMiddleware
from exceptions import APIError, ArgumentNotFound, ResourceAlreadyRunning, ResourceNotRunning, ImageNotFound, ResourceRunning

docker = Docker()
vm = VM()

app = FastAPI()

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):  
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": form_data.scopes},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me/", response_model=User)
async def read_users_me(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["basic"])],    
):
    return current_user

@app.get("/resources")
async def get_list(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["basic"])],    
    type: Annotated[str, Query(description="docker container, docker images, kvm-qemu vms, kvm-qemu volumes")]
):
    if type in "docker container":
        return docker.getContainerList()
    elif type in "docker images":
        return docker.getImageList()
    elif type in "kvm-qemu vms":
        return vm.listDomains()
    elif type in "kvm-qemu volumes":
        return vm.listStorageVolumes()

@app.get("/resources/{id}")
async def get_Info(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["basic"])],    
    id: str,
    filter: Annotated[bool, Query(description="List Snapshots of VM")] = False
):
    if getResourceById(id) == "docker":
        return docker.getContainerStats(id)
    elif getResourceById(id) == "kvm-qemu":
        if filter:
            return vm.listSnapshots(id)
        else:
            return vm.getDomainStats(id)

@app.put("/resources/{id}/start")
async def start_Ressource(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],    
    id: str,
    revertSnapshot = None
):
    try:
        if getResourceById(id) == "docker":
            return docker.startContainer(id)
        elif getResourceById(id) == "kvm-qemu":
            return vm.startVM(id, revertSnapshot)
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)
    except ResourceAlreadyRunning as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)

@app.put("/resources/{id}/stop")
async def stop_Ressource(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],   
    id: str
):
    try:
        if getResourceById(id) == "docker":
            return docker.stopContainer(id)
        elif getResourceById(id) == "kvm-qemu":
            return vm.stopVM(id)
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)
    except ResourceNotRunning as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)
    
@app.delete("/resources/{id}/delete")
async def remove_Ressource(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],
    id: str,
    deleteStorageVol: Annotated[bool, Query(description="Delete asociated storage volume")] = True,
    deleteSnapshot: Annotated[str, Query(description="Delete snapshot instead of vm")] = None,
):
    try:
        if getResourceById(id) == "docker":
            return docker.removeContainer(id)
        elif getResourceById(id) == "kvm-qemu":
            if deleteSnapshot:
                return vm.deleteSnapshot(id, deleteSnapshot)
            if len(vm.getDomainSnapshots(id)) == 0:
                if deleteStorageVol:
                    vm.deleteStorageVol(id)
                return vm.deleteVM(id)
            else: 
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete inactive domain with " + str(len(vm.getDomainSnapshots(id)))+ " snapshots")
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)
    except ResourceRunning as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)

@app.delete("/resources/docker/prune")
async def prune_Containers(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])]
):
    try:
        return docker.pruneContainers()
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)

@app.put("/resources/{id}/snapshot")
async def take_snapshot(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],   
    id: str,
    snapshot_name: str
):
    getResourceById()
    try:
        return vm.createSnapshot(id, snapshot_name)
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)

@app.put("/resources/{id}/shutdown")
async def shutdown_vm(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],
    id: str,
    save: Annotated[bool, Query(description="Save VM for later use, priority over force command")] = False, 
    force: bool = False, 
):
    getResourceById()
    try:
        return vm.shutdownVM(id, save, force)
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)
    except ResourceNotRunning as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)

@app.post("/resources/docker/run")
async def run_Container(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],
    obj: ContainerObj, 
    image: str
):
    try:
        return docker.runContainer(image, obj)
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)
    except ImageNotFound as e2:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e2.message)
    except ArgumentNotFound as e3:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=e3.message)

class Item(BaseModel):
    name: str
    tags: List[str]

@app.post(
    "/resources/kvm-qemu/run/xml",
    openapi_extra={
        "requestBody": {
            "content": {"application/xml": {"schema": Item.schema()}},
            "required": True,
        }})
async def run_vm_xml(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],    
    request: Request
):
    content_type = request.headers['Content-Type']
    if content_type == "application/xml":
        body = await request.body()
        res = vm.runVM_xml(body)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Content type {content_type} not supported')
    return res
    
@app.post("/resources/kvm-qemu/run/json")
async def run_vm_json(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],
    obj: DomainObj
):
    try:
        vm.createStorageVol(obj.dict().get("name"))
        return vm.runVM_json(obj)
    except APIError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

def getResourceById(id):
    res = None
    if vm.getDomainByUUID(id):
        res = "kvm-qemu"
    elif docker.getContainerbyID(id):
        res = "docker"
    
    if res == None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found -> Please check the identifier and try it again")
    return res
