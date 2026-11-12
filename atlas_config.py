import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
GOOGLE_SHEET_SOURCES = (
    'stopstart',
    'xdp',
    'xdpActivity',
    'amazonShipping',
    'palletwaysSheet',
    'courierIssues',
    'routineLive',
)


def setting(name, default=""):
    value = os.environ.get(name)
    if value is not None:
        return value.strip()
    for filename in (".env.local", ".env"):
        path = ROOT / filename
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == name:
                return value.strip().strip("\"'")
    return default


def google_sheets_enabled():
    return setting('ATLAS_GOOGLE_SHEETS_ENABLED', 'true').lower() not in {'false', '0', 'no'}
