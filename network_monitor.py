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
