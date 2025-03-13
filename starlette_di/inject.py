"""This module provides the ``inject``, ``inject_method`` and
``inject_class`` decorators.
"""

import warnings
from collections.abc import Callable
from functools import wraps
from inspect import Parameter, isfunction, ismethod, signature
from typing import overload

from pydantic import BaseModel
from starlette._utils import is_async_callable
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import Response

from .definitions import SERVICE_PROVIDER_ARG_NAME
from .service_provider import ScopedServiceProvider
from .types import EndpointFunction, T


def _raise_if_not_async(func: Callable) -> None:
    """Raises a TypeError if the function is not async.

    Parameters
    ----------
    func : Callable
        Function to check.

    Raises
    ------
    TypeError
        If the function is not async.
    """
    if not is_async_callable(func):
        raise TypeError(f'only async functions are supported, got {func}')


def _extract_service_provider(
    request: Request, kwargs: dict[str, object]
) -> ScopedServiceProvider:
    """Extracts the service provider from the kwargs if present,
    otherwise from the request scope.

    Parameters
    ----------
    request : Request
        Starlette request object.
    kwargs : dict[str, object]
        Function kwargs.

    Returns
    -------
    ScopedServiceProvider
        Service provider.

    Raises
    ------
    RuntimeError
        If no service provider is found in request scope.
    RuntimeError
        If the service provider is not an instance of
        di.service_provider.ScopedServiceProvider.
    """
    if SERVICE_PROVIDER_ARG_NAME in kwargs:
        provider = kwargs[SERVICE_PROVIDER_ARG_NAME]
    else:
        provider = request.scope.get(SERVICE_PROVIDER_ARG_NAME)

    if not provider:
        raise RuntimeError(
            'No service provider found in request scope. '
            'Did you add the DependencyInjectionMiddleware?'
        )

    if not isinstance(provider, ScopedServiceProvider):
        raise RuntimeError(
            f'{SERVICE_PROVIDER_ARG_NAME!r} must be an instance '
            'of di.service_provider.ScopedServiceProvider'
        )

    return provider


async def _parse_model_params(
    request: Request, model_params: list[Parameter]
) -> dict[str, BaseModel]:
    """Parses the Pydantic model params from the request body.

    If there's only one Pydantic model param, pass the whole JSON body.
    Otherwise, parse each param from the JSON body.

    Note that the request body must be a JSON dict.

    Parameters
    ----------
    request : Request
        Starlette request object.
    model_params : list[Parameter]
        List of Pydantic model params.

    Returns
    -------
    dict[str, BaseModel]
        Dict of Pydantic model params.

    Raises
    ------
    ValueError
        If the request body is not a JSON dict.
    ValueError
        If the request body doesn't contain a required param.
    ValueError
        If a param is not a JSON dict.
    """
    request_body = await request.json()
    if not isinstance(request_body, dict):
        raise ValueError(
            f'request body must be a dict, got {type(request_body).__name__}'
        )

    # if there's only one Pydantic model param,
    # pass the whole JSON body
    if len(model_params) == 1:
        param = model_params[0]
        return {param.name: param.annotation(**request_body)}

    # otherwise, parse each param from the JSON body
    kwargs = {}
    for param in model_params:
        if param.name not in request_body:
            raise ValueError(f'request body must contain {param.name!r}')
        if not isinstance(request_body[param.name], dict):
            raise ValueError(
                f'param {param.name!r} must be a dict in the request body, '
                f'got {type(request_body[param.name]).__name__}'
            )

        kwargs[param.name] = param.annotation(**request_body[param.name])

    return kwargs


