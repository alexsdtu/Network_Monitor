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

def parse_network_range(text: str) -> list[ipaddress.IPv4Address]:
    text = text.strip()
    if not text:
        raise ValueError("Укажите диапазон сети")

    if "-" in text and "/" not in text:
        start_s, end_s = (p.strip() for p in text.split("-", 1))
        start = ipaddress.IPv4Address(start_s)
        end = ipaddress.IPv4Address(end_s)
        if int(end) < int(start):
            raise ValueError("Конечный IP меньше начального")
        return [
            ipaddress.IPv4Address(addr)
            for addr in range(int(start), int(end) + 1)
        ]

    if "/" in text:
        network = ipaddress.IPv4Network(text, strict=False)
        hosts = list(network.hosts())
        if not hosts and network.num_addresses <= 2:
            return [ipaddress.IPv4Address(network.network_address)]
        return hosts

    return [ipaddress.IPv4Address(text)]

def ping_host(ip: str) -> bool:
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(PING_TIMEOUT_MS), ip]
    else:
        sec = max(1, PING_TIMEOUT_MS // 1000)
        cmd = ["ping", "-c", "1", "-W", str(sec), ip]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=(PING_TIMEOUT_MS / 1000) + 2,
            creationflags=subprocess.CREATE_NO_WINDOW if system == "windows" else 0,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False
