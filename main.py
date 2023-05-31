from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Union,Annotated
import time
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, Security, UploadFile, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from Docker import Docker, ContainerObj
from VM import VM, DomainObj
from Security import Token, pwd_context, authenticate_user, fake_users_db, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, User, get_current_active_user
from fastapi.middleware.cors import CORSMiddleware
from exceptions import APIError, ArgumentNotFound, DomainAlreadyRunning, DomainNotRunning, ImageNotFound, RessourceNotFound
import urllib.parse

#Docker und VM-Klassen instanziieren
docker = Docker()

vm = VM()

app = FastAPI()

###Middleware zum Hantieren mit CORS-Anfragen
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
    print(form_data.password)
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
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    return current_user




#Intercept the request and check if daemons are running
#@app.middleware("http")
#async def add_process_time_header(request: Request, call_next):
#    start_time = time.time()
#    if vm.libvirtConnect() == 0:
#        response = await call_next(request)
#        process_time = time.time() - start_time
#        response.headers["X-Process-Time"] = str(process_time)
#        return response
#    else:
#         HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Qemu Deamon not available")


@app.get("/containers")
async def get_list(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["user"])],    
    showAll: bool = False, 
    q: Annotated[str | None, Query(title = "Query string", min_length=3, max_length=50, regex="^fixedquery$")] = None
):
    list = docker.getContainerList(showAll)
    return list

@app.get("/containers/{id}")
async def get_Info(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["user"])],    
    id: str
):
    try:
        return docker.getContainerStats(id)
    except RessourceNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)

@app.put("/containers/{id}/start")
async def start_Container(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["admin"])],    
    id: str
):
    try:
        return docker.startContainer(id)
    except RessourceNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)

@app.put("/containers/{id}/stop")
async def stop_Container(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["admin"])],   
    id: str
):
    try:
        return docker.stopContainer(id)
    except RessourceNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    
@app.delete("/containers/{id}/remove")
async def remove_Container(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["admin"])],
    id: str,
    force: bool = False 
):
    try:
        return docker.removeContainer(id, force)
    except RessourceNotFound as e1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e1.message)
    except APIError as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)

@app.delete("/containers/prune")
async def prune_Containers(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["admin"])]
):
    try:
        return docker.pruneContainers()
    except Exception as e:
        raise e

#"bfirsh/reticulate-splines"
@app.post("/containers/run")
async def run_Container(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["admin"])],
    obj: ContainerObj, 
    image: str
):
    try:
        decoded_param = urllib.parse.unquote(image)
        return docker.runContainer(decoded_param, obj)
    except ImageNotFound as e1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e1.message)
    except APIError as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)
    except ArgumentNotFound as e3:
        raise HTTPException(status_code=status.HTTP_406_NOT_ACCEPTABLE, detail=e3.message)

 

###KVM-Qemu
@app.get("/vms")
async def get_VM_list(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["user"])]
):
    return vm.listDomains()

@app.get("/vms/{id}")
async def get_VM_Info(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["user"])],
    id: str
):
    try:
        res = vm.getDomainStats(id)
    except RessourceNotFound as e1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e1.message)
    return res

#pausierte VM kann nicht wieder gestartet werden -> "domain is already running"
@app.put("/vms/{id}/start")
async def start_vm(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["admin"])],
    id: str
):
    try:
        return vm.startVM(id)
    except RessourceNotFound as e1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e1.message)
    except DomainAlreadyRunning as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)

@app.put("/vms/{id}/stop")
async def stop_vm(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["admin"])],
    id: str
):
    try:
        return vm.stopVM(id)
    except RessourceNotFound as e1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e1.message)
    except DomainNotRunning as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)

@app.put("/vms/{id}/shutdown")
async def shutdown_vm(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["admin"])],
    id: str,
    save: bool = False, 
):
    try:
        return vm.shutdownVM(id,save)
    except RessourceNotFound as e1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e1.message)
    except DomainNotRunning as e2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e2.message)

@app.delete("/vms/{id}/delete")
async def delete_vm(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["admin"])],    
    id: str
):
    try:
        return vm.deleteVM(id)
    except RessourceNotFound as e1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e1.message)
    except APIError as e2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e2.message)

class Item(BaseModel):
    name: str
    tags: List[str]

#    class Config:
#        schema_extra: 

@app.post(
    "/vms/run/xml",
    openapi_extra={
        "requestBody": {
            "content": {"application/xml": {"schema": Item.schema()}},
            "required": True,
        },
    })

async def run_vm_xml(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["admin"])],    
    request: Request
):
    content_type = request.headers['Content-Type']
    if content_type == "application/xml":
        body = await request.body()

        res = vm.runVM_xml(body)#Response(content=body, media_type='application/xml')
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Content type {content_type} not supported')
    return res
    
@app.post("/vms/run/json")
async def run_vm_json(
    current_user: Annotated[User, Security(get_current_active_user, scopes=["admin"])],
    obj: DomainObj
):
    try:
        return vm.runVM_json(obj)#Response(content=body, media_type='application/xml')
    except APIError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@app.post("/files/")
async def create_file(
    file: Annotated[bytes,File()],
    fileb:Annotated[UploadFile, File()]
):
    return {
        "file_size": len(file),
        "fileb_content_type": fileb.content_type
    }
