"""Approved Identity Service v1 routes."""

from fastapi import APIRouter

from identity_service.api.v1.auth import router as auth_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
