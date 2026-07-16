"""Process health endpoint."""

from fastapi import APIRouter, Request

from api_gateway.api.errors import request_id_from
from api_gateway.schemas import ErrorResponse, HealthResponse

router = APIRouter(tags=["system"])


@router.get(
    "/healthz",
    response_model=HealthResponse,
    responses={500: {"model": ErrorResponse, "description": "Sanitized internal error"}},
    summary="Check API process liveness",
)
async def health(request: Request) -> HealthResponse:
    """Report process liveness without dependency or environment details."""

    return HealthResponse(request_id=request_id_from(request))
