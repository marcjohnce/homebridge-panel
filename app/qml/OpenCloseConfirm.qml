import QtQuick
import QtQuick.Controls.Basic

// Asks before a garage door is opened or closed or a door lock is unlocked or locked;
// opening / unlocking needs the alarm PIN if one is set
Popup {
    id: root

    property var dev: ({})
    readonly property bool isLock: dev.type === "lock"
    readonly property bool opening: !!dev.state && (isLock ? dev.state.lock !== "unlocked"
                                                           : dev.state.door !== "open" && dev.state.door !== "opening")
    readonly property bool needsPin: opening && panel.alarmPinSet

    function ask(id) {
        dev = panel.device(id);
        pad.entry = "";
        pad.error = "";
        open();
    }
    function confirm() {
        if (needsPin && pad.entry.length < 4)
            return;
        const err = panel.openClose(dev.id, opening, pad.entry);
        if (err !== "") {
            pad.error = err;
            pad.entry = "";
        } else {
            close();
        }
    }

    anchors.centerIn: Overlay.overlay
    width: Theme.s(372)
    padding: 22
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    Overlay.modal: Rectangle {
        color: Qt.rgba(0, 0, 0, 0.35)
    }
    background: Rectangle {
        radius: 18
        color: Theme.tile
    }

    contentItem: Column {
        spacing: 16
        focus: true
        Keys.onReturnPressed: root.confirm()

        Text {
            width: parent.width
            text: root.isLock ? (root.opening ? qsTr("Unlock %1?") : qsTr("Lock %1?")).arg(root.dev.name || "")
                : (root.opening ? qsTr("Open %1?") : qsTr("Close %1?")).arg(root.dev.name || "")
            color: Theme.ink
            font.pixelSize: Theme.s(18)
            font.weight: Font.Medium
            wrapMode: Text.WordWrap
        }
        Text {
            width: parent.width
            visible: root.needsPin
            text: root.isLock ? qsTr("Enter the PIN to unlock") : qsTr("Enter the PIN to open")
            color: Theme.muted
            font.pixelSize: Theme.s(14)
        }
        PinPad {
            id: pad
            objectName: "garagePin"
            width: parent.width
            visible: root.needsPin
            focus: root.needsPin
            onSubmitted: root.confirm()
        }
        Row {
            anchors.right: parent.right
            spacing: 10
            PillButton {
                text: qsTr("Cancel")
                onClicked: root.close()
            }
            PillButton {
                objectName: "garageConfirm"
                primary: true
                text: root.isLock ? (root.opening ? qsTr("Unlock") : qsTr("Lock"))
                    : (root.opening ? qsTr("Open door") : qsTr("Close door"))
                enabled: !root.needsPin || pad.entry.length >= 4
                onClicked: root.confirm()
            }
        }
    }
}
