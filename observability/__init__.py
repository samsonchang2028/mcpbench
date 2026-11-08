"""Bounded local JSONL events. No network or background worker."""
from .jsonl import JsonlWriter, LogError

__all__ = ["JsonlWriter", "LogError"]
