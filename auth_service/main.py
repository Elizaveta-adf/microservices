
import os
import time

import jwt
import requests
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext


app = FastAPI(
    title="Auth Service",
    description="REST API для регистрации и аутентификации пользователей",
    version="1.0.0",
    openapi_version="3.1.0",
    docs_url="/docs",
    root_path="/auth"
)

# In-memory хранилище пользователей
users = {}

# Настройки JWT
SECRET_KEY = os.getenv("JWT_SECRET", "secret-key")
ALGORITHM = "HS256"

# Настройки сервиса
SERVICE_NAME = "auth"
SERVICE_ID = os.getenv("INSTANCE_NAME", "auth")
SERVICE_PORT = int(os.getenv("PORT", "8000"))
CONSUL_URL = os.getenv("CONSUL_URL", "http://consul:8500")

# Хэширование паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserData(BaseModel):
    email: EmailStr
    password: str


def register_in_consul():
    payload = {
        "Name": SERVICE_NAME,
        "ID": SERVICE_ID,
        "Address": SERVICE_ID,
        "Port": SERVICE_PORT
    }

    for attempt in range(10):
        try:
            response = requests.put(
                f"{CONSUL_URL}/v1/agent/service/register",
                json=payload,
                timeout=3
            )
            response.raise_for_status()
            print(f"Registered {SERVICE_ID} in Consul")
            return
        except requests.RequestException as error:
            print(f"Consul is not ready: {error}")
            time.sleep(2)

    print("Could not register in Consul")


def deregister_from_consul():
    try:
        requests.put(
            f"{CONSUL_URL}/v1/agent/service/deregister/{SERVICE_ID}",
            timeout=3
        )
        print(f"Deregistered {SERVICE_ID} from Consul")
    except requests.RequestException as error:
        print(f"Could not deregister from Consul: {error}")


@app.on_event("startup")
def startup_event():
    register_in_consul()


@app.on_event("shutdown")
def shutdown_event():
    deregister_from_consul()


@app.post(
    "/api/auth/register",
    tags=["Auth"],
    summary="Регистрация пользователя"
)
@app.post("/register", include_in_schema=False)
def register(user: UserData):
    if user.email in users:
        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )

    hashed_password = pwd_context.hash(user.password)

    users[user.email] = {
        "email": user.email,
        "password": hashed_password
    }

    return {
        "message": "User registered successfully",
        "email": user.email
    }


@app.post(
    "/api/auth/login",
    tags=["Auth"],
    summary="Аутентификация пользователя"
)
@app.post("/login", include_in_schema=False)
def login(user: UserData):
    saved_user = users.get(user.email)

    if not saved_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not pwd_context.verify(
        user.password,
        saved_user["password"]
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    token = jwt.encode(
        {"sub": user.email},
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@app.get(
    "/me",
    tags=["Auth"],
    summary="Получение данных текущего пользователя"
)
def me(authorization: str = Header(None)):
    if authorization is None:
        raise HTTPException(
            status_code=401,
            detail="Authorization header is required"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header"
        )

    token = authorization.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        email = payload.get("sub")

        if email is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

        return {
            "email": email
        }

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )
