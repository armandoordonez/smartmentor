"""Construcción del adaptador del puerto de IA según la configuración (`AI_SERVICE_MODE`)."""

from typing import Annotated

import httpx
from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.domains.ai_gateway.fake import FakeAiService
from app.domains.ai_gateway.http_client import ClientCredentialsTokenProvider, HttpAiService
from app.domains.ai_gateway.repository import AiServicePort


def create_ai_service(settings: Settings) -> tuple[AiServicePort, httpx.AsyncClient | None]:
    """El adaptador y, si abre conexiones, el cliente HTTP que hay que cerrar al apagar."""
    if settings.ai_service_mode == "fake":
        return FakeAiService(), None
    client = httpx.AsyncClient(
        base_url=settings.ai_service_url, timeout=settings.ai_service_timeout_seconds
    )
    tokens = ClientCredentialsTokenProvider(
        token_url=settings.ai_token_url,
        client_id=settings.ai_service_client_id,
        client_secret=settings.ai_service_client_secret.get_secret_value(),
        client=client,
    )
    return HttpAiService(client, tokens), client


def get_ai_service(request: Request) -> AiServicePort:
    """El adaptador de la aplicación (lo crea el `lifespan`; si falta, se crea el de la config)."""
    service: AiServicePort | None = getattr(request.app.state, "ai_service", None)
    if service is None:
        service, _ = create_ai_service(get_settings())
        request.app.state.ai_service = service
    return service


AiServiceDep = Annotated[AiServicePort, Depends(get_ai_service)]
