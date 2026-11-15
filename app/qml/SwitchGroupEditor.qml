import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Switch group: several switches or plugs of one room of which only one is on at a time
// (e.g. irrigation circuits, fan levels). edit(null) creates one; edit(device) changes it.
Popup {
    id: root

    property var device: null
    property var keyboard: null
    property string draftName
    property string draftRoom
    property var draftMembers: []
    property bool draftHide: true
    property bool draftAllowOff: true
    property bool draftFavorite
    property string draftArea
    property string error

    readonly property var switches: panel.roomEditor.switches    // read once per change
    readonly property var switchRooms: panel.roomEditor.rooms.filter(r => switches.some(s => s.room === r.name))
    // members first in their order, then the other switches of the room
    readonly property var roomSwitches: {
        const here = switches.filter(s => s.room === draftRoom);
        const chosen = draftMembers.map(id => here.find(s => s.id === id)).filter(s => !!s);
        return chosen.concat(here.filter(s => draftMembers.indexOf(s.id) < 0));
    }
    readonly property var areas: [
        { value: "", label: qsTr("Automatic") }, { value: "light", label: qsTr("Lights") },
        { value: "climate", label: qsTr("Climate") }, { value: "security", label: qsTr("Security") }
    ]

    function edit(d) {
        device = d;
        const g = d ? d.switchGroup : null;
        draftName = g ? g.name : "";
        const here = switchRooms.find(r => r.name === panel.currentRoom);
        draftRoom = g ? g.room : (here || switchRooms[0] || { name: "" }).name;
        draftMembers = g ? g.members.slice() : [];
        draftHide = g ? g.hide !== false : true;
        draftAllowOff = g ? g.allow_off !== false : true;
        draftArea = g ? (g.area || "") : "";
        draftFavorite = d ? !!d.favorite : false;
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
    function move(id, step) {
        const m = draftMembers.slice();
        const i = m.indexOf(id);
        const j = i + step;
        if (i < 0 || j < 0 || j >= m.length)
            return;
        m[i] = m[j];
        m[j] = id;
        draftMembers = m;
    }
    function save() {
        const err = panel.roomEditor.saveSwitchGroup({
            id: device ? device.switchGroup.id : "", name: draftName, room: draftRoom,
            members: draftMembers, hide: draftHide, allowOff: draftAllowOff, area: draftArea,
            favorite: draftFavorite
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
                    text: root.device ? qsTr("Switch group") : qsTr("New switch group")
                    color: Theme.ink
                    font.pixelSize: Theme.s(19)
                    font.weight: Font.Medium
                    Accessible.role: Accessible.Heading
                }
                Text {
                    width: parent.width
                    text: qsTr("Only one switch of the group is on at a time. Tapping the tile switches to the next one.")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                    wrapMode: Text.WordWrap
                }

                Text {
                    text: qsTr("Name")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                }
                Rectangle {
                    objectName: "switchGroupName"
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
                        model: root.switchRooms
                        PillButton {
                            required property var modelData
                            text: modelData.name
                            primary: modelData.name === root.draftRoom
                            onClicked: {
                                if (modelData.name !== root.draftRoom) {
                                    root.draftRoom = modelData.name;
                                    root.draftMembers = [];      // switches of one room only
                                }
                            }
                        }
                    }
                }

                Text {
                    topPadding: 4
                    width: parent.width
                    text: qsTr("Switches in the group, in the order of switching")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                    wrapMode: Text.WordWrap
                }
                Rectangle {
                    objectName: "switchGroupMembers"
                    width: parent.width
                    height: memberColumn.implicitHeight
                    radius: 12
                    color: Theme.page

                    Column {
                        id: memberColumn
                        width: parent.width
                        Text {
                            visible: root.roomSwitches.length === 0
                            padding: 16
                            text: qsTr("No switches or plugs in this room.")
                            color: Theme.muted
                            font.pixelSize: Theme.s(15)
                        }
                        Repeater {
                            model: root.roomSwitches
                            Item {
                                id: member
                                required property var modelData
                                readonly property int position: root.draftMembers.indexOf(modelData.id)
                                readonly property bool checked: position >= 0
                                objectName: "switchMember:" + modelData.id
                                width: memberColumn.width
                                height: Theme.s(52)

                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: root.toggleMember(member.modelData.id)
                                }
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 14
                                    anchors.rightMargin: 6
                                    spacing: 14
                                    Rectangle {
                                        Layout.preferredWidth: 26
                                        Layout.preferredHeight: 26
                                        radius: 7
                                        color: member.checked ? Theme.gold : "transparent"
                                        border.color: member.checked || activeFocus ? Theme.gold : Theme.line
                                        border.width: 2
                                        activeFocusOnTab: true
                                        Accessible.role: Accessible.CheckBox
                                        Accessible.name: member.modelData.name
                                        Accessible.checked: member.checked
                                        Keys.onSpacePressed: root.toggleMember(member.modelData.id)
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
                                    IconButton {
                                        visible: member.checked
                                        iconName: "up"
                                        label: qsTr("Move %1 up").arg(member.modelData.name)
                                        enabled: member.position > 0
                                        onClicked: root.move(member.modelData.id, -1)
                                    }
                                    IconButton {
                                        visible: member.checked
                                        iconName: "down"
                                        label: qsTr("Move %1 down").arg(member.modelData.name)
                                        enabled: member.position < root.draftMembers.length - 1
                                        onClicked: root.move(member.modelData.id, 1)
                                    }
                                }
                            }
                        }
                    }
                }

                ToggleRow {
                    width: parent.width
                    label: qsTr("Allow all off")
                    help: qsTr("Off: always one switch is on; the tile is used like an option switch and is not highlighted")
                    checked: root.draftAllowOff
                    toggleName: "switchGroupAllowOff"
                    onToggled: root.draftAllowOff = !root.draftAllowOff
                }
                ToggleRow {
                    width: parent.width
                    label: qsTr("Hide the single switches")
                    help: qsTr("The home screen then shows only the group")
                    checked: root.draftHide
                    toggleName: "switchGroupHide"
                    onToggled: root.draftHide = !root.draftHide
                }
                ToggleRow {
                    width: parent.width
                    label: qsTr("Favorite")
                    help: qsTr("Shown under Favorites, the start page of the panel")
                    checked: root.draftFavorite
                    toggleName: "switchGroupFavorite"
                    onToggled: root.draftFavorite = !root.draftFavorite
                }

                Text {
                    topPadding: 4
                    text: qsTr("Show under")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                }
                Flow {
                    width: parent.width
                    spacing: 10
                    Repeater {
                        model: root.areas
                        PillButton {
                            required property var modelData
                            text: modelData.label
                            primary: modelData.value === root.draftArea
                            onClicked: root.draftArea = modelData.value
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
                    panel.roomEditor.deleteSwitchGroup(root.device.switchGroup.id);
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
                objectName: "switchGroupSave"
                primary: true
                text: qsTr("Save")
                onClicked: root.save()
            }
        }
    }
}
