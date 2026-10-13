
import os

import httpx
import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
import asyncio


ORDERS_URL = os.getenv(
    "ORDERS_URL",
    "http://orders:8000"
)

CATALOG_URL = os.getenv(
    "CATALOG_URL",
    "http://catalog-1:8000"
)


@strawberry.type(description="Информация о товаре из Catalog")
class Product:
    id: int
    name: str
    price: float



@strawberry.type(description="Позиция заказа")
class OrderItem:
    product_id: int
    quantity: int

    @strawberry.field(description="Данные товара из Catalog REST API")
    async def product(self, info: strawberry.Info) -> Product | None:
        cache = info.context["product_cache"]

        async def load_product(product_id: int):
            client = info.context["client"]

            print(
                f"REST request to Catalog: product_id={product_id}",
                flush=True
            )

            response = await client.get(
                f"{CATALOG_URL}/api/catalog/products/{product_id}"
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()["product"]

            return Product(**data)

        if self.product_id not in cache:
            cache[self.product_id] = asyncio.create_task(
                load_product(self.product_id)
            )
        else:
            print(
                f"Cache HIT: product_id={self.product_id}",
                flush=True
            )

        return await cache[self.product_id]


@strawberry.type(description="Заказ пользователя")
class Order:
    id: int
    user_id: int
    items: list[OrderItem]


@strawberry.type
class Query:

    @strawberry.field(description="Заказы пользователя с товарами")
    async def orders(
        self,
        info: strawberry.Info,
        user_id: int
    ) -> list[Order]:

        client = info.context["client"]

        response = await client.get(
            f"{ORDERS_URL}/orders/user/{user_id}"
        )
        response.raise_for_status()

        return [
            Order(
                id=order["id"],
                user_id=order["user_id"],
                items=[
                    OrderItem(**item)
                    for item in order["items"]
                ]
            )
            for order in response.json()
        ]


schema = strawberry.Schema(query=Query)


async def get_context():
    async with httpx.AsyncClient(timeout=10.0) as client:
        yield {
            "client": client,
            "product_cache": {}
        }


app = FastAPI(
    title="GraphQL Gateway",
    description="Агрегация заказов и товаров через GraphQL",
    version="1.0.0"
)

graphql_app = GraphQLRouter(
    schema,
    context_getter=get_context,
    graphql_ide="graphiql"
)

app.include_router(graphql_app, prefix="/graphql")
