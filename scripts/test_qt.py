#!/usr/bin/env python3
"""Exercise the actual QML/XHR/WorkerScript pipeline in an offscreen Qt engine.

Install PySide6-Essentials==6.8.3 into a disposable venv, then run this script
with that interpreter. No server, browser, or tablet connection is needed.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ["QML_XHR_ALLOW_FILE_READ"] = "1"

import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import time

from PySide6.QtCore import QObject, QPointF, QUrl, QSettings, QMetaObject, QEvent, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QJSEngine
from PySide6.QtQuick import QQuickWindow
from shiboken6 import delete

ROOT = Path(__file__).resolve().parents[1]
DOC = "11111111-1111-1111-1111-111111111111"
PAGE_A = "22222222-2222-2222-2222-222222222222"
PAGE_B = "33333333-3333-3333-3333-333333333333"
warnings = []

def message_handler(kind, context, message):
    if "Fontconfig" not in message:
        warnings.append(message)

qInstallMessageHandler(message_handler)
app = QGuiApplication(sys.argv)
app.setOrganizationName("rm-wordcount-test")
app.setApplicationName("rm-wordcount-test")

def wait_for(predicate, label, timeout=4):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        app.processEvents()
        app.sendPostedEvents(None, QEvent.DeferredDelete)
        if predicate(): return
        time.sleep(0.01)
    raise AssertionError(f"Timed out: {label}; Qt messages: {warnings}")

def settle(seconds=0.3):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        app.processEvents()
        app.sendPostedEvents(None, QEvent.DeferredDelete)
        time.sleep(0.01)

def varuint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    return bytes(result) + bytes([value])

def text_page(text, suffix="", delete_suffix=False):
    """Synthetic v6 page with an original chunk and a later edited chunk."""
    def sub(tag, data):
        return bytes([tag * 16 + 12]) + struct.pack("<I", len(data)) + data
    def ident(tag, author, clock):
        return bytes([tag * 16 + 15, author]) + varuint(clock)
    def item(author, value, left_author=0, left_clock=0, deleted=0):
        encoded = value.encode()
        return sub(0, ident(2, author, 1) + ident(3, left_author, left_clock) + ident(4, 0, 0)
                   + b"\x54" + struct.pack("<I", deleted)
                   + sub(6, varuint(len(encoded)) + b"\x01" + encoded))
    items = [item(1, text)]
    if suffix:
        items.append(item(2, "" if delete_suffix else suffix, 1, len(text), len(suffix) if delete_suffix else 0))
    body = (ident(1, 0, 0) + sub(2, sub(1, sub(1, varuint(len(items)) + b"".join(items))) + sub(2, sub(1, b"\x00")))
            + sub(3, bytes(16)) + b"\x44" + bytes(4))
    return b"reMarkable .lines file, version=6          " + struct.pack("<I", len(body)) + b"\x00\x01\x01\x07" + body

# Exercise the slow-path size in Qt itself: V8/Node hides Qt's linear Map lookup.
js = QJSEngine()
js.globalObject().setProperty("scene", js.importModule(str(ROOT / "src/scene.mjs")))
started = time.monotonic()
result = js.evaluate('''scene.orderedText([{
    id: [1, 1], left: [0, 0], right: [0, 0], deleted: 0, format: false,
    text: "ordinary ".repeat(4000)
}]).length''')
elapsed = time.monotonic() - started
assert not result.isError(), result.toString()
assert result.toInt() == 36000
assert elapsed < 3, f"Long-page reconstruction regressed: {elapsed:.3f}s"
print(f"Qt reconstruction: 4000 words in {elapsed:.3f}s (desktop)")
delete(js)

with tempfile.TemporaryDirectory(prefix="rm-wordcount-qt-") as temp:
    temp = Path(temp)
    folder = temp / DOC
    folder.mkdir()
    a, b = folder / f"{PAGE_A}.rm", folder / f"{PAGE_B}.rm"
    shutil.copyfile(ROOT / "tests/fixtures/Bold_Heading_Bullet_Normal.rm", a)
    shutil.copyfile(ROOT / "tests/fixtures/Normal_AB.rm", b)
    source = f'''import QtQuick 2.15
import QtQuick.Window 2.15
import {json.dumps((ROOT / 'src').as_uri())} as WordCount
Window {{
    visible: true
    width: 1000; height: 1300
    color: "#faf9f6"
    WordCount.Counter {{
        objectName: "counter"
        anchors.fill: parent
        documentId: "{DOC}"
        pageId: "{PAGE_A}"
        countingEnabled: true
        dataDirectory: {json.dumps(temp.as_uri())}
        refreshInterval: 100
        property bool pauseOnParse: false
        property string pageAfterParseStarts: ""
        property int parseStarts: 0
        onWorkerBusyChanged: {{
            if (!workerBusy) return;
            parseStarts++;
            if (pauseOnParse) visible = false;
            if (pageAfterParseStarts) {{
                var nextPage = pageAfterParseStarts;
                pageAfterParseStarts = "";
                pageId = nextPage;
            }}
        }}
    }}
}}'''
    engine = QQmlApplicationEngine()
    engine.loadData(source.encode(), QUrl.fromLocalFile(str(temp / "Harness.qml")))
    assert engine.rootObjects(), warnings
    window = engine.rootObjects()[0]
    window.requestActivate()
    counter = window.findChild(QObject, "counter")
    get = counter.property
    put = counter.setProperty

    wait_for(lambda: get("wordCount") == 11, "real page count")
    assert get("label") == "11 words"

    # Save a changed file at the same path: the poll must refresh it.
    shutil.copyfile(ROOT / "tests/fixtures/Normal_AB.rm", a)
    wait_for(lambda: get("wordCount") == 1, "changed save")
    assert get("label") == "1 word"

    # A partly written file must clear the old count, then recover.
    a.write_bytes(b"reMarkable")
    wait_for(lambda: get("wordCount") == -1 and get("errorMessage"), "partial save")
    assert get("label") == "Words —"
    shutil.copyfile(ROOT / "tests/fixtures/Bold_Heading_Bullet_Normal.rm", a)
    wait_for(lambda: get("wordCount") == 11, "recovered save")

    put("pageId", PAGE_B)
    assert get("wordCount") == -1, "must clear the previous page immediately"
    wait_for(lambda: get("wordCount") == 1, "page switch")

    put("countingEnabled", False)
    assert not get("polling")
    shutil.copyfile(ROOT / "tests/fixtures/Bold_Heading_Bullet_Normal.rm", b)
    settle()
    assert get("wordCount") == 1, "keep the cached count while paused"
    put("countingEnabled", True)
    wait_for(lambda: get("wordCount") == 11, "toggle back on")

    put("visible", False)
    assert not get("polling")
    assert get("wordCount") == 11
    generation = get("generation")
    put("visible", True)
    wait_for(lambda: get("wordCount") == 11, "resume after hidden")
    assert get("generation") == generation, "focus changes must not invalidate the page cache"

    long_text = "ordinary " * 1999 + "ordinary"
    b.write_bytes(text_page(long_text))
    wait_for(lambda: get("wordCount") == 2000, "long page")
    b.write_bytes(text_page(long_text, " four five six"))
    wait_for(lambda: get("wordCount") == 2003, "append three words on a long page")
    b.write_bytes(text_page(long_text, " four five six", delete_suffix=True))
    wait_for(lambda: get("wordCount") == 2000, "undo the long-page insertion")

    # Hide precisely when the worker starts: its same-page result must still
    # populate the cache, so resuming never skips a discarded result forever.
    put("pauseOnParse", True)
    b.write_bytes(text_page(long_text, " four five six"))
    wait_for(lambda: get("wordCount") == 2003, "worker completes while hidden")
    assert not get("visible") and not get("polling")
    starts = get("parseStarts")
    put("pauseOnParse", False)
    put("visible", True)
    settle()
    assert get("parseStarts") == starts, "unchanged text must reuse the cached result"

    # Switch pages precisely when the old page begins parsing. Its result may
    # arrive late but must never replace the new page's count.
    put("pageAfterParseStarts", PAGE_A)
    b.write_bytes(text_page(long_text))
    wait_for(lambda: get("pageId") == PAGE_A and get("wordCount") == 11, "page change during a parse")
    put("pageId", PAGE_B)
    wait_for(lambda: get("wordCount") == 2000, "return to long page")

    put("pageId", "../../outside")
    assert not get("validPage") and not get("polling")
    put("pageId", PAGE_B)
    b.unlink()
    wait_for(lambda: bool(get("errorMessage")), "missing page")
    assert get("wordCount") == -1
    shutil.copyfile(ROOT / "tests/fixtures/Wikipedia_highlighted_p1.rm", b)
    wait_for(lambda: get("wordCount") == 0, "page without typed text")

    # Leave a useful image of the actual badge, not an HTML mock-up.
    shutil.copyfile(ROOT / "tests/fixtures/Bold_Heading_Bullet_Normal.rm", b)
    wait_for(lambda: get("wordCount") == 11, "preview")
    settle(0.1)
    target = ROOT / "test-results"
    target.mkdir(exist_ok=True)
    assert window.grabWindow().save(str(target / "counter.png"))

    window.close()
    delete(engine)
    app.processEvents()

# Compile the emitted patch against the synthetic native components and exercise
# both menu actions, the real loader binding, and the persisted setting.
patched = ROOT / "test-results/patched"
assert patched.is_dir(), "Run scripts/test_patch.py with QMLDIFF first"
with tempfile.TemporaryDirectory(prefix="rm-wordcount-menu-") as temp:
    temp = Path(temp)
    shutil.copytree(patched, temp / "ui")
    ui = temp / "ui"
    config = temp / "wordcount.conf"
    toolbar_file = ui / "Toolbar.qml"
    toolbar_file.write_text(toolbar_file.read_text().replace('/home/root/.config/rm-wordcount.conf', str(config)))
    notebook_file = ui / "Notebook.qml"
    notebook_file.write_text(notebook_file.read_text().replace(
        'file:///home/root/xovi/exthome/qt-resource-rebuilder/rm-wordcount/Counter.qml',
        (ROOT / "src/Counter.qml").as_uri()))
    harness = ui / "Harness.qml"
    harness.write_text('''import QtQuick 2.15
import QtQuick.Window 2.15
Window {
    visible: true; width: 1000; height: 1300
    Notebook { id: book; objectName: "notebook"; anchors.fill: parent }
    SettingsMenu { objectName: "settingsMenu"; toolbar: book.toolbar }
    MoreMenu { objectName: "moreMenu"; toolbar: book.toolbar }
}''')

    def load_menu():
        engine = QQmlApplicationEngine()
        engine.load(QUrl.fromLocalFile(str(harness)))
        assert engine.rootObjects(), warnings
        window = engine.rootObjects()[0]
        window.requestActivate()
        app.processEvents()
        bar = window.findChild(QObject, "toolbar")
        settings = window.findChild(QObject, "settingsMenu").findChild(QObject, "menuToggle")
        more = window.findChild(QObject, "moreMenu").findChild(QObject, "menuToggle")
        assert bar and settings and more
        return engine, window, bar, settings, more

    engine, window, bar, settings, more = load_menu()
    assert not bar.property("rmWordCountEnabled")
    assert settings.property("label") == more.property("label") == "Show word count"
    QMetaObject.invokeMethod(settings, "clicked")
    assert bar.property("rmWordCountEnabled")
    assert settings.property("label") == more.property("label") == "Hide word count"
    # The loader created by the actual patch receives the document/page bindings.
    book = window.findChild(QObject, "notebook")
    wait_for(lambda: any(c.metaObject().indexOfProperty("documentId") >= 0 for c in book.findChildren(QObject)), "patched loader")
    counters = [c for c in book.findChildren(QObject) if c.metaObject().indexOfProperty("documentId") >= 0]
    assert len(counters) == 1
    assert counters[0].property("documentId") == DOC and counters[0].property("pageId") == PAGE_A
    badge = counters[0].findChild(QObject, "wordCountBadge")
    wait_for(lambda: badge and badge.property("visible") and badge.width() > 0, "visible patched badge")
    settle(0.1)
    corner = badge.mapToScene(QPointF(0, 0))
    assert corner.x() >= 0 and corner.y() >= 0, "badge must be inside the notebook viewport"
    assert corner.x() + badge.width() <= window.width()
    assert corner.y() + badge.height() <= window.height()
    QMetaObject.invokeMethod(more, "clicked")
    assert not bar.property("rmWordCountEnabled")
    wait_for(lambda: not any(c.metaObject().indexOfProperty("documentId") >= 0 for c in book.findChildren(QObject)), "unloaded counter")
    QMetaObject.invokeMethod(more, "clicked")
    settle(0.7)
    assert QSettings(str(config), QSettings.IniFormat).value("WordCount/counterEnabled", False, type=bool)
    window.close()
    delete(engine)
    app.processEvents()
    engine, window, bar, settings, more = load_menu()
    assert bar.property("rmWordCountEnabled"), "preference must survive a new QML engine"
    assert more.property("label") == "Hide word count"
    window.close()
    delete(engine)
    app.processEvents()

errors = [m for m in warnings if any(word in m for word in ("Error", "is not defined", "Cannot assign", "Failed", "Cannot load"))]
assert not errors, errors
print("PASS: Qt file reads, long-page edits, worker completion while hidden, page changes during parsing, cache reuse, recovery, badge rendering, both patched menus, loader bindings and persisted toggle")
for warning in warnings:
    print("Qt:", warning)
