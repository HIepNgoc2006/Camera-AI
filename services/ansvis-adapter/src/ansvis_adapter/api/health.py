"""Process-only liveness route."""

from fastapi import APIRouter, Request

from ansvis_adapter.api.errors import request_id_from
from ansvis_adapter.schemas.responses import ErrorResponse, HealthResponse

router = APIRouter(tags=["system"])


@router.get(
    "/healthz",
    response_model=HealthResponse,
    responses={500: {"model": ErrorResponse, "description": "Sanitized internal error"}},
)
async def health(request: Request) -> HealthResponse:
    return HealthResponse(request_id=request_id_from(request))
