"""Shared configuration for the MVC application."""
from datetime import timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=7))
