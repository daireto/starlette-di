"""Starlette DI is a dependency injection library for Starlette applications.

It simplifies dependency management by allowing services to be injected using
Scoped, Transient, and Singleton lifetimes (similar to .NET Core). Also,
enables automatic injection of route parameters, and request bodies using
Pydantic models, making API development more efficient, and structured.

Visit the `repository <https://github.com/daireto/starlette-di>`_
for more information.
"""

from .inject import inject, inject_class, inject_method
from .middleware import DependencyInjectionMiddleware
from .service_collection import ServiceCollection
from .service_provider import ScopedServiceProvider, Service, ServiceProvider

__all__ = [
    'inject',
    'inject_class',
    'inject_method',
    'DependencyInjectionMiddleware',
    'ServiceCollection',
    'ScopedServiceProvider',
    'Service',
    'ServiceProvider',
]

__version__ = '0.1.1'
