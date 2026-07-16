"""Process health endpoint."""

from fastapi import APIRouter, Request

from identity_service.api.errors import request_id_from
from identity_service.schemas import ErrorResponse, HealthResponse

router = APIRouter(tags=["system"])


@router.get(
    "/healthz",
    response_model=HealthResponse,
    responses={500: {"model": ErrorResponse, "description": "Sanitized internal error"}},
    summary="Check Identity process liveness",
)
async def health(request: Request) -> HealthResponse:
    return HealthResponse(request_id=request_id_from(request))
