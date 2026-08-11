"""Legacy-compatible entrypoint for the TronClass automation CLI."""

from __future__ import annotations

import sys as _sys

# Force UTF-8 stdio regardless of the OS console codepage. All CLI help text,
# config templates, and log lines are Traditional Chinese; without this, the
# first Chinese character written to stdout/stderr raises UnicodeEncodeError
# and kills the process on any non-UTF-8/non-CJK Windows locale (e.g. the
# default en-US cp1252 codepage — this is exactly what GitHub Actions'
# windows-latest runner uses, and what any English-locale Windows machine
# would hit running --help). Must happen before anything else prints.
# reconfigure() is best-effort: some frozen/redirected stdio objects don't
# support it, so a failure here is silently ignored rather than fatal.
for _stream in (_sys.stdout, _sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:  # pragma: no cover - package import path
    from troTHU import runtime_context as _ctx
except ImportError:  # pragma: no cover - direct script fallback
    import runtime_context as _ctx  # type: ignore


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(_ctx.main())


_sys.modules[__name__] = _ctx
