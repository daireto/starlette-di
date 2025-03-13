<!-- omit in toc -->
# Starlette DI

<p align="center">
    <a href="https://pypi.org/project/starlette-di" target="_blank">
        <img src="https://img.shields.io/pypi/pyversions/starlette-di" alt="Supported Python versions">
    </a>
    <a href="https://pypi.org/project/starlette-di" target="_blank">
        <img src="https://img.shields.io/pypi/v/starlette-di" alt="Package version">
    </a>
    <a href="https://pypi.org/project/starlette" target="_blank">
        <img src="https://img.shields.io/badge/Starlette-0.38.0%2B-orange" alt="Supported Starlette versions">
    </a>
    <a href="https://github.com/daireto/starlette-di/actions" target="_blank">
        <img src="https://github.com/daireto/starlette-di/actions/workflows/publish.yml/badge.svg" alt="Publish">
    </a>
    <a href='https://coveralls.io/github/daireto/starlette-di?branch=main'>
        <img src='https://coveralls.io/repos/github/daireto/starlette-di/badge.svg?branch=main' alt='Coverage Status' />
    </a>
    <a href="/LICENSE" target="_blank">
        <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
    </a>
</p>

Starlette DI is a dependency injection library for Starlette applications.
It simplifies dependency management by allowing services to be injected using
Scoped, Transient, and Singleton lifetimes (similar to .NET Core). Also,
enables automatic injection of route parameters, and request bodies using
Pydantic models, making API development more efficient, and structured.

