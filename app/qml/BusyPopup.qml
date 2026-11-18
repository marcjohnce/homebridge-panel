import QtQuick
import QtQuick.Controls.Basic

// Feedback while the panel builds a page or saves (Busy.run): a dimmed screen with a turning
// spinner and what is happening. It fades in slowly on the render thread, so quick work is done
// before it shows and slow work (e.g. on a Raspberry Pi 3) gets visible feedback; taps are
// blocked meanwhile.
Popup {
    id: root

    property string label
    property var work: null

    function run(text, fn) {
        if (opened) {           // already busy: do it right away
            fn();
            return;
        }
        label = text;
        work = fn;
        open();
        fallback.restart();
    }
    // the dimmed screen has been drawn: now block the app with the work
    function start() {
        fallback.stop();
        if (!work)
            return;
        const fn = work;
        work = null;
        try {
            fn();
        } finally {
            close();
        }
    }

    objectName: "busyPopup"
    parent: Overlay.overlay
    x: 0
    y: 0
    width: parent ? parent.width : 0
    height: parent ? parent.height : 0
    modal: true                 // blocks taps on what is below
    dim: false                  // dimmed by the background below, so it fades in with the popup
    closePolicy: Popup.NoAutoClose
    padding: 0
    z: 1000

    enter: Transition {
        // practically invisible for the first ~300 ms, then fades in
        OpacityAnimator { from: 0; to: 1; duration: 600; easing.type: Easing.InExpo }
    }
    exit: null

    // wait for the frame with the (still transparent) popup, so its animation can start before
    // the work blocks the app; the timer covers windows that are not drawn (tests)
    Connections {
        target: root.parent ? root.parent.Window.window : null
        enabled: root.work !== null
        function onFrameSwapped() {
            Qt.callLater(root.start);
        }
    }
    Timer {
        id: fallback
        interval: 120
        onTriggered: root.start()
    }

    background: Rectangle {
        color: Qt.rgba(0, 0, 0, Theme.name === "light" ? 0.25 : 0.45)
    }
    contentItem: Item {
        Rectangle {
            anchors.centerIn: parent
            width: row.implicitWidth + Theme.s(56)
            height: row.implicitHeight + Theme.s(48)
            radius: 18
            color: Theme.tile
            border.color: Theme.line

            Row {
                id: row
                anchors.centerIn: parent
                spacing: Theme.s(18)
                Spinner {
                    anchors.verticalCenter: parent.verticalCenter
                    running: root.visible
                }
                Text {
                    objectName: "busyLabel"
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.label
                    color: Theme.ink
                    font.pixelSize: Theme.s(19)
                }
            }
        }
    }
}
