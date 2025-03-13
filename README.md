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

A dependency injection library for Starlette.

<!-- omit in toc -->
## Table of Contents
- [Requirements](#requirements)
- [Installation](#installation)
- [Tutorial](#tutorial)
    - [1. Create a service](#1-create-a-service)
    - [2. Create a service collection](#2-create-a-service-collection)
    - [3. Inject the service](#3-inject-the-service)
        - [3.1. Inject into an endpoint function](#31-inject-into-an-endpoint-function)
        - [3.2. Inject into an endpoint method](#32-inject-into-an-endpoint-method)
        - [3.3. Inject into an endpoint class](#33-inject-into-an-endpoint-class)
    - [4. Use the DependencyInjectionMiddleware](#4-use-the-dependencyinjectionmiddleware)
    - [5. Make a request to the endpoint](#5-make-a-request-to-the-endpoint)
    - [Full example](#full-example)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Requirements

- `Python>=3.10`
- `Starlette>=0.38.0`

## Installation

You can simply install **starlette-di** from
[PyPI](https://pypi.org/project/starlette-di/):

```bash
pip install starlette-di
```

## Tutorial

### 1. Create a service

Create a service to be injected, for example:

```python
from abc import ABC, abstractmethod


class IGreeter(ABC):
    @abstractmethod
    def greet(self) -> str: ...


class Greeter(IGreeter):
    def greet(self) -> str:
        return 'Hello!'
```

> [!NOTE]
> You can also inject a factory function:
> ```python
> def greeter_factory() -> IGreeter:
>     return Greeter()
> ```

### 2. Create a service collection

Create a service collection, add the service and build a service provider.

The service provider is used to resolve dependencies.

There are three types of services: singleton, scoped and transient:

- **Singleton**: one instance for the application lifetime.
- **Scoped**: one instance per request.
- **Transient**: new instance created each time it's requested.

For example:

```python
from starlette_di import ServiceCollection

services = ServiceCollection()
services.add_transient(IGreeter, Greeter)
# also, services.add_scoped(IGreeter, Greeter)
# or services.add_singleton(IGreeter, Greeter)
provider = services.build_provider()
```

This is the same for factory functions:

```python
def greeter_factory() -> IGreeter:
    return Greeter()

services.add_transient(IGreeter, greeter_factory)
```

### 3. Inject the service

You can inject the service into an endpoint function, method or class.

#### 3.1. Inject into an endpoint function

Inject the service into an endpoint function using the `@inject` decorator:

```python
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette_di import inject

@inject
async def greet(request: Request, greeter: IGreeter):
    return JSONResponse({'message': greeter.greet()})
```

#### 3.2. Inject into an endpoint method

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
> from starlette_di import inject_method
>
> class GreetEndpoint(HTTPEndpoint):
>     @inject_method(pass_request=False)
>     async def get(self, greeter: IGreeter):
>         return JSONResponse({'message': greeter.greet()})
> ```

#### 3.3. Inject into an endpoint class

Inject the service into an endpoint class using the `@inject_class` decorator:

```python
from starlette.responses import JSONResponse
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

### 4. Use the DependencyInjectionMiddleware

Use the `DependencyInjectionMiddleware` to handle dependency injection.

This middleware sets up the request scope for dependency injection by creating
a scoped service provider and adding it to the request scope.

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

### 5. Make a request to the endpoint

Make a request to the endpoint:

```python
from starlette.testclient import TestClient

client = TestClient(app)
response = client.get('/greet')
print(response.text)
# {"message": "Hello!"}
```

### Full example

You can find the full example [here](example.py).

```
> python example.py
All tests passed!
```

## Documentation

Find the complete documentation [here](https://daireto.github.io/starlette-di/).

## Contributing

Please read the [contribution guidelines](CONTRIBUTING.md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE)
file for details.

## Support

If you find this project useful, give it a ⭐ on GitHub to show your support!
