from __future__ import annotations


import csv

from pathlib import Path


UNKNOWN_STR: str = "UNKNOWN"


def str2bool(ins: str) -> bool:
    """Turn a str representation of a bool into a bool"""
    return True if "true" in ins.casefold() else False
