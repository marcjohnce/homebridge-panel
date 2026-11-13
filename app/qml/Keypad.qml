import QtQuick
import QtQuick.Controls.Basic

// Keypad for port, PIN and IP address; a connected keyboard works as well
Popup {
    id: root

    property var field: ({})
    property string entry: ""
    property string error: ""
    property var acceptFn: null
    property bool fresh: true

    readonly property string kind: field.kind || "number"
    readonly property int maxLength: kind === "pin" ? 8 : (kind === "number" ? 5 : 253)
    readonly property string display: kind === "pin" ? formatPin(entry) : entry
    readonly property var keys: ["1", "2", "3", "4", "5", "6", "7", "8", "9", kind === "host" ? "." : "", "0", "⌫"]

    function formatPin(d) {
        return d.length <= 3 ? d : d.length <= 5 ? d.slice(0, 3) + "-" + d.slice(3) : d.slice(0, 3) + "-" + d.slice(3, 5) + "-" + d.slice(5);
    }
    function edit(f, value, accept) {
        field = f;
        entry = f.kind === "pin" ? String(value).replace(/\D/g, "") : String(value);
        error = "";
        fresh = true;
        acceptFn = accept;
        open();
    }
    function press(k) {
        error = "";
        if (fresh && k !== "⌫")
            entry = "";
        fresh = false;
        if (k === "⌫")
            entry = entry.slice(0, -1);
        else if (k !== "" && entry.length < maxLength)
            entry += k;
    }
    function done() {
        const value = kind === "pin" ? formatPin(entry) : entry;
        const err = panel.settings.validate(field.key, value);
        if (err !== "") {
            error = err;
            return;
        }
        acceptFn(panel.settings.normalized(field.key, value));
        close();
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
        spacing: 14
        focus: true

        Keys.onPressed: event => {
            if (event.key === Qt.Key_Backspace) {
                root.press("⌫");
            } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                root.done();
            } else if (/^[0-9]$/.test(event.text) || (root.kind === "host" && /^[A-Za-z.\-]$/.test(event.text))) {
                root.press(event.text);
            } else {
                return;
            }
            event.accepted = true;
        }

        Text {
            text: root.field.label || ""
            color: Theme.ink
            font.pixelSize: Theme.s(19)
            font.weight: Font.Medium
        }

        Rectangle {
            objectName: "keypadDisplay"
            width: parent.width
            height: Theme.s(58)
            radius: 10
            color: Theme.page
            border.color: root.error !== "" ? Theme.err : Theme.line

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                x: 12
                width: Math.min(valueText.contentWidth + 8, parent.width - 24)
                height: 40
                radius: 6
                color: Theme.goldSoft
                visible: root.fresh && root.entry !== ""
            }
            Text {
                id: valueText
                anchors.verticalCenter: parent.verticalCenter
                x: 16
                width: parent.width - 32
                text: root.display
                elide: Text.ElideLeft
                color: Theme.ink
                font.pixelSize: Theme.s(28)
                font.weight: Font.Light
                Accessible.role: Accessible.EditableText
                Accessible.name: root.field.label || ""
            }
        }

        Text {
            objectName: "keypadHint"
            width: parent.width
            text: root.error !== "" ? root.error : (root.field.help || "")
            color: root.error !== "" ? Theme.err : Theme.muted
            font.pixelSize: Theme.s(13)
            wrapMode: Text.WordWrap
        }

        Grid {
            objectName: "keypadKeys"
            columns: 3
            spacing: 8
            Repeater {
                model: root.keys
                Rectangle {
                    required property string modelData
                    width: (root.availableWidth - 16) / 3
                    height: Theme.s(56)
                    radius: 12
                    color: keyMouse.pressed ? Theme.tilePress : Theme.page
                    visible: modelData !== ""
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData === "⌫" ? qsTr("Delete") : modelData

                    Text {
                        anchors.centerIn: parent
                        visible: parent.modelData !== "⌫"
                        text: parent.modelData
                        color: Theme.ink
                        font.pixelSize: Theme.s(24)
                        font.weight: Font.Light
                    }
                    LineIcon {
                        anchors.centerIn: parent
                        visible: parent.modelData === "⌫"
                        width: 26
                        height: 26
                        name: "backspace"
                        color: Theme.ink
                    }
                    MouseArea {
                        id: keyMouse
                        anchors.fill: parent
                        onClicked: root.press(parent.modelData)
                        onPressAndHold: if (parent.modelData === "⌫") root.entry = ""
                    }
                }
            }
        }

        Row {
            anchors.right: parent.right
            spacing: 10
            PillButton {
                text: qsTr("Cancel")
                onClicked: root.close()
            }
            PillButton {
                objectName: "keypadDone"
                primary: true
                text: qsTr("Done")
                onClicked: root.done()
            }
        }
    }
}
