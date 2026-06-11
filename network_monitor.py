from __future__ import annotations

import ipaddress
import platform
import subprocess
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable

SCAN_INTERVAL_SEC = 20
PING_TIMEOUT_MS = 1000
MAX_WORKERS = 64
FAILURES_BEFORE_LOST = 2


class HostState:
    last_seen: datetime | None = None
    consecutive_failures: int = 0
    lost: bool = False

    def mark_alive(self) -> None:
        self.last_seen = datetime.now()
        self.consecutive_failures = 0
        self.lost = False

    def mark_dead(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= FAILURES_BEFORE_LOST:
            self.lost = True
