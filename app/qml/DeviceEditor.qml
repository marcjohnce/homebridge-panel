import QtQuick
import QtQuick.Controls.Basic

// Edit a device in Settings → Rooms and devices: display name, kind (contact and motion
// sensors: window, door, glass break …) and room. Saved together with "Save".
Popup {
    id: root

    property var device: ({})
    property var keyboard: null          // TextKeyboard of the page
    property string draftName
    property string draftKind
    property string draftRoom
    property string error

    function edit(d) {
        device = d;
        draftName = d.name;
        draftKind = d.kind || "";
        draftRoom = d.room;
        error = "";
        open();
    }
    function save() {
        const err = panel.roomEditor.saveDevice(device.id, draftName, draftKind, draftRoom);
        if (err !== "")
            error = err;
        else
            close();
    }
    function editName() {
        keyboard.hint = qsTr("Leave empty to use the name from Homebridge");
        keyboard.maxLength = 40;
        keyboard.edit(qsTr("Display name"), draftName, text => {
            root.draftName = text.trim() === "" ? root.device.baseName : text.trim().replace(/\s+/g, " ");
            return "";
        });
    }
    function newRoom() {
        keyboard.hint = "";
        keyboard.maxLength = 24;
        keyboard.edit(qsTr("New room"), "", text => {
            const err = panel.roomEditor.addRoom(text);
            if (err === "")
                root.draftRoom = text.trim().replace(/\s+/g, " ");
            return err;
        });
    }

    anchors.centerIn: Overlay.overlay
    width: Math.min(parent ? parent.width - 40 : Theme.s(640), Theme.s(640))
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
        spacing: Theme.s(12)

        Text {
            width: parent.width
            text: qsTr("Edit device")
            color: Theme.ink
            font.pixelSize: Theme.s(19)
            font.weight: Font.Medium
            Accessible.role: Accessible.Heading
        }

        Text {
            text: qsTr("Display name")
            color: Theme.muted
            font.pixelSize: Theme.s(14)
        }
        Rectangle {
            objectName: "deviceName"
            width: parent.width
            height: Theme.s(54)
            radius: 10
            color: Theme.page
            border.color: activeFocus ? Theme.gold : Theme.line
            border.width: activeFocus ? 2 : 1
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Change %1, currently %2").arg(qsTr("Display name")).arg(root.draftName)
            Keys.onReturnPressed: root.editName()

            Text {
                anchors.verticalCenter: parent.verticalCenter
                x: 16
                width: parent.width - 60
                text: root.draftName
                elide: Text.ElideRight
                color: Theme.ink
                font.pixelSize: Theme.s(22)
                font.weight: Font.Light
            }
            LineIcon {
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right
                anchors.rightMargin: 14
                width: 22
                height: 22
                name: "pencil"
                color: Theme.muted
            }
            MouseArea {
                anchors.fill: parent
                onClicked: root.editName()
            }
        }
        Row {
            width: parent.width
            spacing: 12
            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - (resetName.visible ? resetName.width + 12 : 0)
                text: qsTr("In Homebridge: “%1”").arg(root.device.baseName || "")
                color: Theme.muted
                font.pixelSize: Theme.s(13)
                elide: Text.ElideRight
            }
            UnderlineButton {
                id: resetName
                objectName: "resetName"
                visible: root.draftName !== root.device.baseName
                text: qsTr("Original name")
                pixelSize: Theme.s(14)
                onClicked: root.draftName = root.device.baseName
            }
        }

        Text {
            visible: (root.device.kinds || []).length > 0
            topPadding: 4
            text: qsTr("Kind")
            color: Theme.muted
            font.pixelSize: Theme.s(14)
        }
        Flow {
            objectName: "kindChoices"
            visible: (root.device.kinds || []).length > 0
            width: parent.width
            spacing: 10
            Repeater {
                model: root.device.kinds || []
                PillButton {
                    required property var modelData
                    objectName: "kind:" + modelData.value
                    text: modelData.label
                    primary: modelData.value === root.draftKind
                    onClicked: root.draftKind = modelData.value
                }
            }
        }

        Text {
            topPadding: 4
            text: qsTr("Room")
            color: Theme.muted
            font.pixelSize: Theme.s(14)
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
                    primary: modelData.name === root.draftRoom
                    onClicked: root.draftRoom = modelData.name
                }
            }
            PillButton {
                objectName: "newRoomChoice"
                text: qsTr("New room …")
                onClicked: root.newRoom()
            }
        }

        Text {
            width: parent.width
            visible: root.error !== ""
            text: root.error
            color: Theme.err
            font.pixelSize: Theme.s(14)
            wrapMode: Text.WordWrap
        }

        Row {
            anchors.right: parent.right
            spacing: 10
            PillButton {
                text: qsTr("Cancel")
                onClicked: root.close()
            }
            PillButton {
                objectName: "deviceSave"
                primary: true
                text: qsTr("Save")
                onClicked: root.save()
            }
        }
    }
}