async def _update_kwargs(
    kwargs: dict[str, object],
    func: EndpointFunction,
    request: Request,
    provider: ScopedServiceProvider,
    is_method: bool = False,
) -> None:
    """Updates the kwargs with the dependencies, request path params
    and Pydantic models (request body).

    The update is done in place.

    Parameters
    ----------
    kwargs : dict[str, object]
        Function kwargs.
    func : EndpointFunction
        Function to update kwargs for.
    request : Request
        Starlette request object.
    provider : ScopedServiceProvider
        Service provider.
    is_method : bool, optional
        Whether the function is a method of a class, by default False.

    Raises
    ------
    TypeError
        If a path param is not of the expected type.
    """
    model_params: list[Parameter] = []

    sig = signature(func)
    for param_name, param in sig.parameters.items():
        if param_name == 'self':
            if is_method:
                continue

            warnings.warn(
                f"Parameter 'self' found in function {func.__qualname__!r}. "
                f"You should either remove the 'self' parameter or use the "
                "@inject_method decorator instead of @inject",
                category=UserWarning,
            )  # pragma: no cover

        if param_name == 'request' or param_name in kwargs:
            continue

        if param.annotation is Parameter.empty:
            continue

        # if param is a request (this is a rare case)
        if param.annotation is Request:
            kwargs[param_name] = request
            continue

        # if param is a Pydantic model (the request body)
        if issubclass(param.annotation, BaseModel):
            model_params.append(param)
            continue

        # resolve dependency
        try:
            kwargs[param_name] = provider.get_service(param.annotation)
        except KeyError:
            # if service isn't registered, let the original func handle it
            pass

        # for example: /path/{param}
        if param_name in request.path_params:
            path_param = request.path_params[param_name]
            if param.annotation is not type(path_param):
                raise TypeError(
                    f'path param {param_name!r} must be of type '
                    f'{param.annotation.__name__}'
                )

            kwargs[param_name] = request.path_params[param_name]
            continue

    if model_params:
        kwargs.update(await _parse_model_params(request, model_params))


def _update_constructor_kwargs(
    kwargs: dict[str, object],
    orig_init: Callable,
    request: Request,
    provider: ScopedServiceProvider,
) -> None:
    """Updates the kwargs of a class constructor with the dependencies.

    The update is done in place.

    Parameters
    ----------
    kwargs : dict[str, object]
        Class constructor kwargs.
    orig_init : Callable
        Class constructor.
    request : Request
        Starlette request object.
    provider : ScopedServiceProvider
        Service provider.
    """
    sig = signature(orig_init)
    for param_name, param in sig.parameters.items():
        if (
            param_name
            in ('self', 'scope', 'receive', 'send', 'service_provider')
            or param_name in kwargs
        ):
            continue

        if param.annotation is Parameter.empty:
            continue

        # if param is a request (this is a rare case)
        if param.annotation is Request:
            kwargs[param_name] = request
            continue

        # resolve dependency
        try:
            kwargs[param_name] = provider.get_service(param.annotation)
        except KeyError:
            # if service isn't registered, let the original init handle it
            pass


def _inject_constructor(cls: type[T]) -> None:
    """Injects dependencies into a class constructor."""
    orig_init = cls.__init__

    @wraps(orig_init)
    def wrapper(self, *args, **kwargs):
        request = Request(
            kwargs.get('scope', args[0]),
            kwargs.get('receive', args[1]),
            kwargs.get('send', args[2]),
        )

        provider = _extract_service_provider(request, kwargs)

        _update_constructor_kwargs(kwargs, orig_init, request, provider)
        orig_init(self, *args, **kwargs)

    cls.__init__ = wrapper


def _inject_class_methods(cls: type[T]) -> None:
    """Injects dependencies, request path params and Pydantic models
    into class methods."""
    for name, method in cls.__dict__.items():
        if name.startswith('__'):
            continue
        if not (callable(method) and (isfunction(method) or ismethod(method))):
            continue
        setattr(cls, name, inject_method(method))


class _InjectMethodDecorator:
    """See the ``inject_method`` function for more details."""

    def __init__(self, pass_request: bool) -> None:
        self.pass_request = pass_request

    def __call__(self, func: EndpointFunction):
        _raise_if_not_async(func)

        pass_request = self.pass_request

        @wraps(func)
        async def wrapper(self, request: Request, *args, **kwargs) -> Response:
            # here, self is not the instance of this decorator class,
            # but the instance of the class that this decorator is applied to
            provider = _extract_service_provider(request, kwargs)
            await _update_kwargs(
                kwargs, func, request, provider, is_method=True
            )

            if pass_request:
                return await func(self, request, *args, **kwargs)

            return await func(self, *args, **kwargs)

        return wrapper


