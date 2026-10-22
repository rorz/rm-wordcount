// SPDX-License-Identifier: GPL-3.0-only
import QtQuick 2.15
import QtQml.WorkerScript 2.15
import "scene.mjs" as Scene

Item {
    id: counter
    property string documentId: ""
    property string pageId: ""
    property bool countingEnabled: false
    // Overridable only by the local test harness.
    property string dataDirectory: "file:///home/root/.local/share/remarkable/xochitl"
    property int refreshInterval: 2000
    readonly property bool validPage: /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(documentId)
                                      && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(pageId)
    readonly property bool polling: countingEnabled && validPage && visible && Qt.application.state === Qt.ApplicationActive
    readonly property string pageKey: documentId + "/" + pageId
    property int wordCount: -1
    property string errorMessage: ""
    property int generation: 0
    property var request: null
    property bool workerBusy: false
    property var lastPayload: null
    readonly property string label: wordCount < 0 ? (errorMessage ? "Words —" : "Words …")
                                                 : wordCount + (wordCount === 1 ? " word" : " words")

    function cancelRead() {
        deadline.stop()
        if (request) {
            var old = request
            request = null
            old.onreadystatechange = function() {}
            old.abort()
        }
    }
    function invalidate() {
        generation++
        cancelRead()
        lastPayload = null
        wordCount = -1
        errorMessage = ""
        if (polling) Qt.callLater(refresh)
    }
    function fail(message) {
        wordCount = -1
        errorMessage = message
        lastPayload = null
    }
    function refresh() {
        if (!polling || request || workerBusy || !worker.ready) return
        var token = generation
        var xhr = new XMLHttpRequest()
        request = xhr
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE || request !== xhr) return
            request = null
            deadline.stop()
            if (token !== generation || !polling) return
            try {
                if (xhr.status !== 0 && xhr.status !== 200) throw new Error("Page is not available")
                if (!xhr.response || xhr.response.byteLength === 0) throw new Error("Waiting for a saved page")
                var payload = Scene.textPayload(xhr.response)
                if (lastPayload && lastPayload.length === payload.length) {
                    var same = true
                    for (var i = 0; i < payload.length; i++) {
                        if (payload[i] !== lastPayload[i]) { same = false; break }
                    }
                    if (same) return
                }
                lastPayload = payload
                workerBusy = true
                worker.sendMessage({ generation: token, payload: payload })
            } catch (error) { fail(String(error.message)) }
        }
        xhr.open("GET", dataDirectory + "/" + pageKey + ".rm", true)
        xhr.responseType = "arraybuffer"
        deadline.start()
        xhr.send()
    }

    onPageKeyChanged: invalidate()
    onPollingChanged: {
        // Focus/visibility changes do not change the page. Keep its count and
        // parsed-payload cache, then check for a newer save when it resumes.
        if (polling) Qt.callLater(refresh)
        else cancelRead()
    }
    Component.onDestruction: cancelRead()

    Timer {
        interval: counter.refreshInterval
        repeat: true
        running: counter.polling
        onTriggered: counter.refresh()
    }
    Timer {
        id: deadline
        interval: 5000
        onTriggered: { counter.cancelRead(); counter.fail("Page read timed out") }
    }
    WorkerScript {
        id: worker
        source: "worker.mjs"
        onReadyChanged: if (ready) counter.refresh()
        onMessage: function(message) {
            counter.workerBusy = false
            // A hidden page may finish an already-started parse. Cache that
            // result; generation still rejects results for a different page.
            if (message.generation !== counter.generation) {
                if (counter.polling) Qt.callLater(counter.refresh)
                return
            }
            counter.wordCount = message.count
            counter.errorMessage = message.error
            if (message.error) counter.lastPayload = null
        }
    }
    Rectangle {
        id: badge
        objectName: "wordCountBadge"
        visible: counter.countingEnabled && counter.validPage
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 24
        width: caption.implicitWidth + 28
        height: caption.implicitHeight + 16
        color: "white"
        border.color: "#b8b8b8"
        border.width: 1
        radius: 6
        // No input handlers: writing and selection pass through this overlay.
        Text {
            id: caption
            anchors.centerIn: parent
            text: counter.label
            color: "#424242"
            font.family: "Noto Sans"
            font.pixelSize: 22
            textFormat: Text.PlainText
        }
        // The tablet's Qt build has no Accessible attached object. Referencing
        // it here prevents the entire component from loading.
    }
}
