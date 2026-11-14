import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Light group: several lights of one room shown and switched as one tile.
// edit(null) creates one; edit(device) changes it.
Popup {
    id: root

    property var device: null
    property var keyboard: null
    property string draftName
    property string draftRoom
    property var draftMembers: []
    property bool draftHide: true
    property string error

    readonly property var roomLights: panel.roomEditor.lights.filter(l => l.room === draftRoom)
    readonly property var lightRooms: panel.roomEditor.rooms.filter(r => panel.roomEditor.lights.some(l => l.room === r.name))

    function edit(d) {
        device = d;
        const g = d ? d.group : null;
        draftName = g ? g.name : "";
        const here = lightRooms.find(r => r.name === panel.currentRoom);
        draftRoom = g ? g.room : (here || lightRooms[0] || { name: "" }).name;
        draftMembers = g ? g.members.slice() : [];
        draftHide = g ? g.hide : true;
        error = "";
        open();
    }
    function editName() {
        keyboard.edit(qsTr("Name"), draftName, text => {
            root.draftName = text.trim();
            return "";
        }, { maxLength: 40 });
    }
    function toggleMember(id) {
        const m = draftMembers.slice();
        const i = m.indexOf(id);
        if (i >= 0)
            m.splice(i, 1);
        else
            m.push(id);
        draftMembers = m;
    }
    function save() {
        const err = panel.roomEditor.saveGroup({
            id: device ? device.group.id : "", name: draftName, room: draftRoom,
            members: draftMembers, hide: draftHide
        });
        if (err !== "")
            error = err;
        else
            close();
    }

    anchors.centerIn: Overlay.overlay
    width: Math.min(parent ? parent.width - 40 : Theme.s(640), Theme.s(640))
    height: Math.min(implicitHeight, parent ? parent.height - 40 : implicitHeight)
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

    contentItem: ColumnLayout {
        spacing: Theme.s(12)

        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            implicitHeight: form.implicitHeight
            contentHeight: form.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            Column {
                id: form
                width: parent.width
                spacing: Theme.s(12)

                Text {
                    text: root.device ? qsTr("Light group") : qsTr("New light group")
                    color: Theme.ink
                    font.pixelSize: Theme.s(19)
                    font.weight: Font.Medium
                    Accessible.role: Accessible.Heading
                }

                Text {
                    text: qsTr("Name")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                }
                Rectangle {
                    objectName: "groupName"
                    width: parent.width
                    height: Theme.s(50)
                    radius: 10
                    color: Theme.page
                    border.color: activeFocus ? Theme.gold : Theme.line
                    border.width: activeFocus ? 2 : 1
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: qsTr("Change %1, currently %2").arg(qsTr("Name")).arg(root.draftName)
                    Keys.onReturnPressed: root.editName()

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        x: 14
                        width: parent.width - 52
                        text: root.draftName
                        elide: Text.ElideRight
                        color: Theme.ink
                        font.pixelSize: Theme.s(19)
                        font.weight: Font.Light
                    }
                    LineIcon {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        width: 20
                        height: 20
                        name: "pencil"
                        color: Theme.muted
                    }
                    MouseArea {
                        id: nameMouse
                        anchors.fill: parent
                        onClicked: root.editName()
                    }
                }

                Text {
                    topPadding: 4
                    text: qsTr("Room")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                }
                Flow {
                    width: parent.width
                    spacing: 10
                    Repeater {
                        model: root.lightRooms
                        PillButton {
                            required property var modelData
                            text: modelData.name
                            primary: modelData.name === root.draftRoom
                            onClicked: {
                                if (modelData.name !== root.draftRoom) {
                                    root.draftRoom = modelData.name;
                                    root.draftMembers = [];      // lights of one room only
                                }
                            }
                        }
                    }
                }

                Text {
                    topPadding: 4
                    text: qsTr("Lights in the group")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                }
                Rectangle {
                    objectName: "groupMembers"
                    width: parent.width
                    height: memberColumn.implicitHeight
                    radius: 12
                    color: Theme.page

                    Column {
                        id: memberColumn
                        width: parent.width
                        Text {
                            visible: root.roomLights.length === 0
                            padding: 16
                            text: qsTr("No lights in this room.")
                            color: Theme.muted
                            font.pixelSize: Theme.s(15)
                        }
                        Repeater {
                            model: root.roomLights
                            Item {
                                id: member
                                required property var modelData
                                readonly property bool checked: root.draftMembers.indexOf(modelData.id) >= 0
                                objectName: "member:" + modelData.id
                                width: memberColumn.width
                                height: Theme.s(52)
                                activeFocusOnTab: true
                                Accessible.role: Accessible.CheckBox
                                Accessible.name: modelData.name
                                Accessible.checked: checked
                                Keys.onSpacePressed: root.toggleMember(modelData.id)

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 14
                                    anchors.rightMargin: 14
                                    spacing: 14
                                    Rectangle {
                                        Layout.preferredWidth: 26
                                        Layout.preferredHeight: 26
                                        radius: 7
                                        color: member.checked ? Theme.gold : "transparent"
                                        border.color: member.checked || member.activeFocus ? Theme.gold : Theme.line
                                        border.width: 2
                                        LineIcon {
                                            anchors.centerIn: parent
                                            visible: member.checked
                                            width: 18
                                            height: 18
                                            lineWidth: 2
                                            name: "check"
                                            color: Theme.goldInk
                                        }
                                    }
                                    LineIcon {
                                        Layout.preferredWidth: Theme.s(22)
                                        Layout.preferredHeight: Theme.s(22)
                                        name: member.modelData.icon
                                        color: Theme.ink
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: member.modelData.name
                                        color: Theme.ink
                                        font.pixelSize: Theme.s(16)
                                        elide: Text.ElideRight
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: root.toggleMember(member.modelData.id)
                                }
                            }
                        }
                    }
                }

                Item {
                    width: parent.width
                    height: Math.max(Theme.s(52), hideText.implicitHeight + 8)
                    Column {
                        id: hideText
                        anchors.left: parent.left
                        anchors.right: hideToggle.left
                        anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2
                        Text {
                            width: parent.width
                            text: qsTr("Hide the single lights")
                            color: Theme.ink
                            font.pixelSize: Theme.s(16)
                            wrapMode: Text.WordWrap
                        }
                        Text {
                            width: parent.width
                            text: qsTr("The home screen then shows only the group")
                            color: Theme.muted
                            font.pixelSize: Theme.s(13)
                            wrapMode: Text.WordWrap
                        }
                    }
                    Rectangle {
                        id: hideToggle
                        objectName: "groupHideToggle"
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        width: Theme.s(54)
                        height: Theme.s(32)
                        radius: height / 2
                        color: root.draftHide ? Theme.gold : Theme.line
                        activeFocusOnTab: true
                        Accessible.role: Accessible.CheckBox
                        Accessible.name: qsTr("Hide the single lights")
                        Accessible.checked: root.draftHide
                        Keys.onSpacePressed: root.draftHide = !root.draftHide
                        Rectangle {
                            width: parent.height - 6
                            height: parent.height - 6
                            radius: height / 2
                            y: 3
                            x: root.draftHide ? parent.width - width - 3 : 3
                            color: Theme.knob
                            Behavior on x { NumberAnimation { duration: 150 } }
                        }
                        MouseArea {
                            anchors.fill: parent
                            anchors.margins: -8
                            onClicked: root.draftHide = !root.draftHide
                        }
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
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            PillButton {
                visible: !!root.device
                text: qsTr("Delete")
                onClicked: {
                    panel.roomEditor.deleteGroup(root.device.group.id);
                    root.close();
                }
            }
            Item {
                Layout.fillWidth: true
            }
            PillButton {
                text: qsTr("Cancel")
                onClicked: root.close()
            }
            PillButton {
                objectName: "groupSave"
                primary: true
                text: qsTr("Save")
                onClicked: root.save()
            }
        }
    }
}
