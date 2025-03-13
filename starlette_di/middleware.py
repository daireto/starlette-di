"""This module provides the ``DependencyInjectionMiddleware``
class to handle dependency injection.
"""

from uuid import uuid4

from starlette.types import ASGIApp, Receive, Scope, Send

from .definitions import SERVICE_PROVIDER_ARG_NAME
from .service_provider import ServiceProvider


class DependencyInjectionMiddleware:
    """Middleware for dependency injection.

    It sets up the request scope for dependency injection by
    creating a scoped service provider and adding it to the
    request scope.

    >>> from starlette_di.definitions import SERVICE_PROVIDER_ARG_NAME
    >>> request.scope[SERVICE_PROVIDER_ARG_NAME]
    <starlette_di.service_provider.ScopedServiceProvider object at 0x00000...>
    """

    app: ASGIApp
    """ASGI app."""

    service_provider: ServiceProvider
    """Service provider."""

    def __init__(
        self, app: ASGIApp, service_provider: ServiceProvider
    ) -> None:
        """Middleware for dependency injection.

        Parameters
        ----------
        app : ASGIApp
            ASGI app.
        service_provider : ServiceProvider
            Service provider.
        """
        self.app = app
        self.service_provider = service_provider

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        """Sets up the request scope for dependency injection.

        Visit the `Starlette documentation <https://www.starlette.io/middleware/#writing-pure-asgi-middleware>`_
        for more information about ASGI middlewares.
        """
        if scope['type'] != 'http':
            await self.app(scope, receive, send)  # pragma: no cover
            return None  # pragma: no cover

        scope_id = str(uuid4())
        scoped_provider = self.service_provider.create_scope(scope_id)
        scope[SERVICE_PROVIDER_ARG_NAME] = scoped_provider

        try:
            await self.app(scope, receive, send)
        finally:
            scoped_provider.clear_scoped_instances()
