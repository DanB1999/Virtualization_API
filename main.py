from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Union,Annotated
import time
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from Docker import Docker
from VM import VM

# to get a string like this run:
# openssl rand -hex 32
SECRET_KEY = "b18cddaef06d377b97f01a3de062a2e1ec2cca8cf9a37b543786b9227155ae64"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30



fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
        "disabled": False,
    }
}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

#Docker und VM-Klassen instanziieren
docker = Docker()

vm = VM()


app = FastAPI()


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


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
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me/", response_model=User)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    return current_user


@app.get("/users/me/items/")
async def read_own_items(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    return [{"item_id": "Foo", "owner": current_user.username}]





class ContainerObj(BaseModel):
    name: Union[str, None] = None #Wenn kein key im request vorhanden setzt der den Wert auf NULL
    ports: int = "1234" 
    volumes = ["host-vol:mount-vol"]
    detach: bool = True

class DomainObj(BaseModel):
    name: Union[str, None] = None
    memory: int = 500000
    vcpu: int = 1
    source_file: str

#Intercept the request and check if daemons are running
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    time.sleep(5)
    if vm.checkConnection() == 0:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    else:
         HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Qemu Deamon not available")


@app.get("/containers/list/{showAll}")
def get_list(showAll: bool = False):
    list = docker.getContainerList(showAll)
    return list

@app.get("/containers/{id}/stats")
def get_Info(id: str):
    info  = docker.getContainerStats(id)
    return info

@app.put("/containers/{id}/start")
def start_Container(id: str):
    try:
        res = docker.startContainer(id)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    return res

@app.put("/containers/{id}/stop")
def stop_Container(id: str):
    try:
        res = docker.stopContainer(id)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    return res

@app.delete("/containers/{id}/remove")
def remove_Container(id: str):
    try:
        res = docker.removeContainer(id)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
    return res

@app.delete("/containers/prune")
def  prune_Containers():
    return docker.pruneContainers()

#"bfirsh/reticulate-splines"
@app.put("/containers/run/")
def run_Container(obj: ContainerObj, image: str | None = None):
    return docker.runContainer(image, obj)

###KVM-Qemu
@app.get("/kvm/list")
def get_VM_list():
    return vm.listDomains()

@app.get("/kvm/{id}/stats")
def get_VM_Info(id: str):
    try:
        res = vm.getDomainStats(id)
    except AttributeError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
    return res

@app.put("/kvm/{id}/start")
def start_vm(id: str):
    try:
        res = vm.startVM(id)
    except AttributeError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_226_IM_USED, detail="VM already running")
    if res == 0:      
        raise HTTPException(status_code=status.HTTP_200_OK, detail="VM erfolgreich gestartet")

@app.put("/kvm/{id}/stop")
def stop_vm(id: str):
    try:
        res = vm.stopVM(id)
    except AttributeError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
    if res == 0:      
        raise HTTPException(status_code=status.HTTP_200_OK, detail="VM erfolgreich gestoppt")


@app.put("/kvm/{id}/shutdown")
async def shutdown_vm(id: str):
    try:
        res = vm.shutdownVM(id)
    except AttributeError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
    if res == 0:      
        raise HTTPException(status_code=status.HTTP_200_OK, detail="VM erfolgreich heruntergefahren")


@app.put("/kvm/run")
def run_vm(obj: DomainObj):
    return vm.runVM(obj)
