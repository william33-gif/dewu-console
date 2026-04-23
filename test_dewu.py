import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

from appium import webdriver
from appium.options.android import UiAutomator2Options


APPIUM_URL = os.environ.get("DEWU_APPIUM_URL", "http://127.0.0.1:4723")
DEVICE_UDID = os.environ.get("DEWU_UDID", "f9e0c554")
ADB_PATH = os.environ.get("DEWU_ADB_PATH", r"C:\Users\Administrator\AppData\Local\Android\Sdk\platform-tools\adb.exe")
PUSHED_IMAGES = os.environ.get("DEWU_PUSHED_IMAGES", "")
TASK_TITLE = os.environ.get("DEWU_TITLE", "").strip()
TASK_CONTENT = os.environ.get("DEWU_CONTENT", "").strip()
TASK_ID = os.environ.get("DEWU_TASK_ID", "").strip()
RESULT_DIR = os.environ.get("DEWU_RESULT_DIR", "").strip()
RESULT_URL_PREFIX = os.environ.get("DEWU_RESULT_URL_PREFIX", "/media/results").rstrip("/")

TITLE_FIELD_X = int(os.environ.get("DEWU_TITLE_X", "157"))
TITLE_FIELD_Y = int(os.environ.get("DEWU_TITLE_Y", "583"))
CONTENT_FIELD_X = int(os.environ.get("DEWU_CONTENT_X", "157"))
CONTENT_FIELD_Y = int(os.environ.get("DEWU_CONTENT_Y", "850"))
PUBLISH_BUTTON_X = int(os.environ.get("DEWU_PUBLISH_X", "996"))
PUBLISH_BUTTON_Y = int(os.environ.get("DEWU_PUBLISH_Y", "177"))
FOCUS_TAP_COUNT = int(os.environ.get("DEWU_FOCUS_TAP_COUNT", "1"))

FOCUS_SETTLE_SECONDS = 0.12
PASTE_SETTLE_SECONDS = 0.35
PASTE_KEYCODE = 279
EDITOR_READY_SECONDS = float(os.environ.get("DEWU_EDITOR_READY_SECONDS", "2.0"))
PUBLISH_RESULT_WAIT_SECONDS = float(os.environ.get("DEWU_PUBLISH_RESULT_WAIT_SECONDS", "1.0"))


caps = {
    "platformName": "Android",
    "appium:automationName": "UiAutomator2",
    "appium:deviceName": "Android",
    "appium:udid": DEVICE_UDID,
    "appium:appPackage": "com.shizhuang.duapp",
    "appium:appActivity": "com.shizhuang.duapp.modules.home.ui.HomeActivity",
    "appium:noReset": True,
    "appium:ignoreHiddenApiPolicyError": True,
    "appium:newCommandTimeout": 120,
}

driver = webdriver.Remote(
    APPIUM_URL,
    options=UiAutomator2Options().load_capabilities(caps),
)


def log(message: str) -> None:
    print(message, flush=True)


def tap(x: int, y: int, desc: str = "") -> None:
    driver.execute_script(
        "mobile: clickGesture",
        {
            "x": x,
            "y": y,
        },
    )
    if desc:
        log(f"Tapped: {desc} ({x}, {y})")


