import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from starlette_di.service_collection import ServiceCollection
from starlette_di.service_provider import Service

from ._core import (
    Counter,
    Greeter,
    ICounter,
    IGreeter,
    IServicesTester,
    ScopedService,
    ServicesTester,
    create_test_client,
    factory_provider,
    greet,
    provider,
)


@pytest.fixture(scope='session')
def test_client():
    return create_test_client()


def test_service_collection(test_client):
    services = ServiceCollection()
    services.add_transient(IGreeter, Greeter)
    services.add_singleton(ICounter, Counter)
    services.add_scoped(ScopedService)
    services.add_transient(IServicesTester, ServicesTester)
    assert IGreeter in services._services
    assert ICounter in services._services
    assert ScopedService in services._services
    assert IServicesTester in services._services
    assert services._services[IGreeter].implementation == Greeter
    assert services._services[ICounter].implementation == Counter
    assert services._services[ScopedService].implementation == ScopedService
    assert services._services[IServicesTester].implementation == ServicesTester
    assert services._services[IGreeter].lifetime == 'transient'
    assert services._services[ICounter].lifetime == 'singleton'
    assert services._services[ScopedService].lifetime == 'scoped'
    assert services._services[IServicesTester].lifetime == 'transient'

    provider = services.build_provider()
    scoped = provider.create_scope('test')
    assert scoped.get_service(IGreeter) is not None
    assert scoped.get_service(ICounter) is not None
    assert scoped.get_service(ScopedService) is not None
    assert scoped.get_service(IServicesTester) is not None

    last_scoped_id = id(scoped.get_service(ScopedService))
    scoped.clear_scoped_instances()
    assert id(scoped.get_service(ScopedService)) != last_scoped_id


def test_transient_service(test_client):
    # first request
    response = test_client.get('/test-services')
    data = response.json()
    last_id = data['greeter_id']
    assert last_id != data['tester_ids']['greeter_id']

    # second request
    response = test_client.get('/test-services')
    data = response.json()
    assert data['greeter_id'] != last_id
    assert data['greeter_id'] != data['tester_ids']['greeter_id']


def test_scoped_service(test_client):
    # first request
    response = test_client.get('/test-services')
    data = response.json()
    last_id = data['scoped_id']
    assert last_id == data['tester_ids']['scoped_id']

    # second request
    response = test_client.get('/test-services')
    data = response.json()
    assert data['scoped_id'] != last_id
    assert data['scoped_id'] == data['tester_ids']['scoped_id']


def test_singleton_service(test_client):
    # first request
    response = test_client.get('/test-services')
    data = response.json()
    last_id = data['counter_id']
    assert last_id == data['tester_ids']['counter_id']

    # second request
    response = test_client.get('/test-services')
    data = response.json()
    assert data['counter_id'] == last_id
    assert data['counter_id'] == data['tester_ids']['counter_id']


def test_factory_functions():
    scope_id = 'test'
    scoped_service_provider = factory_provider.create_scope(scope_id)
    assert isinstance(scoped_service_provider.get_service(IGreeter), Greeter)
    assert isinstance(scoped_service_provider.get_service(ICounter), Counter)
    assert isinstance(
        scoped_service_provider.get_service(ScopedService), ScopedService
    )
    assert isinstance(
        scoped_service_provider.get_service(IServicesTester), ServicesTester
    )


# Errors
def test_no_service_provider_error():
    app = Starlette(routes=[Route('/greet', endpoint=greet)])
    client = TestClient(app)
    with pytest.raises(RuntimeError):
        client.get('/greet')


def test_service_type_not_registered_error():
    with pytest.raises(KeyError):
        provider.get_service(int)


def test_no_implementation_registered_error():
    provider._services[int] = Service(
        lifetime='transient', implementation=None, instance=None
    )
    with pytest.raises(ValueError):
        provider.get_service(int)
    provider._services.pop(int)


def test_scope_id_is_required_for_scoped_services_error():
    with pytest.raises(ValueError):
        provider.get_service(ScopedService)


def test_unsupported_service_lifetime_error():
    class Temp:
        pass

    provider._services[Temp] = Service(
        lifetime='unknown',  # type: ignore
        implementation=Temp,
        instance=None,
    )
    with pytest.raises(ValueError):
        provider.get_service(Temp)
    provider._services.pop(Temp)


def test_no_service_registered_for_parameter_error():
    class Temp1:
        pass

    class Temp2:
        def __init__(self, greeter: IGreeter, other: int = 1): ...

    def temp(scoped: Temp1): ...

    assert isinstance(provider._run_factory(Temp2), Temp2)

    with pytest.raises(ValueError):
        provider._run_factory(temp)
