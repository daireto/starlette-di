"""This module provides the ``Service`` class
to store service information and the ``ServiceProvider``
class to resolve services.

It also provides the ``ScopedServiceProvider`` class
to resolve scoped services.
"""

from collections.abc import Callable
from dataclasses import dataclass
from inspect import Parameter, isclass, signature
from typing import Any, Generic, Literal, TypeVar

T = TypeVar('T', bound=object)


@dataclass
class Service(Generic[T]):
    """Service information."""

    lifetime: Literal['singleton', 'scoped', 'transient']
    """Lifetime of the service."""

    implementation: type[T] | Callable[..., T] | None
    """Implementation of the service.

    It can be a class or a factory function.
    """

    instance: T | None = None
    """Instance of the service."""


class ServiceProvider:
    """Service provider for resolving services."""

    _services: dict[type, Service]
    """Registered services."""

    _scoped_instances: dict[str, dict[type, Any]]
    """Scoped instances."""

    def __init__(self, services: dict[type, Service]) -> None:
        """Service provider for resolving services.

        Parameters
        ----------
        services : dict[type, Service]
            Registered services.
        """
        self._services = services
        self._scoped_instances = {}

    def get_service(
        self, service_type: type[T], scope_id: str | None = None
    ) -> T:
        """Resolves a service instance based on its registered type.

        Parameters
        ----------
        service_type : type[T]
            Service type.
        scope_id : str | None, optional
            Scope id, by default None.

        Returns
        -------
        T
            Service instance.

        Raises
        ------
        KeyError
            If the service is not registered.
        ValueError
            If no implementation or factory function is registered.
        ValueError
            If a scope id is required for scoped services.
        ValueError
            If the service lifetime is not supported.
        """
        if service_type not in self._services:
            raise KeyError(
                f'service {service_type.__name__} is not registered'
            )

        service = self._services[service_type]

        if not service.implementation:
            raise ValueError(
                f'no implementation registered for {service_type.__name__}'
            )

        # handle singletons (created once for application lifetime)
        if service.lifetime == 'singleton':
            if service.instance is None:
                if isclass(service.implementation):
                    service.instance = self._instantiate(
                        service.implementation, scope_id
                    )
                else:
                    service.instance = self._run_factory(
                        service.implementation, scope_id
                    )

            return service.instance  # type: ignore

        # handle scoped services (created once per request)
        elif service.lifetime == 'scoped':
            if scope_id is None:
                raise ValueError('a scope id is required for scoped services')

            if scope_id not in self._scoped_instances:
                self._scoped_instances[scope_id] = {}

            if service_type not in self._scoped_instances[scope_id]:
                if isclass(service.implementation):
                    self._scoped_instances[scope_id][service_type] = (
                        self._instantiate(service.implementation, scope_id)
                    )
                else:
                    self._scoped_instances[scope_id][service_type] = (
                        self._run_factory(service.implementation, scope_id)
                    )

            return self._scoped_instances[scope_id][service_type]

        # handle transient services (created each time)
        elif service.lifetime == 'transient':
            if isclass(service.implementation):
                return self._instantiate(service.implementation, scope_id)
            else:
                return self._run_factory(service.implementation, scope_id)

        raise ValueError(f'unsupported service lifetime: {service.lifetime!r}')

    def create_scope(self, scope_id: str) -> 'ScopedServiceProvider':
        """Creates a scoped service provider.

        Parameters
        ----------
        scope_id : str
            Scope id.

        Returns
        -------
        ScopedServiceProvider
            Scoped service provider.
        """
        return ScopedServiceProvider(self, scope_id)

    def clear_scoped_instances(self, scope_id: str) -> None:
        """Clears scoped instances for a given ``scope_id``.

        Parameters
        ----------
        scope_id : str
            Scope id.
        """
        if scope_id in self._scoped_instances:
            del self._scoped_instances[scope_id]

    def _instantiate(self, cls: type[T], scope_id: str | None = None) -> T:
        """Instantiates a class, resolving its
        constructor dependencies.

        Parameters
        ----------
        cls : type[T]
            Class to instantiate.
        scope_id : str | None, optional
            Scope id, by default None.

        Returns
        -------
        T
            Class instance.
        """
        return cls(**self._parse_params(cls, scope_id))

    def _run_factory(
        self, factory: Callable[..., T], scope_id: str | None = None
    ) -> T:
        """Runs a factory function, resolving its
        dependencies.

        Parameters
        ----------
        factory : Callable[..., T]
            Factory function.
        scope_id : str | None, optional
            Scope id, by default None.

        Returns
        -------
        T
            Factory function result.
        """
        return factory(**self._parse_params(factory, scope_id))

    def _parse_params(
        self, class_or_func: Callable[..., T], scope_id: str | None = None
    ) -> dict[str, type]:
        """Parses the parameters of a class constructor or
        a factory function.

        Parameters
        ----------
        class_or_func : Callable[..., T]
            Class or factory function.
        scope_id : str | None, optional
            Scope id, by default None.

        Returns
        -------
        dict[str, type]
            Dict of parameter names and types.

        Raises
        ------
        ValueError
            If a service is not registered.
        """
        params = {}

        is_constructor = isclass(class_or_func)
        if is_constructor:
            class_or_func = class_or_func.__init__  # type: ignore

        sig = signature(class_or_func)
        for param_name, param in sig.parameters.items():
            if is_constructor and param_name == 'self':
                continue

            if param.annotation is Parameter.empty:
                continue

            if param.annotation not in self._services:
                if param.default is not Parameter.empty:
                    continue

                raise ValueError(
                    f'no service registered for {param.annotation.__name__}'
                )

            # resolve the dependency
            params[param_name] = self.get_service(param.annotation, scope_id)

        return params


class ScopedServiceProvider:
    """Scoped service provider."""

    _provider: ServiceProvider
    """Parent service provider."""

    _scope_id: str
    """Scope id."""

    def __init__(self, provider: ServiceProvider, scope_id: str) -> None:
        """Creates a scoped service provider.

        Parameters
        ----------
        provider : ServiceProvider
            Parent service provider.
        scope_id : str
            Scope id.
        """
        self._provider = provider
        self._scope_id = scope_id

    def get_service(self, service_type: type[T]) -> T:
        """Resolves a service instance based on its registered type.

        Parameters
        ----------
        service_type : type[T]
            Service type.

        Returns
        -------
        T
            Service instance.

        Raises
        ------
        KeyError
            If the service is not registered.
        ValueError
            If no implementation or factory function is registered.
        ValueError
            If a scope id is required for scoped services.
        ValueError
            If the service lifetime is not supported.
        """
        return self._provider.get_service(service_type, self._scope_id)

    def clear_scoped_instances(self) -> None:
        """Clears scoped instances."""
        self._provider.clear_scoped_instances(self._scope_id)
