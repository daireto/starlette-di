"""This module provides the types used in the DI system."""

from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from starlette.responses import Response

T = TypeVar('T')
P = ParamSpec('P')

EndpointFunction = Callable[P, Awaitable[Response]]
