import os
import time

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


app = FastAPI(title="Catalog Service")

INSTANCE_NAME = os.getenv("INSTANCE_NAME", "catalog")
PORT = int(os.getenv("PORT", "8000"))
CONSUL_URL = os.getenv("CONSUL_URL", "http://consul:8500")

products = {}
next_id = 1


class Product(BaseModel):
    name: str
    price: float


def register_in_consul():
    payload = {
        "Name": "catalog",
        "ID": INSTANCE_NAME,
        "Address": INSTANCE_NAME,
        "Port": PORT
    }

    for attempt in range(10):
        try:
            response = requests.put(
                f"{CONSUL_URL}/v1/agent/service/register",
                json=payload,
                timeout=3
            )
            response.raise_for_status()

            print(f"Registered {INSTANCE_NAME} in Consul")
            return

        except requests.RequestException as error:
            print(f"Consul is not ready: {error}")
            time.sleep(2)

    print("Could not register in Consul")


def deregister_from_consul():
    try:
        requests.put(
            f"{CONSUL_URL}/v1/agent/service/deregister/{INSTANCE_NAME}",
            timeout=3
        )

        print(f"Deregistered {INSTANCE_NAME} from Consul")

    except requests.RequestException as error:
        print(f"Could not deregister from Consul: {error}")


@app.on_event("startup")
def startup_event():
    register_in_consul()


@app.on_event("shutdown")
def shutdown_event():
    deregister_from_consul()


@app.get("/products")
def get_products():
    return {
        "instance_id": INSTANCE_NAME,
        "products": list(products.values())
    }


@app.post("/products")
def create_product(product: Product):
    global next_id

    product_data = {
        "id": next_id,
        "name": product.name,
        "price": product.price
    }

    products[next_id] = product_data
    next_id += 1

    return {
        "instance_id": INSTANCE_NAME,
        "product": product_data
    }


@app.put("/products/{product_id}")
def update_product(product_id: int, product: Product):
    if product_id not in products:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    products[product_id] = {
        "id": product_id,
        "name": product.name,
        "price": product.price
    }

    return {
        "instance_id": INSTANCE_NAME,
        "product": products[product_id]
    }


@app.delete("/products/{product_id}")
def delete_product(product_id: int):
    if product_id not in products:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    deleted_product = products.pop(product_id)

    return {
        "instance_id": INSTANCE_NAME,
        "deleted": deleted_product
    }