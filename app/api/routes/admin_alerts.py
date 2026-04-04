from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.alerts import AlertingService
from app.api.deps.admin import require_admin_token

router = APIRouter(prefix="/admin", tags=["admin"])


class TestAlertRequest(BaseModel):
    recipients: list[str] = Field(min_length=1)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)


@router.post("/test-alert", dependencies=[Depends(require_admin_token)])
def test_alert(request: TestAlertRequest) -> dict[str, int | str]:
    service = AlertingService()
    delivered = service.send_test_alert(
        recipients=request.recipients,
        subject=request.subject,
        body=request.body,
    )
    return {"status": "sent", "delivered": delivered}
