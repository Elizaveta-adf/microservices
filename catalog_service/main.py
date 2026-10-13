
import os
import time

import requests
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field


app = FastAPI(
    title="Catalog Service",
    description="REST API каталога товаров с пагинацией",
    version="1.0.0",
    openapi_version="3.1.0",
    docs_url="/docs",
    root_path="/catalog"
)

INSTANCE_NAME = os.getenv("INSTANCE_NAME", "catalog")
PORT = int(os.getenv("PORT", "8000"))
CONSUL_URL = os.getenv("CONSUL_URL", "http://consul:8500")

# In-memory хранилище товаров
products = {}
next_id = 1


class Product(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        description="Название товара",
        examples=["Laptop"]
    )
    price: float = Field(
        ...,
        ge=0,
        description="Цена товара",
        examples=[1500.0]
    )


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


# Старый endpoint из ЛР2
@app.get("/products", include_in_schema=False)
def get_products():
    return {
        "instance_id": INSTANCE_NAME,
        "products": list(products.values())
    }


# REST API ЛР3: список товаров с пагинацией
@app.get(
    "/api/catalog/products",
    tags=["Catalog"],
    summary="Получение списка товаров с пагинацией",
    description="Возвращает товары с учётом номера страницы и размера страницы"
)
def get_products_paginated(
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(10, ge=1, le=100, description="Количество товаров на странице")
):
    all_products = list(products.values())
    total = len(all_products)

    start = (page - 1) * size
    end = start + size

    return {
        "instance_id": INSTANCE_NAME,
        "page": page,
        "size": size,
        "total": total,
        "products": all_products[start:end]
    }


# REST API ЛР3: получение товара по ID
@app.get(
    "/api/catalog/products/{product_id}",
    tags=["Catalog"],
    summary="Получение товара по идентификатору",
    description="Возвращает товар по его ID или ошибку 404"
)
def get_product_by_id(product_id: int):
    if product_id not in products:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    return {
        "instance_id": INSTANCE_NAME,
        "product": products[product_id]
    }


# CRUD из ЛР2
@app.post(
    "/products",
    tags=["Catalog"],
    summary="Создание товара"
)
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


@app.put(
    "/products/{product_id}",
    tags=["Catalog"],
    summary="Изменение товара"
)
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


@app.delete(
    "/products/{product_id}",
    tags=["Catalog"],
    summary="Удаление товара"
)
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
