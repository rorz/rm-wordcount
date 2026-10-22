#!/usr/bin/env python3
"""Apply the *shipped hashed patch* with upstream QMLDiff and a synthetic UI.

This validates QMLDiff syntax, insertions, and the firmware guard. It does not
prove that a tablet's private QML has the expected structure. That remains a
device test. Set QMLDIFF to a built upstream qmldiff executable.
"""
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile

from build import PATCHES

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = {
    11313888899523275277: "/Toolbar.qml",
    11704595946725378272: "/SettingsMenu.qml",
    6025599999262907645: "/MoreMenu.qml",
    1224665461898798997: "/Notebook.qml",
    8397993708429497603: "Item",
    6504254477: "root",
    454089850271038938: "Item",
    254480451320573660: "Component",
    16710723433319324941: "menuContent",
    14125623155555875541: "Column",
    233724020048228: "content",
    425121728314878811: "Ark",
    432643201877711221: "MenuItem",
    214632764553: "label",
    233745975898428: "toolbar",
    254542236275632405: "onClicked",
    15738511857451076348: "closeMenus",
    254547437090201330: "sceneView",
    7712934851008712: "document",
    5972374: "id",
    6504167078: "page",
    254533375641282938: "resolvePageId",
}

FIXTURES = {
    "Toolbar.qml": "import QtQuick 2.15\nItem { id: root; function closeMenus() {} }",
    "SettingsMenu.qml": '''import QtQuick 2.15
import "ark" as Ark
Item { id: root; property var toolbar; Component { id: menuContent; Column { id: content } }
Loader { sourceComponent: menuContent } }''',
    "MoreMenu.qml": '''import QtQuick 2.15
import "ark" as Ark
Item { id: root; property var toolbar; Column {} }''',
    "Notebook.qml": '''import QtQuick 2.15
Item { id: root
    property alias toolbar: bar
    property QtObject sceneView: QtObject {
        property var document: ({ id: "11111111-1111-1111-1111-111111111111",
            resolvePageId: function(index) { return "22222222-2222-2222-2222-222222222222"; } })
        property int page: 0
    }
    Toolbar { id: bar; objectName: "toolbar" }
}''',
}


def check():
    executable = os.environ.get("QMLDIFF", "qmldiff")
    with tempfile.TemporaryDirectory(prefix="rm-wordcount-patch-") as temp:
        temp = Path(temp)
        source = temp / "source"
        source.mkdir()
        for name, contents in FIXTURES.items(): (source / name).write_text(contents)
        hashtab = temp / "hashtab"
        hashtab.write_bytes(b"".join(struct.pack(">QI", h, len(s.encode())) + s.encode() for h, s in SYMBOLS.items()))
        allowed_versions = ("3.27.3.0", "3.27.30", "3.28.0.172")
        for version in (*allowed_versions, "3.27.1.0", "3.28.0.0", "3.28.0.171", "3.28.0.173", "3.29.0.0", "3.270.0", "3.26.0.0"):
            destination = temp / version
            command = [executable, "apply-diffs", "--hashtab", str(hashtab), "--version", version,
                       str(source), str(destination), *[str(ROOT / path) for path in PATCHES.values()]]
            result = subprocess.run(command, text=True, capture_output=True)
            assert result.returncode == 0, result.stdout + result.stderr
            emitted = {p.name: p.read_text() for p in destination.rglob("*.qml")}
            if version in allowed_versions:
                assert len(emitted) == 4, emitted
                assert "property alias rmWordCountEnabled" in " ".join(emitted["Toolbar.qml"].split()), emitted["Toolbar.qml"]
                assert 'import Qt.labs.settings 1.0 as RmWordCountPrefs' in emitted["Toolbar.qml"]
                assert 'Hide word count' in emitted["SettingsMenu.qml"]
                assert 'Hide word count' in emitted["MoreMenu.qml"]
                assert 'Loader' in emitted["Notebook.qml"]
                assert 'resolvePageId' in emitted["Notebook.qml"]
                # Both adapters ship together. Their guards must ensure each
                # supported firmware gets exactly one toggle and one overlay.
                assert len(re.findall(r"\bproperty\s+alias\s+rmWordCountEnabled\b", emitted["Toolbar.qml"])) == 1, emitted["Toolbar.qml"]
                assert emitted["SettingsMenu.qml"].count("Hide word count") == 1
                assert emitted["MoreMenu.qml"].count("Hide word count") == 1
                assert len(re.findall(r"\bid\s*:\s*rmWordCountLoader\b", emitted["Notebook.qml"])) == 1, emitted["Notebook.qml"]
                saved = ROOT / "test-results/patched"
                saved.mkdir(parents=True, exist_ok=True)
                for name, contents in emitted.items(): (saved / name).write_text(contents)
                (saved / "ark").mkdir(exist_ok=True)
                (saved / "ark/MenuItem.qml").write_text('''import QtQuick 2.15
Item { objectName: "menuToggle"; property string label; signal clicked() }''')
            else:
                assert not any("rmWordCount" in text for text in emitted.values()), emitted
    print("PASS: released QMLDiff selects exactly one adapter on 3.27.3.0, 3.27.30 and 3.28.0.172; other versions get no injected UI")


if __name__ == "__main__": check()