def adb_tap(x: int, y: int, desc: str = "") -> bool:
    try:
        completed = subprocess.run(
            [ADB_PATH, "-s", DEVICE_UDID, "shell", "input", "tap", str(x), str(y)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:
        log(f"ADB tap failed for {desc}: {exc}")
        return False

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        log(f"ADB tap returned non-zero for {desc}: {detail or completed.returncode}")
        return False

    if desc:
        log(f"ADB tapped: {desc} ({x}, {y})")
    return True


def focus_text_field(x: int, y: int, desc: str) -> None:
    for attempt in range(FOCUS_TAP_COUNT):
        tap_desc = f"{desc} focus {attempt + 1}"
        if not adb_tap(x, y, tap_desc):
            tap(x, y, tap_desc)
        time.sleep(FOCUS_SETTLE_SECONDS)


def paste_into_focused_field(value: str, desc: str) -> None:
    driver.set_clipboard_text(value, label=f"dewu_{desc}")
    time.sleep(0.08)
    driver.press_keycode(PASTE_KEYCODE)
    time.sleep(PASTE_SETTLE_SECONDS)
    log(f"Pasted {desc}")


def fill_editor_fields(title: str, content: str) -> None:
    if title:
        focus_text_field(TITLE_FIELD_X, TITLE_FIELD_Y, "title")
        paste_into_focused_field(title, "title")
    else:
        log("No title provided, skip title fill")

    if content:
        focus_text_field(CONTENT_FIELD_X, CONTENT_FIELD_Y, "content")
        paste_into_focused_field(content, "content")
    else:
        log("No content provided, skip content fill")


def tap_publish_button() -> None:
    if not adb_tap(PUBLISH_BUTTON_X, PUBLISH_BUTTON_Y, "publish"):
        tap(PUBLISH_BUTTON_X, PUBLISH_BUTTON_Y, "publish")
    log("Publish button tapped")


def capture_publish_screenshot() -> str | None:
    if not RESULT_DIR:
        log("Publish screenshot skipped: no result dir configured")
        return None

    result_dir = Path(RESULT_DIR)
    result_dir.mkdir(parents=True, exist_ok=True)
    task_slug = TASK_ID or f"dewu_{int(time.time())}"
    filename = f"{task_slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    screenshot_path = result_dir / filename

    if not driver.save_screenshot(str(screenshot_path)):
        log("Publish screenshot failed: driver.save_screenshot returned false")
        return None

    screenshot_url = f"{RESULT_URL_PREFIX}/{filename}" if RESULT_URL_PREFIX else str(screenshot_path)
    log(f"Publish screenshot saved: {screenshot_path}")
    log(f"PUBLISH_SCREENSHOT_URL={screenshot_url}")
    return screenshot_url


log(f"Connected to device: {DEVICE_UDID}, Appium: {APPIUM_URL}")
log(f"ADB path: {ADB_PATH}")
if PUSHED_IMAGES:
    log(f"Pushed images: {PUSHED_IMAGES}")
if TASK_TITLE:
    log(f"Task title received: {TASK_TITLE}")
if TASK_CONTENT:
    log(f"Task content received: length={len(TASK_CONTENT)}")
log(f"Title focus point: ({TITLE_FIELD_X}, {TITLE_FIELD_Y})")
log(f"Content focus point: ({CONTENT_FIELD_X}, {CONTENT_FIELD_Y})")
log(f"Publish point: ({PUBLISH_BUTTON_X}, {PUBLISH_BUTTON_Y})")
log(f"Editor ready wait: {EDITOR_READY_SECONDS}s")
log(f"Publish screenshot wait: {PUBLISH_RESULT_WAIT_SECONDS}s")

try:
    time.sleep(1.3)

    tap(945, 2265, "Me")
    time.sleep(1.5)

    tap(132, 599, "Creator Center")
    time.sleep(2.5)

    tap(996, 177, "Top Right Plus")
    time.sleep(2.5)

    points = [
        (307, 973),
        (1036, 608),
        (671, 608),
        (307, 608),
    ]

    for idx, (x, y) in enumerate(points, start=1):
        tap(x, y, f"Image {idx}")
        time.sleep(0.55)

    log("Selected 4 images")
    time.sleep(0.9)

    tap(935, 2212, "Next 1")
    time.sleep(1.2)

    tap(935, 2212, "Next 2")
    time.sleep(EDITOR_READY_SECONDS)

    fill_editor_fields(TASK_TITLE, TASK_CONTENT)
    time.sleep(0.5)
    tap_publish_button()
    time.sleep(PUBLISH_RESULT_WAIT_SECONDS)
    capture_publish_screenshot()
    log("PUBLISH_SUCCESS")
except Exception as exc:
    log(f"Script failed: {exc}")
    raise
finally:
    driver.quit()
