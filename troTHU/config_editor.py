"""Open and reload the human config with the OS's plain-text editor.

Windows uses the built-in legacy Notepad (a stable, always-present binary).
macOS shells out to `open -W -e` (TextEdit, waiting for it to quit). Other
POSIX systems try $VISUAL/$EDITOR, then fall back to a handful of common
editors on PATH."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

try:  # pragma: no cover - package import path
    import troTHU.runtime_context as ctx
except ImportError:  # pragma: no cover - direct script fallback
    import runtime_context as ctx  # type: ignore


LEGACY_NOTEPAD_PATH = Path("C:/Windows/System32/notepad.exe")
_POSIX_FALLBACK_EDITORS = ("xdg-open", "gedit", "kate", "nano", "vi")


def _editor_command(path: Path) -> list[str] | None:
    """Return the argv to open `path` in a text editor for the current OS, or
    None if nothing usable was found."""
    if sys.platform.startswith("win"):
        if LEGACY_NOTEPAD_PATH.exists():
            return [str(LEGACY_NOTEPAD_PATH), str(path)]
        notepad = shutil.which("notepad.exe") or shutil.which("notepad")
        return [notepad, str(path)] if notepad else None
    if sys.platform == "darwin":
        # -W: wait for the app to quit before returning (needed so the caller can
        # reload config right after editing); -e: force TextEdit so a .conf/.toml
        # extension can't get routed to something unexpected.
        return ["open", "-W", "-e", str(path)]
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        return [editor, str(path)]
    for candidate in _POSIX_FALLBACK_EDITORS:
        found = shutil.which(candidate)
        if found:
            return [found, str(path)]
    return None


def open_config_in_legacy_notepad(path: Path, *, wait: bool = True) -> ctx.Dict[str, ctx.Any]:
    config_path = Path(path)
    command = _editor_command(config_path)
    if not command:
        return {"ok": False, "status": "editor_missing", "path": str(config_path)}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        if config_path.name == ctx.CONFIG_ADVANCED_PATH.name:
            ctx.write_advanced_config_file({})
        else:
            ctx.write_config_file(ctx.copy.deepcopy(ctx.DEFAULT_CONFIG))
    process = subprocess.Popen(command)
    if wait:
        process.wait()
    return {"ok": True, "status": "opened", "editor": command[0], "path": str(config_path)}


def config_now_value(config: ctx.Mapping[str, ctx.Any] | None = None) -> str:
    cfg = config or ctx.CONFIG
    simple = cfg.get("_simple") if isinstance(cfg.get("_simple"), dict) else {}
    return ctx.normalize_text(simple.get("now"))


def effective_config_now_value(config: ctx.Mapping[str, ctx.Any] | None = None) -> str:
    cfg = config or ctx.CONFIG
    simple = cfg.get("_simple") if isinstance(cfg.get("_simple"), dict) else {}
    raw_now = ctx.normalize_text(simple.get("now"))
    if raw_now:
        return raw_now
    return ctx.normalize_text(ctx.infer_single_account_now(simple))


def display_config_now_value(value: ctx.Any) -> str:
    text = ctx.normalize_text(value)
    return text or "-"


def reload_config_after_editor() -> ctx.Dict[str, ctx.Any]:
    ctx.CONFIG_BOOTSTRAPPED = False
    config = ctx.bootstrap_config(force=True)
    return {"ok": True, "status": "reloaded", "now": config_now_value(config), "effective_now": effective_config_now_value(config)}


def config_is_ready_to_run() -> bool:
    """True when a real (user, password) can be resolved to log in with.

    Interactive-browser providers (a URL school, or now=URL) need NO config
    password — the user types credentials in the browser — so they are always
    "ready". Otherwise mirror auth_runtime.login's missing-credentials guard
    (real user AND password); blank, placeholder, or still-example credentials
    resolve to "not ready"."""
    try:
        if ctx.provider_requires_interactive_browser_login():
            return True
    except Exception:
        pass
    user, passwd, _ = ctx.resolve_credentials()
    return ctx.has_real_credential(user) and ctx.has_real_credential(passwd)


def ensure_config_now_or_open_editor(config_path: Path | None = None) -> ctx.Dict[str, ctx.Any]:
    path = Path(config_path or ctx.CONFIG_PATH)
    raw_now = config_now_value(ctx.CONFIG)
    effective_now = effective_config_now_value(ctx.CONFIG)
    if config_is_ready_to_run():
        if not raw_now and effective_now:
            ctx.log_print("config.conf 的 now 是空白；偵測到只有一個帳號，將直接使用 `{}`。".format(effective_now))
            return {"ok": True, "status": "inferred_single_account", "now": "", "effective_now": effective_now}
        return {"ok": True, "status": "ready", "now": raw_now, "effective_now": effective_now}
    # Not ready to log in (blank / placeholder / still-example credentials): open the
    # editor exactly once. If it is still not ready after the user closes Notepad, hand
    # back to the caller — which keeps monitoring and waits for a keypress rather than
    # exiting or auto-opening again.
    ctx.log_print("尚未偵測到可用的帳號密碼，將用文字編輯器開啟 config.conf。")
    opened = ctx.open_config_in_legacy_notepad(path, wait=True)
    if not opened.get("ok"):
        return opened
    reloaded = ctx.reload_config_after_editor()
    if config_is_ready_to_run():
        return reloaded
    return {
        "ok": False,
        "status": "still_unconfigured",
        "message": "仍未偵測到可用帳密，將進入監控；按任意鍵可再次編輯 config.conf。",
    }


def _key_poller_windows() -> ctx.Any:
    """Non-blocking single-keypress poll via msvcrt. Returns a `() -> bool`
    callable, or None if msvcrt isn't importable (should not happen on nt)."""
    try:
        import msvcrt
    except Exception:
        return None

    def poll() -> bool:
        if not msvcrt.kbhit():
            return False
        try:
            msvcrt.getwch()
        except Exception:
            pass
        return True

    return poll


