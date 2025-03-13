"""This module provides the ``ServiceCollection`` class
to register services.
"""

from collections.abc import Callable
from typing import Literal, TypeVar

from .service_provider import Service, ServiceProvider

T = TypeVar('T')


class ServiceCollection:
    """Collection of services.

    **Lifetime of services**

    - singleton: one instance for the application lifetime
    - scoped: one instance per request
    - transient: new instance created each time it's requested

    **Use with DependencyInjectionMiddleware**

    When using the ``DependencyInjectionMiddleware``,
    you should pass the service provider returned by the
    ``build_provider`` method to the middleware::

        services = ServiceCollection()
        services.add_transient(IFoo, Foo)
        services.add_singleton(IBar, Bar)
        services.add_scoped(IBaz, Baz)
        provider = services.build_provider()

        app = Starlette(
            routes=[Route('/foo', FooEndpoint)],
            middleware=[
                Middleware(DependencyInjectionMiddleware, service_provider=provider),
            ]
        )
    """

    _services: dict[type, Service]
    """Registered services."""

    def __init__(self) -> None:
        """Collection of services."""
        self._services = {}

    def add_singleton(
        self,
        service_type: type[T],
        implementation: type[T] | Callable[..., T] | None = None,
    ):
        """Register a service as a singleton
        (one instance for the application lifetime).

        If no implementation is provided, the service type
        is used as the implementation.

        Parameters
        ----------
        service_type : type[T]
            Service type.
        implementation : type[T] | Callable[..., T] | None, optional
            Implementation type or factory function, by default None.

        Returns
        -------
        Self
            Service collection.

        Examples
        --------
        Add a class as a singleton service:
        >>> services = ServiceCollection()
        >>> services.add_singleton(IFoo, Foo)

        Add a factory function as a singleton service:
        >>> def foo_factory():
        ...     return Foo()
        >>> services = ServiceCollection()
        >>> services.add_singleton(IFoo, foo_factory)
        """
        return self.add('singleton', service_type, implementation)

    def add_transient(
        self,
        service_type: type[T],
        implementation: type[T] | Callable[..., T] | None = None,
    ):
        """Register a service as transient
        (new instance created each time it's requested).

        If no implementation is provided, the service type
        is used as the implementation.

        Parameters
        ----------
        service_type : type[T]
            Service type.
        implementation : type[T] | Callable[..., T] | None, optional
            Implementation type or factory function, by default None.

        Returns
        -------
        Self
            Service collection.

        Examples
        --------
        Add a class as a transient service:
        >>> services = ServiceCollection()
        >>> services.add_transient(IFoo, Foo)

        Add a factory function as a transient service:
        >>> def foo_factory():
        ...     return Foo()
        >>> services = ServiceCollection()
        >>> services.add_transient(IFoo, foo_factory)
        """
        return self.add('transient', service_type, implementation)

    def add_scoped(
        self,
        service_type: type[T],
        implementation: type[T] | Callable[..., T] | None = None,
    ):
        """Register a service as scoped
        (one instance per request).

        If no implementation is provided, the service type
        is used as the implementation.

        Parameters
        ----------
        service_type : type[T]
            Service type.
        implementation : type[T] | Callable[..., T] | None, optional
            Implementation type or factory function, by default None.

        Returns
        -------
        Self
            Service collection.

        Examples
        --------
        Add a class as a scoped service:
        >>> services = ServiceCollection()
        >>> services.add_scoped(IFoo, Foo)

        Add a factory function as a scoped service:
        >>> def foo_factory():
        ...     return Foo()
        >>> services = ServiceCollection()
        >>> services.add_scoped(IFoo, foo_factory)
        """
        return self.add('scoped', service_type, implementation)

    def add(
        self,
        lifetime: Literal['singleton', 'scoped', 'transient'],
        service_type: type[T],
        implementation: type[T] | Callable[..., T] | None = None,
    ):
        """Registers a service.

        If no implementation is provided, the service type
        is used as the implementation.

        Parameters
        ----------
        lifetime : {'singleton', 'scoped', 'transient'}
            Lifetime of the service.
        service_type : type[T]
            Service type.
        implementation : type[T] | Callable[..., T] | None, optional
            Implementation type or factory function, by default None.

        Returns
        -------
        Self
            Service collection.

        Examples
        --------
        Add a class as a singleton service:
        >>> services = ServiceCollection()
        >>> services.add('singleton', IFoo, Foo)

        Add a factory function as a scoped service:
        >>> def foo_factory():
        ...     return Foo()
        >>> services = ServiceCollection()
        >>> services.add('scoped', IFoo, foo_factory)
        """
        if implementation is None:
            implementation = service_type

        self._services[service_type] = Service(
            lifetime=lifetime,
            implementation=implementation,
            instance=None,
        )

        return self

    def build_provider(self) -> ServiceProvider:
        """Builds a service provider from the registered services.

        **Use with DependencyInjectionMiddleware**

        When using the ``DependencyInjectionMiddleware``,
        you should pass the service provider returned by this method
        to the middleware::

            services = ServiceCollection()
            services.add_transient(IFoo, Foo)
            services.add_singleton(IBar, Bar)
            services.add_scoped(IBaz, Baz)
            provider = services.build_provider()

            app = Starlette(
                routes=[Route('/foo', FooEndpoint)],
                middleware=[
                    Middleware(DependencyInjectionMiddleware, service_provider=provider),
                ]
            )

        Returns
        -------
        ServiceProvider
            Service provider.
        """
        return ServiceProvider(self._services)