def inject(func: EndpointFunction):
    """Decorator for injecting dependencies, request path params and
    Pydantic models into an endpoint function.

    .. note::
        The decorated function must be asynchronous. Otherwise,
        it will raise a ``TypeError``.

    Examples
    --------
    The following steps show how to use this decorator:

    1. Create a service collection and build a service provider:
    >>> services = ServiceCollection()
    >>> services.add_transient(IGreeter, Greeter)
    >>> provider = services.build_provider()

    2. Inject dependencies into an endpoint function:
    >>> @inject
    ... async def greet(request: Request, greeter: IGreeter):
    ...     return JSONResponse({'message': greeter.greet()})

    3. Use the DependencyInjectionMiddleware to handle dependency injection:
    >>> app = Starlette(
    ...     routes=[Route('/greet', greet)],
    ...     middleware=[
    ...         Middleware(DependencyInjectionMiddleware, service_provider=provider),
    ...     ]
    ... )

    4. Make a request to the endpoint:
    >>> client = TestClient(app)
    >>> response = client.get('/greet')
    >>> await response.json()
    {'message': 'Hello!'}
    """
    _raise_if_not_async(func)

    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        provider = _extract_service_provider(request, kwargs)
        await _update_kwargs(kwargs, func, request, provider)
        return await func(request, *args, **kwargs)

    return wrapper


@overload
def inject_method(func: EndpointFunction): ...


@overload
def inject_method(*, pass_request: bool = True): ...


def inject_method(
    func: EndpointFunction | None = None, pass_request: bool = True
):
    """Decorator for injecting dependencies, request path params and
    Pydantic models into an endpoint method (a method of a class).

    If the ``pass_request`` argument is set to ``False``, the request
    object is not passed to the method. This is useful when implementing
    a custom ``starlette.routing.Route`` class for endpoints that do not
    expect the request object to be passed. For example::

        @inject_method(pass_request=False)
        async def get(self, greeter: IGreeter):
            return JSONResponse({'message': greeter.greet()})

    .. note::
        The decorated method must be asynchronous. Otherwise,
        it will raise a ``TypeError``.

    Examples
    --------
    The following steps show how to use this decorator:

    1. Create a service collection and build a service provider:
    >>> services = ServiceCollection()
    >>> services.add_transient(IGreeter, Greeter)
    >>> provider = services.build_provider()

    2. Inject dependencies into an endpoint method:
    >>> class GreetEndpoint(HTTPEndpoint):
    ...     @inject_method
    ...     async def get(self, request: Request, greeter: IGreeter):
    ...         return JSONResponse({'message': greeter.greet()})

    3. Use the DependencyInjectionMiddleware to handle dependency injection:
    >>> app = Starlette(
    ...     routes=[Route('/greet', GreetEndpoint)],
    ...     middleware=[
    ...         Middleware(DependencyInjectionMiddleware, service_provider=provider),
    ...     ]
    ... )

    4. Make a request to the endpoint:
    >>> client = TestClient(app)
    >>> response = client.get('/greet')
    >>> await response.json()
    {'message': 'Hello!'}
    """
    if func is not None:
        # called as @inject_method
        return _InjectMethodDecorator(pass_request)(func)

    # called as @inject_method()
    return _InjectMethodDecorator(pass_request)


def inject_class(cls: type[T]):
    """Decorator for injecting dependencies into a class constructor.
    It also injects dependencies, request path params and Pydantic
    models into the methods of the class.

    This decorator must be used on subclasses of ``HTTPEndpoint``,
    otherwise it will raise a ``TypeError``.

    .. note::
        The methods of the decorated class must be asynchronous.
        Otherwise, it will raise a ``TypeError``.

    Examples
    --------
    The following steps show how to use this decorator:

    1. Create a service collection and build a service provider:
    >>> services = ServiceCollection()
    >>> services.add_transient(IGreeter, Greeter)
    >>> provider = services.build_provider()

    2. Inject dependencies into an endpoint class:
    >>> @inject_class
    ... class GreetEndpoint(HTTPEndpoint):
    ...     def __init__(self, request: Request, greeter: IGreeter):
    ...         super().__init__(request)
    ...         self.greeter = greeter
    ...
    ...     async def get(self, request: Request):
    ...         return JSONResponse({'message': self.greeter.greet()})

    3. Use the DependencyInjectionMiddleware to handle dependency injection:
    >>> app = Starlette(
    ...     routes=[Route('/greet', GreetEndpoint)],
    ...     middleware=[
    ...         Middleware(DependencyInjectionMiddleware, service_provider=provider),
    ...     ]
    ... )

    4. Make a request to the endpoint:
    >>> client = TestClient(app)
    >>> response = client.get('/greet')
    >>> await response.json()
    {'message': 'Hello!'}
    """
    if not issubclass(cls, HTTPEndpoint):
        raise TypeError('cls must be a subclass of HTTPEndpoint')

    _inject_constructor(cls)
    _inject_class_methods(cls)
    return cls
