from abc import ABC, abstractmethod

from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.endpoints import HTTPEndpoint
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from starlette_di import (
    DependencyInjectionMiddleware,
    ServiceCollection,
    inject,
    inject_class,
    inject_method,
)


# Models
class User(BaseModel):
    name: str
    age: int


class Product(BaseModel):
    name: str
    price: float


# Services
class IGreeter(ABC):
    @abstractmethod
    def greet(self) -> str: ...


class Greeter(IGreeter):
    def greet(self) -> str:
        return 'Hello!'


class ICounter(ABC):
    @abstractmethod
    def count(self) -> int: ...


class Counter(ICounter):
    def __init__(self, greeter: IGreeter):
        self._count = 0
        self._greeter = greeter

    def count(self) -> int:
        self._count += 1
        return self._count


class IServicesTester(ABC):
    @abstractmethod
    def test(self) -> None: ...


class ServicesTester(IServicesTester):
    def __init__(self, greeter: IGreeter, counter: ICounter):
        self._greeter = greeter
        self._counter = counter

    def test(self):
        return {
            'greeter_id': id(self._greeter),
            'counter_id': id(self._counter),
        }


# Factories
def services_tester_factory(greeter: IGreeter, counter: ICounter):
    return ServicesTester(greeter, counter)


# Service collection
services = ServiceCollection()
services.add_transient(IGreeter, Greeter)
services.add_singleton(ICounter, Counter)
services.add_scoped(IServicesTester, ServicesTester)
provider = services.build_provider()


# Endpoints
@inject
async def greet(request: Request, greeter: IGreeter):
    return JSONResponse({'message': greeter.greet()})


@inject_class
class CounterEndpoint(HTTPEndpoint):
    async def get(self, request: Request, counter: ICounter):
        return JSONResponse({'value': counter.count()})


class ServicesTesterEndpoint(HTTPEndpoint):
    @inject_method
    async def get(self, request: Request, services_tester: IServicesTester):
        return JSONResponse(services_tester.test())


@inject
async def create_user(request: Request, user: User):
    return JSONResponse({'name': user.name, 'age': user.age})


@inject
async def update_product(request: Request, user: User, product: Product):
    return JSONResponse({'user_name': user.name, 'product_name': product.name})


# Application
app = Starlette(
    routes=[
        Route('/greet', greet),
        Route('/counter', CounterEndpoint),
        Route('/test-services', ServicesTesterEndpoint),
        Route('/users', create_user, methods=['POST']),
        Route('/products', update_product, methods=['POST']),
    ],
    middleware=[
        Middleware(DependencyInjectionMiddleware, service_provider=provider),
    ],
)

# Test client
client = TestClient(app)
response = client.get('/greet')
assert response.json() == {'message': 'Hello!'}

response = client.get('/counter')
assert response.json() == {'value': 1}

response = client.get('/counter')
assert response.json() == {'value': 2}

response = client.get('/test-services')
service_ids1 = response.json()

response = client.get('/test-services')
service_ids2 = response.json()
assert service_ids1['greeter_id'] != service_ids2['greeter_id']
assert service_ids1['counter_id'] == service_ids2['counter_id']

data = {'name': 'Jane Doe', 'age': 25}
response = client.post('/users', json=data)
assert response.json() == {'name': 'Jane Doe', 'age': 25}

data = {
    'user': {'name': 'Jane Doe', 'age': 25},
    'product': {'name': 'Computer', 'price': 225.0},
}
response = client.post('/products', json=data)
assert response.json() == {'user_name': 'Jane Doe', 'product_name': 'Computer'}

print('All tests passed!')
