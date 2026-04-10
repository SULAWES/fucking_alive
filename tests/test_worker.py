import unittest
from unittest.mock import patch

import app.worker as worker_module


class WorkerTests(unittest.TestCase):
    def test_scheduler_does_not_start_when_disabled(self) -> None:
        with patch.object(worker_module.settings, "alert_scheduler_enabled", False), patch.object(
            worker_module, "BlockingScheduler"
        ) as scheduler_cls:
            worker_module.main()

        scheduler_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
