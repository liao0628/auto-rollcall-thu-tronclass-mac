# -*- mode: python ; coding: utf-8 -*-
#
# macOS counterpart of auto-rollcall-thu-tronclass.spec. PyInstaller cannot
# cross-compile, so this file only produces a working binary when run with
# `pyinstaller` ON macOS (e.g. the macos-latest GitHub Actions runner, or a
# real Mac) — never on Windows/Linux.
#
# Differences from the Windows spec, and why:
#   - icon.icns instead of icon.ico (macOS icon format).
#   - The Playwright Node driver is bundled as-is (NOT stripped like the
#     Windows build does with node.exe). The on-demand add-on-bundle
#     downloader in troTHU/addon_runtime.py + troTHU/ocr_sidecar.py currently
#     only knows the Windows binary names ("node.exe", "ocr-sidecar.exe"), so
#     stripping the driver here would leave macOS users with no way to fetch
#     it back. This keeps the macOS build ~90MB larger but functionally
#     complete; revisit once the add-on downloader gains macOS binary names.
#   - No code signing / notarization — this is an unsigned developer build.
#     Gatekeeper will need "right-click > Open" (or `xattr -dr
#     com.apple.quarantine`) the first time; there is no Apple Developer
#     account backing this project.
#
# Keep HIDDEN_IMPORTS/DATAS/EXCLUDES in sync with auto-rollcall-thu-tronclass.spec
# (the canonical Windows spec) by hand — see that file for the authoritative
# list and `python -m troTHU.tron package-check --json` for drift detection.

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_all


APP_NAME = "auto-rollcall-thu-tronclass"
ROOT = Path(globals().get("SPECPATH", ".")).resolve()
ENTRYPOINT = ROOT / "troTHU" / "tron.py"


def safe_collect_submodules(package_name):
    try:
        return collect_submodules(package_name)
    except Exception:
        return []


# Keep local user data outside the bundle. The executable creates or updates
# config.yaml next to itself on first run, and runtime folders such as state/,
# log/, cookies/, tests/, and external reference projects must never be bundled.
# Bundle the factory-default school registry so providers.py can seed
# config.advanced.toml on first run (loaded via __file__/_MEIPASS in providers._seed_path).
DATAS = [
    (str(ROOT / "troTHU" / "schools.toml"), "troTHU"),
]

HIDDEN_IMPORTS = sorted(
    set(
        [
            "troTHU.account_store",
            "troTHU.account_runtime_store",
            "troTHU.addon_runtime",
            "troTHU.adapter_bridge",
            "troTHU.adapter_server",
            "troTHU.answer_flow",
            "troTHU.auth_runtime",
            "troTHU.autoanswer_runtime",
            "troTHU.autoanswer_store",
            "troTHU.app_qr_experience",
            "troTHU.bot_handlers",
            "troTHU.bot_runtime",
            "troTHU.bot_status",
            "troTHU.cli_accounts",
            "troTHU.cli_app",
            "troTHU.cli_bot",
            "troTHU.cli_courses",
            "troTHU.cli_main",
            "troTHU.cli_parser",
            "troTHU.cli_provider",
            "troTHU.cli_qr",
            "troTHU.cli_research",
            "troTHU.cli_system",
            "troTHU.cli_teacher",
            "troTHU.config_runtime",
            "troTHU.config_editor",
            "troTHU.config_view",
            "troTHU.connection_probe",
            "troTHU.course_context",
            "troTHU.course_discovery",
            "troTHU.debug_capture",
            "troTHU.discord_adapter",
            "troTHU.global_radar_solver",
            "troTHU.local_scanner",
            "troTHU.llm_answerer",
            "troTHU.login_flow",
            "troTHU.login_probe",
            "troTHU.line_adapter",
            "troTHU.input_safety",
            "troTHU.log_core",
            "troTHU.console_ui",
            "troTHU.notify_runtime",
            "troTHU.fatal_errors",
            "troTHU.research_crawler",
            "troTHU.monitor_runtime",
            "troTHU.notification_delivery",
            "troTHU.number_rollcall",
            "troTHU.number_runtime",
            "troTHU.notification_bus",
            "troTHU.observability",
            "troTHU.ocr_captcha",
            "troTHU.ocr_sidecar",
            "troTHU.package_diagnostics",
            "troTHU.pending_qr",
            "troTHU.providers",
            "troTHU.qr_rollcall",
            "troTHU.qr_runtime",
            "troTHU.qr_teacher_runtime",
            "troTHU.quiz_engine",
            "troTHU.quiz_models",
            "troTHU.radar_rollcall",
            "troTHU.radar_map_assist",
            "troTHU.radar_solver",
            "troTHU.redaction",
            "troTHU.radar_runtime",
            "troTHU.self_registration_runtime",
            "troTHU.release_builder",
            "troTHU.research_mode",
            "troTHU.research_sandbox",
            "troTHU.release_checklist",
            "troTHU.rollcall_progress",
            "troTHU.rollcall_engine",
            "troTHU.rollcall_models",
            "troTHU.rollcall_runtime",
            "troTHU.runtime_context",
            "troTHU.runtime_helpers",
            "troTHU.config_format",
            "troTHU.group_runtime",
            "troTHU.status_reports",
            "troTHU.telegram_adapter",
            "troTHU.teacher_rollcall",
            "troTHU.tron_http",
            "troTHU.ux_tools",
            "troTHU.webview_sync",
            "aiohttp",
            "aiohttp.web",
            "yaml",
        ]
        + safe_collect_submodules("nacl")
    )
)

# The heavy OCR stack (ddddocr/onnxruntime/cv2/numpy/PIL) is NOT bundled — same
# lean-default policy as the Windows build. There is no macOS OCR sidecar add-on
# yet; users who need it can `pip install -e .[ocr]` and run from source.
EXCLUDES = [
    "aiohttp.pytest_plugin",
    "cv2",
    "ddddocr",
    "keyring",
    "keyrings",
    "mypy",
    "numpy",
    "onnxruntime",
    "PIL",
    "Pillow",
    "pyzbar",
    "pydantic",
    "pydantic_core",
    "pytest",
    "setuptools",
    "tests",
]

playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all("playwright")

combined_datas = DATAS + playwright_datas
combined_binaries = playwright_binaries
combined_hiddenimports = sorted(
    set(
        HIDDEN_IMPORTS
        + playwright_hiddenimports
        + [
            "playwright",
            "playwright.async_api",
            "playwright._impl._driver",
            "greenlet",
            "pyee",
            "troTHU.browser_install",
            "troTHU.addon_runtime",
            "troTHU.ocr_captcha",
            "troTHU.ocr_sidecar",
        ]
    )
)

a = Analysis(
    [str(ENTRYPOINT)],
    pathex=[str(ROOT)],
    binaries=combined_binaries,
    datas=combined_datas,
    hiddenimports=combined_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.icns",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
