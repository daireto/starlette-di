import asyncio

import pytest
from starlette.requests import Request

from starlette_di import inject, inject_class

from ._core import (
    CustomEndpoint,
    GetCountEndpoint,
    create_test_client,
    factory_provider,
)


@pytest.fixture(scope='session')
def test_client():
    return create_test_client()


def test_inject_function(test_client):
    response = test_client.get('/greet')
    data = response.json()
    assert data['message'] == 'Hello!'


def test_inject_method(test_client):
    response = test_client.get('/counter')
    data = response.json()
    assert isinstance(data['value'], int)

    response = test_client.post('/counter', json={'value': 10})
    data = response.json()
    assert data['value'] == 10

    # response = test_client.post('/all', json={'reset': 100, 'greet': 'Jane'})
    response = test_client.post(
        '/all', json={'reset': {'value': 100}, 'greet': {'name': 'Jane'}}
    )
    data = response.json()
    assert data['count'] == 100
    assert data['message'] == 'Hello, Jane!'


def test_inject_class(test_client):
    response = test_client.get('/all')
    data = response.json()
    assert data['message'] == 'Hello!'
    assert isinstance(data['count'], int)


def test_service_provider_kwarg():
    sp = factory_provider.create_scope('test')
    scope, receive, send = {'type': 'http', 'service_provider': sp}, None, None
    test = GetCountEndpoint(scope, receive, send, service_provider=sp)  # type: ignore
    data = asyncio.run(test.get(Request(scope, receive, send)))  # type: ignore
    assert data['value'] == 0


def test_path_param(test_client):
    response = test_client.get('/all/Jane')
    data = response.json()
    assert data['message'] == 'Hello, Jane!'


def test_not_pass_request(test_client):
    sp = factory_provider.create_scope('test')
    scope, receive, send = {'type': 'http', 'service_provider': sp}, None, None
    custom_endpoint = CustomEndpoint()
    response = asyncio.run(
        custom_endpoint.greet(Request(scope, receive, send))  # type: ignore
    )
    assert response['message'] == 'Hello!'


# Errors
def test_func_not_async_error():
    def sync_endpoint(): ...

    with pytest.raises(TypeError):
        inject(sync_endpoint)  # type: ignore


def test_service_provider_not_found_error():
    scope, receive, send = {'type': 'http'}, None, None
    with pytest.raises(RuntimeError):
        GetCountEndpoint(scope, receive, send)  # type: ignore


def test_service_provider_not_scoped():
    sp = factory_provider
    scope, receive, send = {'type': 'http', 'service_provider': sp}, None, None
    with pytest.raises(RuntimeError):
        GetCountEndpoint(scope, receive, send, service_provider=sp)  # type: ignore


def test_request_body_must_be_dict_error(test_client):
    with pytest.raises(ValueError):
        test_client.post('/all', json=[])


def test_request_body_must_contain_param_error(test_client):
    with pytest.raises(ValueError):
        test_client.post('/all', json={'reset': {'value': 100}})


def test_param_must_be_dict_error(test_client):
    with pytest.raises(ValueError):
        test_client.post(
            '/all', json={'reset': {'value': 100}, 'greet': 'Jane'}
        )


def test_path_param_must_be_of_type_error(test_client):
    with pytest.raises(TypeError):
        test_client.get('/wrong_param/1')


def test_cls_must_be_an_endpoint_error():
    with pytest.raises(TypeError):
        inject_class(CustomEndpoint)
