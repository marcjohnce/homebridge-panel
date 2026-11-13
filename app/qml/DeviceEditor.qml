import QtQuick
import QtQuick.Controls.Basic

// Edit a device in Settings → Rooms and devices: display name, kind (contact and motion
// sensors: window, door, glass break …), room, outdoor sensor and hidden. Saved with "Save".
Popup {
    id: root

    property var device: ({})
    property var keyboard: null          // TextKeyboard of the page
    property string draftName
    property string draftKind
    property string draftRoom
    property bool draftHidden
    property bool draftOutdoor
    property string error

    function edit(d) {
        device = d;
        draftName = d.name;
        draftKind = d.kind || "";
        draftRoom = d.room;
        draftHidden = !!d.hidden;
        draftOutdoor = !!d.outdoor;
        error = "";
        open();
    }
    function save() {
        const err = panel.roomEditor.saveDevice(device.id, draftName, draftKind, draftRoom, draftHidden, draftOutdoor);
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

        ToggleRow {
            objectName: "outdoorRow"
            visible: !!root.device.canOutdoor
            width: parent.width
            label: qsTr("Outdoor sensor")
            help: qsTr("Counts for the outdoor temperature instead of indoors")
            checked: root.draftOutdoor
            toggleName: "outdoorToggle"
            onToggled: root.draftOutdoor = !root.draftOutdoor
        }
        ToggleRow {
            width: parent.width
            label: qsTr("Hide on the home screen")
            help: qsTr("Hidden devices are only listed here, also not under “All”")
            checked: root.draftHidden
            toggleName: "hiddenToggle"
            onToggled: root.draftHidden = !root.draftHidden
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

    // label and help on the left, switch on the right
    component ToggleRow: Item {
        id: row
        property string label
        property string help
        property bool checked
        property string toggleName
        signal toggled

        height: Math.max(Theme.s(52), texts.implicitHeight + 8)

        Column {
            id: texts
            anchors.left: parent.left
            anchors.right: toggle.left
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2
            Text {
                width: parent.width
                text: row.label
                color: Theme.ink
                font.pixelSize: Theme.s(16)
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                text: row.help
                color: Theme.muted
                font.pixelSize: Theme.s(13)
                wrapMode: Text.WordWrap
            }
        }
        Rectangle {
            id: toggle
            objectName: row.toggleName
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            width: Theme.s(54)
            height: Theme.s(32)
            radius: height / 2
            color: row.checked ? Theme.gold : Theme.line
            border.color: activeFocus ? Theme.ink : "transparent"
            border.width: 2
            activeFocusOnTab: true
            Accessible.role: Accessible.CheckBox
            Accessible.name: row.label
            Accessible.checked: row.checked
            Keys.onSpacePressed: row.toggled()

            Behavior on color { ColorAnimation { duration: 150 } }

            Rectangle {
                width: parent.height - 6
                height: parent.height - 6
                radius: height / 2
                y: 3
                x: row.checked ? parent.width - width - 3 : 3
                color: Theme.knob
                Behavior on x { NumberAnimation { duration: 150 } }
            }
            MouseArea {
                anchors.fill: parent
                anchors.margins: -8
                onClicked: row.toggled()
            }
        }
    }
}
