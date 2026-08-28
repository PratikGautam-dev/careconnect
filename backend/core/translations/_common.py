# core/translations/_common.py
"""Shared types every per-domain string file in this package imports, kept
separate from __init__.py so those domain files can import Language without
importing the package __init__ itself (which imports them back to build the
merged STRINGS dict) -- avoids a circular import."""
from typing import Literal

Language = Literal["en", "hi"]
DEFAULT_LANGUAGE: Language = "en"
SUPPORTED_LANGUAGES: set[str] = {"en", "hi"}