<!-- omit in toc -->
## Table of Contents
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Tutorial](#tutorial)
    - [1. Create a service](#1-create-a-service)
    - [2. Configure dependency injection](#2-configure-dependency-injection)
    - [3. Injecting services](#3-injecting-services)
    - [4. Inject path params](#4-inject-path-params)
    - [5. Inject request body](#5-inject-request-body)
    - [6. Use the DependencyInjectionMiddleware](#6-use-the-dependencyinjectionmiddleware)
    - [Full example](#full-example)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Features

- **Scoped, Transient, and Singleton**: Dependency injection with three service lifetimes, similar to .NET Core.
- **Service Injection**: Supports injecting services into functions, methods, and endpoint classes in Starlette.
- **Route Parameter Injection**: Automatically extracts URL parameters in controllers.
- **Request Body Injection**: Maps JSON request body data directly to Pydantic models.
- **Dependency Injection Middleware**: Provides a middleware layer to manage dependency injection throughout the request lifecycle.
- **Pydantic Compatibility**: Leverages Pydantic for data validation, and conversion.
- **Decorators for Endpoints**: Simplifies injection with `@inject`, `@inject_method`, and `@inject_class`.

## Requirements

- `Python>=3.10`
- `Starlette>=0.38.0`
- `Pydantic>=1.10.21`

## Installation

You can simply install **starlette-di** from
[PyPI](https://pypi.org/project/starlette-di/):

```bash
pip install starlette-di
```

## Tutorial

### 1. Create a service

Define a service that can be injected:

```python
from abc import ABC, abstractmethod

class IGreeter(ABC):
    @abstractmethod
    def greet(self) -> str: ...


class Greeter(IGreeter):
    def greet(self) -> str:
        return 'Hello!'
```

Alternatively, use a factory function:

```python
def greeter_factory() -> IGreeter:
    return Greeter()
```

### 2. Configure dependency injection

Use a `ServiceCollection` to register services with different lifetimes:

- **Singleton**: one instance for the application lifetime.
- **Scoped**: one instance per request.
- **Transient**: new instance created each time it's requested.

Example:

```python
from starlette_di import ServiceCollection

services = ServiceCollection()
services.add_transient(IGreeter, Greeter)
# also, services.add_scoped(IGreeter, Greeter)
# or services.add_singleton(IGreeter, Greeter)
provider = services.build_provider()
```

Using a factory function:

```python
def greeter_factory() -> IGreeter:
    return Greeter()

services.add_transient(IGreeter, greeter_factory)
```

### 3. Injecting services

Use the `@inject`, `@inject_method`, and `@inject_class` decorators to inject
the service into an endpoint function, method or class respectively.

> [!WARNING]
> Only asynchronous endpoints can be decorated.
> Trying to decorate a synchronous endpoint will raise
> a `TypeError`.

**Inject into an endpoint function**

Inject the service into an endpoint function using the `@inject` decorator:

```python
from starlette.requests import Request
from starlette.responses import JSONResponse

from starlette_di import inject

@inject
async def greet(request: Request, greeter: IGreeter):
    return JSONResponse({'message': greeter.greet()})
```

**Inject into an endpoint method**

Inject the service into an endpoint method using the `@inject_method` decorator:

```python
from starlette.requests import Request
from starlette.endpoints import HTTPEndpoint
from starlette.responses import JSONResponse

from starlette_di import inject_method

class GreetEndpoint(HTTPEndpoint):
    @inject_method
    async def get(self, request: Request, greeter: IGreeter):
        return JSONResponse({'message': greeter.greet()})
```

> [!NOTE]
> If you are implementing a custom `starlette.routing.Route` class for endpoints
> that do not expect the request object to be passed, you can set the
> `pass_request` argument to `False`:
> ```python
> from starlette.responses import JSONResponse
> from starlette.endpoints import HTTPEndpoint
>
> from starlette_di import inject_method
>
> class GreetEndpoint(HTTPEndpoint):
>     @inject_method(pass_request=False)
>     async def get(self, greeter: IGreeter):
>         return JSONResponse({'message': greeter.greet()})
> ```

**Inject into an endpoint class**

Inject the service into an endpoint class using the `@inject_class` decorator:

```python
from starlette.responses import JSONResponse
from starlette.endpoints import HTTPEndpoint

from starlette_di import inject_class

@inject_class
class GreetEndpoint(HTTPEndpoint):
    def __init__(self, request: Request, greeter: IGreeter):
        super().__init__(request)
        self.greeter = greeter

    async def get(self, request: Request):
        return JSONResponse({'message': self.greeter.greet()})
```

> [!WARNING]
> The decorated class must be a subclass of `starlette.endpoints.HTTPEndpoint`.
> Otherwise, it will raise a `TypeError`.
> To learn more about endpoints, see the
> [Starlette documentation](https://www.starlette.io/endpoints/).

### 4. Inject path params

You can inject request path parameters:

```python
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from starlette_di import inject

@inject
async def greet_person(self, request: Request, name: str):
    return JSONResponse({'message': f'Hello {name}!'})

routes = [
    Route('/greet/{name:str}', greet_person),
]
```

### 5. Inject request body

Also, you can inject the request body using
[Pydantic models](https://docs.pydantic.dev/latest/concepts/models/#basic-model-usage).
If there's only one Pydantic model parameter, the whole JSON body is injected.
Otherwise, each parameter is extracted from the JSON body using its name.

**Only one parameter**:

```python
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse

class User(BaseModel):
    name: str
    age: int

@inject
async def create_user(request: Request, user: User):
    return JSONResponse({'name': user.name, 'age': user.age})

# Example request
# {'name': 'Jane Doe', 'age': 25}
```

**Two or more parameters**

```python
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse

class User(BaseModel):
    name: str
    age: int

class Product(BaseModel):
    name: str
    price: float

@inject
async def update_product(request: Request, user: User, product: Product):
    return JSONResponse({'user_name': user.name, 'product_name': product.name})

# Example request
# {
#     'user': {'name': 'Jane Doe', 'age': 25},
#     'product': {'name': 'Computer', 'price': 225.0},
# }
```

> [!WARNING]
> The request body must be a JSON dict. Otherwise, it will raise a `ValueError`.

### 6. Use the DependencyInjectionMiddleware

Use the `DependencyInjectionMiddleware` to handle dependency injection.

This middleware sets up the request scope for dependency injection by creating
a scoped service provider, and adding it to the request scope.

Pass the service provider built in [here](#2-create-a-service-collection) to
the `service_provider` argument of the middleware:

```python
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Route
from starlette_di import DependencyInjectionMiddleware

app = Starlette(
    routes=[Route('/greet', GreetEndpoint)],
    middleware=[
        Middleware(DependencyInjectionMiddleware, service_provider=provider),
    ]
)
```

> [!NOTE]
> You can access the scoped service provider from the request scope using the
> `SERVICE_PROVIDER_ARG_NAME` constant:
> ```python
> from starlette_di.definitions import SERVICE_PROVIDER_ARG_NAME
>
> request.scope[SERVICE_PROVIDER_ARG_NAME]
> # <starlette_di.service_provider.ScopedServiceProvider object at 0x00000...>
> ```

### Full example

Find the full tutorial example [here](example.py).

## Contributing

See the [contribution guidelines](CONTRIBUTING.md).

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE)
file for details.

## Support

If you find this project useful, give it a ⭐ on GitHub!
