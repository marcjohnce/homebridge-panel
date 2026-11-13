import QtQuick
import QtQuick.Controls.Basic

// Moves a device to another room; "New room" creates one and moves the device there
Popup {
    id: root

    property var device: ({})
    signal newRoomRequested(var device)

    function pick(d) {
        device = d;
        open();
    }

    anchors.centerIn: Overlay.overlay
    width: Math.min(parent ? parent.width - 40 : Theme.s(560), Theme.s(560))
    padding: Theme.s(24)
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
        spacing: Theme.s(16)

        Text {
            width: parent.width
            text: root.device.name || ""
            color: Theme.ink
            font.pixelSize: Theme.s(19)
            font.weight: Font.Medium
            elide: Text.ElideRight
            Accessible.role: Accessible.Heading
        }
        Text {
            width: parent.width
            text: qsTr("Choose the room for this device.")
            color: Theme.muted
            font.pixelSize: Theme.s(15)
            wrapMode: Text.WordWrap
        }
        Flow {
            objectName: "roomChoices"
            width: parent.width
            spacing: 10
            Repeater {
                model: panel.roomEditor.rooms
                PillButton {
                    required property var modelData
                    objectName: "roomChoice:" + modelData.name
                    text: modelData.name
                    primary: modelData.name === root.device.room
                    onClicked: {
                        panel.roomEditor.assign(root.device.id, modelData.name);
                        root.close();
                    }
                }
            }
            PillButton {
                objectName: "newRoomChoice"
                text: qsTr("New room …")
                onClicked: {
                    root.close();
                    root.newRoomRequested(root.device);
                }
            }
        }
        PillButton {
            anchors.right: parent.right
            text: qsTr("Cancel")
            onClicked: root.close()
        }
    }
}
