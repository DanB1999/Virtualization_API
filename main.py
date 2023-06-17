from datetime import  timedelta
from typing import List, Annotated
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from Docker import Docker, ContainerObj
from VM import VM, DomainObj
from Security import User, Token, fake_users_db, authenticate_user, create_access_token, get_current_active_user, ACCESS_TOKEN_EXPIRE_MINUTES
from fastapi.middleware.cors import CORSMiddleware
from exceptions import APIError, ArgumentNotFound, ResourceAlreadyRunning, ResourceNotFound, ResourceNotRunning, ImageNotFound, ResourceRunning

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
        return docker.list_containers()
    elif type in "docker images":
        return docker.list_images()
    elif type in "kvm-qemu vms":
        return vm.list_vms()
    elif type in "kvm-qemu volumes":
        return vm.list_storage_vol()

@app.get("/resources/{id}")
async def get_info(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["basic"])],    
    id: str,
    filter: Annotated[bool, Query(description="List Snapshots of VM")] = False
):
    if get_resource(id) == "docker":
        return docker.get_container_info(id)
    elif get_resource(id) == "kvm-qemu":
        if filter:
            return vm.list_snapshots(id)
        else:
            return vm.get_vm_info(id)

@app.put("/resources/{id}/start")
async def start_resource(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],    
    id: str,
    revertSnapshot = None
):
    try:
        if get_resource(id) == "docker":
            return docker.start_container(id)
        elif get_resource(id) == "kvm-qemu":
            return vm.start_vm(id, revertSnapshot)
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)
    except ResourceAlreadyRunning as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)

@app.put("/resources/{id}/stop")
async def stop_resource(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],   
    id: str
):
    try:
        if get_resource(id) == "docker":
            return docker.stop_container(id)
        elif get_resource(id) == "kvm-qemu":
            return vm.stop_vm(id)
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)
    except ResourceNotRunning as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)

@app.put("/resources/{id}/restart")
async def restart_resource(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],   
    id: str
):
    try:
        if get_resource(id) == "docker":
            return docker.restart_container(id)
        elif get_resource(id) == "kvm-qemu":
            return vm.reboot_vm(id)
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)
    except ResourceNotRunning as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)
    
@app.delete("/resources/{id}/delete")
async def remove_resource(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],
    id: str,
    deleteStorageVol: Annotated[bool, Query(description="Delete asociated storage volume")] = True,
    deleteSnapshot: Annotated[str, Query(description="Delete snapshot instead of vm")] = None,
):
    try:
        if get_resource(id) == "docker":
            return docker.remove_container(id)
        elif get_resource(id) == "kvm-qemu":
            if deleteSnapshot:
                return vm.deleteSnapshot(id, deleteSnapshot)
            if len(vm.get_vm_snapshots(id)) == 0:
                if deleteStorageVol:
                    vm.delete_storage_vol(id)
                return vm.delete_vm(id)
            else: 
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete inactive domain with " + str(len(vm.getDomainSnapshots(id)))+ " snapshots")
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)
    except ResourceRunning as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)

@app.delete("/resources/docker/prune")
async def prune_containers(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])]
):
    try:
        return docker.prune_containers()
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)

@app.put("/resources/{id}/snapshot")
async def take_snapshot(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],   
    id: str,
    snapshot_name: str
):
    get_resource()
    try:
        return vm.create_snapshot(id, snapshot_name)
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)

@app.put("/resources/{id}/shutdown")
async def shutdown_vm(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],
    id: str,
    save: Annotated[bool, Query(description="Save VM for later use, priority over force command")] = False, 
    force: bool = False, 
):
    get_resource()
    try:
        return vm.shutdown_vm(id, save, force)
    except APIError as e1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e1.message)
    except ResourceNotRunning as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)

@app.post("/resources/docker/run")
async def run_container(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],
    obj: ContainerObj, 
    image: str
):
    try:
        return docker.run_container(image, obj)
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
        res = vm.run_vm_xml(body)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Content type {content_type} not supported')
    return res
    
@app.post("/resources/kvm-qemu/run/json")
async def run_vm_json(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["advanced"])],
    obj: DomainObj
):
    try:
        vm.create_storage_vol(obj.dict().get("name"))
        return vm.run_vm_json(obj)
    except APIError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

def get_resource(id):
    res = None
    try:
        if vm.get_vm(id):
            res = "kvm-qemu"
    except ResourceNotFound:
        try:
            if docker.get_container(id):
                res = "docker"
        except ResourceNotFound:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found -> Please check the identifier and try it again")
    return res