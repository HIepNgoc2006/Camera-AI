"""Internal adapter; authentication middleware must supply a trusted source context."""

from __future__ import annotations

from collections.abc import Mapping

from notification_service.application.service import NotificationApplicationService
from notification_service.domain.models import NotificationOutcome, TrustedSourceContext


def accept_internal_intent(
    service: NotificationApplicationService,
    payload: Mapping[str, object],
    context: TrustedSourceContext,
) -> NotificationOutcome:
    return service.accept_intent(payload, context)
