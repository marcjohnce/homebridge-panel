import QtQuick
import QtQuick.Layouts

// Settings → Rooms and devices. Rooms can be added, renamed, reordered and deleted;
// devices get a display name, a room and (security sensors) a kind. Every change is saved and shown on the home screen at once.
Rectangle {
    id: root

    property int tab: 0                // 0 rooms, 1 devices
    property string message
    signal closed

    readonly property var editor: panel.roomEditor
    readonly property var rooms: editor.rooms
    readonly property var filledRooms: rooms.filter(r => r.count > 0)
    readonly property string defaultRoom: {
        const r = rooms.find(r => r.isDefault);
        return r ? r.name : "";
    }

    function countText(n) {
        return n === 0 ? qsTr("No devices") : n === 1 ? qsTr("1 device") : qsTr("%1 devices").arg(n);
    }
    function addRoom() {
        keyboard.hint = "";
        keyboard.maxLength = 24;
        keyboard.edit(qsTr("New room"), "", text => root.editor.addRoom(text));
    }
    function renameRoom(room) {
        keyboard.hint = "";
        keyboard.maxLength = 24;
        keyboard.edit(qsTr("Rename room"), room.name, text => root.editor.renameRoom(room.name, text));
    }

    color: Theme.page
    focus: true
    Keys.onEscapePressed: root.closed()

    MouseArea {
        anchors.fill: parent
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 28
        anchors.rightMargin: 28
        anchors.topMargin: 18
        spacing: 4

        BackHeader {
            Layout.fillWidth: true
            backText: qsTr("Settings")
            title: qsTr("Rooms and devices")
            onBack: root.closed()
        }

        Row {
            Layout.fillWidth: true
            Layout.maximumWidth: Theme.s(760)
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 6
            spacing: 32
            UnderlineButton {
                objectName: "tab:rooms"
                text: qsTr("Rooms")
                selected: root.tab === 0
                onClicked: root.tab = 0
            }
            UnderlineButton {
                objectName: "tab:devices"
                text: qsTr("Devices")
                selected: root.tab === 1
                onClicked: root.tab = 1
            }
        }

        Flickable {
            id: flick
            objectName: "roomsFlick"
            layer.enabled: GraphicsInfo.api === GraphicsInfo.Software   // see TileGrid.qml

            Rectangle {
                parent: flick
                anchors.fill: parent
                z: -1
                visible: flick.layer.enabled
                color: Theme.page
            }

            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: (root.tab === 0 ? roomsColumn : devicesColumn).implicitHeight + 24
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            // ---------- rooms ----------
            ColumnLayout {
                id: roomsColumn
                visible: root.tab === 0
                width: Math.min(parent.width, Theme.s(760))
                x: (parent.width - width) / 2
                spacing: 12

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 10
                    Layout.leftMargin: 4
                    text: root.message !== "" ? root.message
                        : qsTr("The order here is the order of the rooms on the home screen.")
                    color: root.message !== "" ? Theme.err : Theme.muted
                    font.pixelSize: Theme.s(14)
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    objectName: "roomList"
                    Layout.fillWidth: true
                    Layout.preferredHeight: roomRows.implicitHeight
                    radius: 14
                    color: Theme.tile

                    Column {
                        id: roomRows
                        width: parent.width
                        Repeater {
                            model: root.rooms
                            Column {
                                id: roomItem
                                required property var modelData
                                required property int index
                                width: roomRows.width

                                Rectangle {
                                    visible: roomItem.index > 0
                                    width: parent.width - 36
                                    x: 18
                                    height: 1
                                    color: Theme.line
                                }
                                RowLayout {
                                    objectName: "room:" + roomItem.modelData.name
                                    width: parent.width
                                    height: Math.max(Theme.s(68), roomText.implicitHeight + 20)
                                    spacing: 4

                                    ColumnLayout {
                                        id: roomText
                                        Layout.fillWidth: true
                                        Layout.leftMargin: 18
                                        spacing: 2
                                        Text {
                                            Layout.fillWidth: true
                                            text: roomItem.modelData.name
                                            color: Theme.ink
                                            font.pixelSize: Theme.s(17)
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: roomItem.modelData.isDefault
                                                ? qsTr("%1 – new devices appear here").arg(root.countText(roomItem.modelData.count))
                                                : root.countText(roomItem.modelData.count)
                                            color: Theme.muted
                                            font.pixelSize: Theme.s(13)
                                            wrapMode: Text.WordWrap
                                        }
                                    }
                                    IconButton {
                                        iconName: "up"
                                        label: qsTr("Move %1 up").arg(roomItem.modelData.name)
                                        enabled: roomItem.index > 0
                                        onClicked: root.editor.moveRoom(roomItem.modelData.name, -1)
                                    }
                                    IconButton {
                                        iconName: "down"
                                        label: qsTr("Move %1 down").arg(roomItem.modelData.name)
                                        enabled: roomItem.index < root.rooms.length - 1
                                        onClicked: root.editor.moveRoom(roomItem.modelData.name, 1)
                                    }
                                    IconButton {
                                        objectName: "rename:" + roomItem.modelData.name
                                        iconName: "pencil"
                                        label: qsTr("Rename %1").arg(roomItem.modelData.name)
                                        onClicked: root.renameRoom(roomItem.modelData)
                                    }
                                    IconButton {
                                        objectName: "delete:" + roomItem.modelData.name
                                        Layout.rightMargin: 8
                                        iconName: "trash"
                                        label: qsTr("Delete %1").arg(roomItem.modelData.name)
                                        onClicked: {
                                            root.message = "";
                                            confirm.ask({
                                                key: roomItem.modelData.name,
                                                label: qsTr("Delete room"),
                                                button: qsTr("Delete"),
                                                confirm: roomItem.modelData.count > 0
                                                    ? qsTr("Delete \"%1\"? Its devices move to \"%2\".").arg(roomItem.modelData.name).arg(root.defaultRoom)
                                                    : qsTr("Delete \"%1\"?").arg(roomItem.modelData.name)
                                            });
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                PillButton {
                    objectName: "addRoom"
                    text: qsTr("Add room")
                    onClicked: root.addRoom()
                }
            }

            // ---------- devices, grouped by room ----------
            ColumnLayout {
                id: devicesColumn
                visible: root.tab === 1
                width: Math.min(parent.width, Theme.s(760))
                x: (parent.width - width) / 2
                spacing: 10

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: 10
                    Layout.leftMargin: 4
                    text: root.editor.devices.length > 0 ? qsTr("Tap a device to change its name, kind or room.")
                        : qsTr("No devices yet. Devices appear here once the panel is connected to Homebridge.")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                    wrapMode: Text.WordWrap
                }

                Repeater {
                    model: root.filledRooms
                    ColumnLayout {
                        id: group
                        required property var modelData
                        readonly property var members: root.editor.devices.filter(d => d.room === modelData.name)
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            Layout.leftMargin: 4
                            Layout.topMargin: 8
                            text: group.modelData.name
                            color: Theme.muted
                            font.pixelSize: Theme.s(15)
                            Accessible.role: Accessible.Heading
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: memberRows.implicitHeight
                            radius: 14
                            color: Theme.tile

                            Column {
                                id: memberRows
                                width: parent.width
                                Repeater {
                                    model: group.members
                                    Column {
                                        id: devItem
                                        required property var modelData
                                        required property int index
                                        width: memberRows.width

                                        Rectangle {
                                            visible: devItem.index > 0
                                            width: parent.width - 36
                                            x: 18
                                            height: 1
                                            color: Theme.line
                                        }
                                        Item {
                                            objectName: "device:" + devItem.modelData.id
                                            width: parent.width
                                            height: Theme.s(60)
                                            activeFocusOnTab: true
                                            Accessible.role: Accessible.Button
                                            Accessible.name: qsTr("Edit %1").arg(devItem.modelData.name)
                                            Keys.onReturnPressed: deviceEditor.edit(devItem.modelData)

                                            Rectangle {
                                                anchors.fill: parent
                                                radius: 14
                                                color: devMouse.pressed ? Theme.tilePress : "transparent"
                                                border.color: Theme.gold
                                                border.width: parent.activeFocus ? 2 : 0
                                            }
                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.leftMargin: 18
                                                anchors.rightMargin: 14
                                                spacing: 14
                                                LineIcon {
                                                    Layout.preferredWidth: Theme.s(24)
                                                    Layout.preferredHeight: Theme.s(24)
                                                    name: devItem.modelData.icon
                                                    color: devItem.modelData.reachable && !devItem.modelData.hidden ? Theme.ink : Theme.muted
                                                }
                                                Text {
                                                    Layout.fillWidth: true
                                                    text: devItem.modelData.name
                                                    color: devItem.modelData.reachable && !devItem.modelData.hidden ? Theme.ink : Theme.muted
                                                    font.pixelSize: Theme.s(16)
                                                    elide: Text.ElideRight
                                                }
                                                Text {
                                                    objectName: "hiddenLabel:" + devItem.modelData.id
                                                    visible: devItem.modelData.hidden
                                                    text: qsTr("Hidden")
                                                    color: Theme.muted
                                                    font.pixelSize: Theme.s(14)
                                                }
                                                LineIcon {
                                                    Layout.preferredWidth: 20
                                                    Layout.preferredHeight: 20
                                                    name: "chevron"
                                                    color: Theme.muted
                                                }
                                            }
                                            MouseArea {
                                                id: devMouse
                                                anchors.fill: parent
                                                onClicked: deviceEditor.edit(devItem.modelData)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    TextKeyboard {
        id: keyboard
        objectName: "textKeyboard"
    }

    DeviceEditor {
        id: deviceEditor
        objectName: "deviceEditor"
        keyboard: keyboard
    }

    ConfirmDialog {
        id: confirm
        objectName: "roomConfirm"
        onConfirmed: name => root.message = root.editor.deleteRoom(name)
    }
}
