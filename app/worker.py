import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from app.alerts import AlertingService
from app.core.config import settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging(settings.log_level)
    scheduler = BlockingScheduler(timezone=settings.app_timezone)
    service = AlertingService()

    scheduler.add_job(
        _run_alert_scan,
        "interval",
        minutes=settings.alert_scan_interval_minutes,
        next_run_time=datetime.now(),
        args=[service],
        id="alert-scan",
        replace_existing=True,
    )

    logger.info(
        "starting alert scheduler: interval_minutes=%s timezone=%s",
        settings.alert_scan_interval_minutes,
        settings.app_timezone,
    )
    scheduler.start()


def _run_alert_scan(service: AlertingService) -> None:
    result = service.run_scan_once()
    logger.info(
        "alert scan completed: scanned_users=%s overdue_users=%s delivered=%s failed=%s skipped=%s",
        result.scanned_users,
        result.overdue_users,
        result.delivered,
        result.failed,
        result.skipped,
        extra={"event_type": "alert_scan", "delivery_status": "DONE"},
    )


if __name__ == "__main__":
    main()
