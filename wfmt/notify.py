"""Local Windows toast notifications. Nothing leaves the PC."""
from __future__ import annotations

import logging

from .models import Notice

log = logging.getLogger(__name__)
APP_NAME = "WF Market Tracker"
_toaster = None


def notify(notice: Notice) -> None:
    global _toaster
    try:
        from windows_toasts import Toast, WindowsToaster

        if _toaster is None:
            _toaster = WindowsToaster(APP_NAME)
        toast = Toast([notice.title, notice.body])
        if notice.url:
            toast.launch_action = notice.url
        _toaster.show_toast(toast)
    except Exception as e:  # never let a notification break the app
        log.warning("notification failed: %s", type(e).__name__)
