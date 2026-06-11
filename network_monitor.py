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

def scan_hosts(
    addresses: list[ipaddress.IPv4Address],
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, bool]:
    total = len(addresses)
    results: dict[str, bool] = {}
    done = 0

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, total or 1)) as pool:
        futures = {pool.submit(ping_host, str(ip)): str(ip) for ip in addresses}
        for future in as_completed(futures):
            ip = futures[future]
            try:
                results[ip] = future.result()
            except Exception:
                results[ip] = False
            done += 1
            if on_progress:
                on_progress(done, total)

    return results

class NetworkMonitorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Network Monitor")
        self.root.minsize(720, 480)

        self._hosts: dict[str, HostState] = {}
        self._addresses: list[ipaddress.IPv4Address] = []
        self._monitoring = False
        self._scan_running = False
        self._timer_id: str | None = None
        self._scan_thread: threading.Thread | None = None

        self._build_ui()

def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Диапазон сети:").pack(side=tk.LEFT)
        self.range_var = tk.StringVar(value="192.168.1.0/24")
        self.range_entry = ttk.Entry(top, textvariable=self.range_var, width=28)
        self.range_entry.pack(side=tk.LEFT, padx=(8, 4))

        hint = ttk.Label(
            top,
            text="(CIDR, IP-IP или один IP)",
            foreground="#666",
        )
        hint.pack(side=tk.LEFT)

        buttons = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        buttons.pack(fill=tk.X)

        self.start_btn = ttk.Button(buttons, text="Старт", command=self.start_monitoring)
        self.start_btn.pack(side=tk.LEFT)
        self.stop_btn = ttk.Button(
            buttons, text="Стоп", command=self.stop_monitoring, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=8)

        self.status_var = tk.StringVar(value="Остановлено")
        ttk.Label(buttons, textvariable=self.status_var).pack(side=tk.LEFT, padx=12)

        self.progress = ttk.Progressbar(self.root, mode="determinate")
        self.progress.pack(fill=tk.X, padx=10, pady=(0, 8))

        table_frame = ttk.Frame(self.root, padding=10)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("ip", "status", "last_activity")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("ip", text="IP-адрес")
        self.tree.heading("status", text="Статус")
        self.tree.heading("last_activity", text="Последняя активность")

        self.tree.column("ip", width=160, anchor=tk.W)
        self.tree.column("status", width=200, anchor=tk.W)
        self.tree.column("last_activity", width=220, anchor=tk.W)

        scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure("active", foreground="#1a7f37")
        self.tree.tag_configure("lost", foreground="#c41e3a")

        legend = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        legend.pack(fill=tk.X)
        ttk.Label(
            legend,
            text="Зелёный — активен | Красный — недоступен после повторных проверок "
            f"(≥{FAILURES_BEFORE_LOST}) | Интервал: {SCAN_INTERVAL_SEC} с",
        ).pack(anchor=tk.W)

def start_monitoring(self) -> None:
        try:
            self._addresses = parse_network_range(self.range_var.get())
        except ValueError as exc:
            messagebox.showerror("Ошибка диапазона", str(exc))
            return

        if len(self._addresses) > 1024:
            if not messagebox.askyesno(
                "Подтверждение",
                f"Будет проверено {len(self._addresses)} адресов. Продолжить?",
            ):
                return

self._hosts.clear()
        self._monitoring = True
        self.range_entry.config(state=tk.DISABLED)
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self._run_scan_cycle()

def stop_monitoring(self) -> None:
        self._monitoring = False
        if self._timer_id:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None
        self.range_entry.config(state=tk.NORMAL)
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Остановлено")
        self.progress["value"] = 0
