"""Approved versioned API Gateway routes."""

from fastapi import APIRouter

from api_gateway.api.v1.identity import router as identity_router

router = APIRouter(prefix="/api/v1")
router.include_router(identity_router)