def _key_poller_posix() -> ctx.Any:
    """Non-blocking single-keypress poll for macOS/Linux terminals, using cbreak
    mode (so a key is seen immediately, without waiting for Enter) plus a
    zero-timeout select() (msvcrt.kbhit()'s POSIX equivalent). Returns
    (poll, restore), or None when stdin isn't an interactive terminal (piped
    input, service/cron context, etc.) — in that case the caller has no way to
    detect a keypress at all."""
    try:
        import select
        import termios
        import tty
    except Exception:
        return None
    stdin = sys.stdin
    if not stdin.isatty():
        return None
    try:
        fd = stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    except Exception:
        return None

    def poll() -> bool:
        ready, _unused_w, _unused_x = select.select([stdin], [], [], 0)
        if not ready:
            return False
        try:
            stdin.read(1)
        except Exception:
            pass
        return True

    def restore() -> None:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            pass

    return poll, restore


async def watch_any_key_to_edit_config(shutdown_event: ctx.asyncio.Event, session: ctx.Any = None) -> None:
    restore = None
    if ctx.os.name == "nt":
        poll_key_pressed = _key_poller_windows()
    else:
        posix_poller = _key_poller_posix()
        if posix_poller is None:
            await shutdown_event.wait()
            return
        poll_key_pressed, restore = posix_poller
    if poll_key_pressed is None:
        await shutdown_event.wait()
        return
    try:
        while not shutdown_event.is_set():
            await ctx.asyncio.sleep(0.25)
            if not poll_key_pressed():
                continue
            # v1.7: while an auto-answer is prepared in its delay window, a keypress submits it
            # immediately instead of opening the config editor.
            if ctx.autoanswer_has_pending():
                ctx.request_immediate_autoanswer()
                ctx.log_print("偵測到按鍵，立即送出已備妥的自動答題。")
                continue
            ctx.log_print("偵測到按鍵，開啟 config.conf。關閉編輯器後會重新載入設定。")
            before = effective_config_now_value(ctx.CONFIG)
            with ctx.pause_status_line():
                opened = await ctx.asyncio.to_thread(ctx.open_config_in_legacy_notepad, ctx.CONFIG_PATH, wait=True)
            if not opened.get("ok"):
                ctx.log_print("無法開啟文字編輯器: {}".format(opened.get("status")))
                continue
            ctx.reload_config_after_editor()
            after = effective_config_now_value(ctx.CONFIG)
            ctx.LAST_LOGIN_RESULT = ctx.LoginResult(status="transient_error", credential_source="config_reload")
            if after != before:
                ctx.log_print("設定 now 已變更為 `{}`，將清除目前 session 並套用新設定。\n{}".format(
                    display_config_now_value(after), ctx.describe_group_target(ctx.CONFIG)))
                ctx.update_monitor_status(target_label=ctx.group_status_label(ctx.CONFIG), redraw=False)
                try:
                    if session is not None:
                        session.cookie_jar.clear()
                    ctx.clear_session_cookies(ctx.BASE_DIR, ctx.get_active_profile(ctx.CONFIG).name)
                except Exception:
                    pass
    finally:
        if restore is not None:
            restore()
