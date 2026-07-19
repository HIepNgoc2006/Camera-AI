"""Persistence ports for the Camera Registry application boundary."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from camera_registry_service.domain.models import (
    Camera,
    CameraAuditIntent,
    CameraChangeRequest,
    RegistryChangeOutcome,
    TrustedRegistryContext,
    Zone,
    ZoneChangeRequest,
)


class CameraRegistryRepository(Protocol):
    def create_zone(
        self,
        zone: Zone,
        audit_intent: CameraAuditIntent,
    ) -> RegistryChangeOutcome:
        """Atomically create a tenant zone and its audit intent or return an identical retry."""

    def change_zone(
        self,
        request: ZoneChangeRequest,
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        """Atomically update/deactivate a tenant zone with optimistic concurrency."""

    def create_camera(
        self,
        camera: Camera,
        audit_intent: CameraAuditIntent,
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        """Atomically create a camera after locking and rechecking its owned zone."""

    def change_camera(
        self,
        request: CameraChangeRequest,
        context: TrustedRegistryContext,
    ) -> RegistryChangeOutcome:
        """Atomically update, map, or deactivate a tenant camera."""

    def get_zone(self, zone_id: UUID, school_id: UUID) -> Zone | None:
        """Return only a tenant-owned zone."""

    def get_camera(self, camera_id: UUID, school_id: UUID) -> Camera | None:
        """Return only a tenant-owned camera."""
