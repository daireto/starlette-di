from typing import Protocol

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


# Protocol definitions
class IGreeter(Protocol):
    def greet(self, name: str = '') -> str: ...


class ICounter(Protocol):
    def count(self) -> int: ...

    def get_count(self) -> int: ...

    def reset_to(self, value: int) -> None: ...


class IServicesTester(Protocol):
    def test(self) -> None: ...


# Service implementations
class Greeter(IGreeter):
    def greet(self, name: str = '') -> str:
        if name:
            return f'Hello, {name}!'
        return 'Hello!'


class ScopedService:
    pass


class Counter(ICounter):
    def __init__(self, scoped: ScopedService, greeter: IGreeter):
        self._count = 0
        self._scoped = scoped
        self._greeter = greeter

    def count(self) -> int:
        self._count += 1
        return self._count

    def get_count(self) -> int:
        return self._count

    def reset_to(self, value: int) -> None:
        self._count = value


class ServicesTester(IServicesTester):
    def __init__(
        self, greeter: IGreeter, counter: ICounter, scoped: ScopedService
    ):
        self._greeter = greeter
        self._counter = counter
        self._scoped = scoped

    def test(self):
        return {
            'greeter_id': id(self._greeter),
            'counter_id': id(self._counter),
            'scoped_id': id(self._scoped),
        }


# Request DTOs
class ResetCounter(BaseModel):
    value: int


class SendGreetToAnyone(BaseModel):
    name: str


# Test utilities
def greeter_factory():
    return Greeter()


def counter_factory(scoped: ScopedService, greeter: IGreeter):
    return Counter(scoped, greeter)


def scoped_factory():
    return ScopedService()


def services_tester_factory(
    greeter: IGreeter, counter: ICounter, scoped: ScopedService
):
    return ServicesTester(greeter, counter, scoped)


services = ServiceCollection()
services.add_transient(IGreeter, Greeter)
services.add_singleton(ICounter, Counter)
services.add_scoped(ScopedService, ScopedService)
services.add_transient(IServicesTester, ServicesTester)
provider = services.build_provider()

factory_services = ServiceCollection()
factory_services.add_transient(IGreeter, greeter_factory)
factory_services.add_singleton(ICounter, counter_factory)
factory_services.add_scoped(ScopedService, scoped_factory)
factory_services.add_transient(IServicesTester, services_tester_factory)
factory_provider = factory_services.build_provider()


# Test endpoints
@inject
async def greet(request: Request, greeter: IGreeter):
    return JSONResponse({'message': greeter.greet()})


class CounterEndpoint(HTTPEndpoint):
    @inject_method
    async def get(
        self,
        request: Request,
        counter: ICounter,
    ):
        return JSONResponse({'value': counter.count()})

    @inject_method
    async def post(
        self,
        request: Request,
        counter: ICounter,
        reset: ResetCounter,
    ):
        counter.reset_to(reset.value)
        return JSONResponse({'value': counter.get_count()})


@inject_class
class GreetAndCountEndpoint(HTTPEndpoint):

    i_am_not_a_callable = 1

    def __init__(
        self,
        scope,
        receive,
        send,
        greeter: IGreeter,
        request: Request,
        unknown: int = 1,
    ):
        super().__init__(scope, receive, send)
        self.greeter = greeter
        self.request = request

    async def get(self, request: Request, counter: ICounter, name: str = ''):
        return JSONResponse(
            {
                'message': self.greeter.greet(name),
                'count': counter.count(),
            }
        )

    async def post(
        self,
        request: Request,
        counter: ICounter,
        reset: ResetCounter,
        greet: SendGreetToAnyone,
    ):
        counter.reset_to(reset.value)
        return JSONResponse(
            {
                'message': f'Hello, {greet.name}!',
                'count': counter.get_count(),
            }
        )


@inject_class
class GetCountEndpoint(HTTPEndpoint):
    def __init__(
        self,
        scope,
        receive,
        send,
        service_provider,
        counter: ICounter,
        other=0,
    ):
        super().__init__(scope, receive, send)
        self.counter = counter

    async def get(
        self, request, same_request: Request, other=4, unknown: int = 1
    ):
        return {'value': self.counter.get_count()}


class CustomEndpoint:
    @inject_method(pass_request=False)
    async def greet(self, greeter: IGreeter):
        return {'message': greeter.greet()}


@inject
async def services_tester(
    request: Request,
    greeter: IGreeter,
    counter: ICounter,
    scoped: ScopedService,
    services_tester: IServicesTester,
):
    ids_from_tester = services_tester.test()
    return JSONResponse(
        {
            'greeter_id': id(greeter),
            'counter_id': id(counter),
            'scoped_id': id(scoped),
            'tester_ids': ids_from_tester,
        }
    )


# Test client
def create_test_client() -> TestClient:
    """Create a configured test client with all necessary services."""
    routes = [
        Route('/greet', greet),
        Route('/counter', CounterEndpoint),
        Route('/all', GreetAndCountEndpoint),
        Route('/all/{name:str}', GreetAndCountEndpoint),
        Route('/wrong_param/{name:int}', GreetAndCountEndpoint),
        Route('/test-services', services_tester),
    ]

    app = Starlette(
        routes=routes,
        middleware=[
            Middleware(
                DependencyInjectionMiddleware, service_provider=provider
            )
        ],
    )

    return TestClient(app)
