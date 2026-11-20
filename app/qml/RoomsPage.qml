import QtQuick
import QtQuick.Layouts

// Settings → Rooms and devices. Rooms can be added, renamed, reordered and deleted;
// devices get a display name, a room and (security sensors) a kind. Every change is saved and
// shown on the home screen at once – except moving rows up and down: the rows only change places
// here, the new order is saved when the page or the tab is left (editor.finishMoves).
Rectangle {
    id: root

    property int tab: 0                // 0 rooms, 1 devices
    property string moved              // last moved row ("device:<id>", "favorite:<id>"), highlighted
    property string message
    signal closed

    readonly property var editor: panel.roomEditor
    readonly property var rooms: editor.rooms
    // read once per change: every access from QML converts the whole list
    readonly property var devices: editor.devices
    readonly property var favorites: editor.favorites
    // groups of the Devices tab: favorites first (their order is the order on the start page),
    // then the rooms; only while the tab is shown
    readonly property string favoritesKey: "\u0001favorites"     // not a room name
    readonly property var groupKeys: tab !== 1 ? []
        : (favorites.length > 0 ? [favoritesKey] : []).concat(filledRooms.map(r => r.name))
    onGroupKeysChanged: fill(groupModel, groupKeys)
    readonly property var filledRooms: rooms.filter(r => r.count > 0)
    readonly property string defaultRoom: {
        const r = rooms.find(r => r.isDefault);
        return r ? r.name : "";
    }

    // The lists hold only keys (ListModel): moving a row up or down moves its delegate, nothing
    // is built again – also on a Raspberry Pi with many devices. The data come from these maps.
    readonly property var roomByName: {
        const out = {};
        for (const r of rooms)
            out[r.name] = r;
        return out;
    }
    readonly property var deviceById: {
        const out = {};
        for (const d of devices.concat(favorites))
            out[d.id] = d;
        return out;
    }
    // fills a ListModel with the keys of a list after the lists changed in the editor – only if
    // they differ from the rows shown: a device update must not rebuild the list (and lose the
    // scroll position) while rows are being moved; the rows read their data from the maps above
    function fill(model, keys) {
        if (model.count === keys.length && keys.every((k, i) => model.get(i).key === k))
            return;
        model.clear();
        for (const key of keys)
            model.append({ key: key });
    }
    // moves the row at `index` of a ListModel by one place; false at either end
    function shift(model, index, delta) {
        const to = index + delta;
        if (index < 0 || to < 0 || to >= model.count)
            return false;
        model.move(index, to, 1);
        return true;
    }
    function moveRoom(name, index, delta, rowHeight) {
        if (!shift(roomModel, index, delta))
            return;
        keepInPlace("room:" + name, delta, rowHeight);
        editor.moveRoom(name, delta);
    }

    ListModel {
        id: roomModel
    }
    ListModel {
        id: groupModel
    }
    onRoomsChanged: fill(roomModel, rooms.map(r => r.name))
    Component.onCompleted: fill(roomModel, rooms.map(r => r.name))
    Component.onDestruction: if (panel) panel.roomEditor.finishMoves()

    function countText(n) {
        return n === 0 ? qsTr("No devices") : n === 1 ? qsTr("1 device") : qsTr("%1 devices").arg(n);
    }
    function addRoom() {
        keyboard.edit(qsTr("New room"), "", text => root.editor.addRoom(text));
    }
    function openDevice(d) {
        if (d.panelTile)
            return;                 // the Wi-Fi tile: set up under Settings → Wi-Fi for guests
        if (d.virtual)
            virtualEditor.edit(d);
        else if (d.group)
            groupEditor.edit(d);
        else if (d.switchGroup)
            switchGroupEditor.edit(d);
        else
            deviceEditor.edit(d);
    }
    // After moving a row up or down the list scrolls by one row, so the moved row stays under the
    // finger and tapping again moves the same room or device further (not its new neighbour).
    // At the top or bottom end the list may scroll past its edge for this; it returns when the
    // list is scrolled by hand or the tab changes.
    function keepInPlace(key, delta, rowHeight) {
        moved = key;
        const y = flick.contentY + delta * rowHeight;
        flick.topMargin = Math.max(flick.topMargin, -y);
        flick.bottomMargin = Math.max(flick.bottomMargin, y - Math.max(0, flick.contentHeight - flick.height));
        flick.contentY = y;
    }
    function settleList() {
        if (flick.topMargin === 0 && flick.bottomMargin === 0)
            return;
        const y = Math.max(0, Math.min(flick.contentY, Math.max(0, flick.contentHeight - flick.height)));
        flick.topMargin = 0;
        flick.bottomMargin = 0;
        flick.contentY = y;
    }
    function renameRoom(room) {
        keyboard.edit(qsTr("Rename room"), room.name, text => root.editor.renameRoom(room.name, text));
    }

    onTabChanged: {
        editor.finishMoves();       // the other tab shows the new order
        moved = "";
        settleList();
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
                onClicked: if (root.tab !== 1) Busy.run(qsTr("Loading devices …"), () => root.tab = 1)
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
            onMovementEnded: root.settleList()
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
                            model: roomModel
                            Column {
                                id: roomItem
                                required property string key
                                required property int index          // place as shown, follows moves
                                readonly property var modelData: root.roomByName[key] || ({ name: key, count: 0 })
                                width: roomRows.width

                                Rectangle {
                                    visible: roomItem.index > 0
                                    width: parent.width - 36
                                    x: 18
                                    height: 1
                                    color: Theme.line
                                }
                                RowLayout {
                                    id: roomRow
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
                                        objectName: "roomUp:" + roomItem.key
                                        iconName: "up"
                                        label: qsTr("Move %1 up").arg(roomItem.modelData.name)
                                        enabled: roomItem.index > 0
                                        onClicked: root.moveRoom(roomItem.key, roomItem.index, -1, roomRow.height + 1)
                                    }
                                    IconButton {
                                        objectName: "roomDown:" + roomItem.key
                                        iconName: "down"
                                        label: qsTr("Move %1 down").arg(roomItem.modelData.name)
                                        enabled: roomItem.index < roomModel.count - 1
                                        onClicked: root.moveRoom(roomItem.key, roomItem.index, 1, roomRow.height + 1)
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
                    text: root.devices.length > 0 ? qsTr("Tap a device to change its name, kind or room or to make it a favorite.")
                        : qsTr("No devices yet. Devices appear here once the panel is connected to Homebridge.")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                    wrapMode: Text.WordWrap
                }

                Flow {
                    Layout.fillWidth: true
                    spacing: 10
                    PillButton {
                        objectName: "addVirtual"
                        iconName: "plus"
                        text: qsTr("Virtual device (MQTT)")
                        onClicked: virtualEditor.edit(null)
                    }
                    PillButton {
                        objectName: "addGroup"
                        iconName: "plus"
                        text: qsTr("Light group")
                        onClicked: groupEditor.edit(null)
                    }
                    PillButton {
                        objectName: "addSwitchGroup"
                        iconName: "plus"
                        text: qsTr("Switch group")
                        onClicked: switchGroupEditor.edit(null)
                    }
                }

                Repeater {
                    model: groupModel
                    ColumnLayout {
                        id: group
                        required property string key
                        readonly property bool favorites: key === root.favoritesKey
                        readonly property var modelData: ({ name: favorites ? qsTr("Favorites") : key })
                        readonly property var members: favorites ? root.favorites
                            : root.devices.filter(d => d.room === modelData.name)
                        onMembersChanged: root.fill(memberModel, members.map(d => d.id))
                        Component.onCompleted: root.fill(memberModel, members.map(d => d.id))
                        function move(id, index, delta) {
                            if (!root.shift(memberModel, index, delta))
                                return;
                            root.keepInPlace((favorites ? "favorite:" : "device:") + id, delta, Theme.s(60) + 1);
                            if (favorites)
                                root.editor.moveFavorite(id, delta);
                            else
                                root.editor.moveDevice(id, delta);
                        }
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
                                ListModel {
                                    id: memberModel
                                }
                                Repeater {
                                    model: memberModel
                                    Column {
                                        id: devItem
                                        required property string key
                                        required property int index          // place as shown, follows moves
                                        readonly property var modelData: root.deviceById[key] || ({ id: key, name: "", icon: "", room: "" })
                                        width: memberRows.width

                                        Rectangle {
                                            visible: devItem.index > 0
                                            width: parent.width - 36
                                            x: 18
                                            height: 1
                                            color: Theme.line
                                        }
                                        Item {
                                            id: devRow
                                            objectName: (group.favorites ? "favorite:" : "device:") + devItem.modelData.id
                                            width: parent.width
                                            height: Theme.s(60)
                                            activeFocusOnTab: true
                                            Accessible.role: Accessible.Button
                                            Accessible.name: qsTr("Edit %1").arg(devItem.modelData.name)
                                            Keys.onReturnPressed: root.openDevice(devItem.modelData)

                                            MouseArea {
                                                id: devMouse
                                                anchors.fill: parent
                                                onClicked: root.openDevice(devItem.modelData)
                                            }
                                            Rectangle {
                                                anchors.fill: parent
                                                radius: 14
                                                color: devMouse.pressed ? Theme.tilePress
                                                     : root.moved === devRow.objectName ? Theme.goldSoft : "transparent"
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
                                                    objectName: (group.favorites ? "favoriteLabel:" : "hiddenLabel:") + devItem.modelData.id
                                                    visible: group.favorites || devItem.modelData.hidden || devItem.modelData.grouped || devItem.modelData.quiet
                                                    text: group.favorites ? devItem.modelData.room
                                                        : devItem.modelData.hidden ? qsTr("Hidden")
                                                        : devItem.modelData.grouped ? qsTr("In a group") : qsTr("No alerts")
                                                    color: Theme.muted
                                                    font.pixelSize: Theme.s(14)
                                                }
                                                IconButton {
                                                    objectName: (group.favorites ? "favoriteUp:" : "deviceUp:") + devItem.modelData.id
                                                    iconName: "up"
                                                    label: qsTr("Move %1 up").arg(devItem.modelData.name)
                                                    enabled: devItem.index > 0
                                                    onClicked: group.move(devItem.key, devItem.index, -1)
                                                }
                                                IconButton {
                                                    objectName: (group.favorites ? "favoriteDown:" : "deviceDown:") + devItem.modelData.id
                                                    iconName: "down"
                                                    label: qsTr("Move %1 down").arg(devItem.modelData.name)
                                                    enabled: devItem.index < memberModel.count - 1
                                                    onClicked: group.move(devItem.key, devItem.index, 1)
                                                }
                                                LineIcon {
                                                    Layout.preferredWidth: 20
                                                    Layout.preferredHeight: 20
                                                    opacity: devItem.modelData.panelTile ? 0 : 1
                                                    name: "chevron"
                                                    color: Theme.muted
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

    VirtualDeviceEditor {
        id: virtualEditor
        objectName: "virtualEditor"
        keyboard: keyboard
    }

    LightGroupEditor {
        id: groupEditor
        objectName: "groupEditor"
        keyboard: keyboard
    }

    SwitchGroupEditor {
        id: switchGroupEditor
        objectName: "switchGroupEditor"
        keyboard: keyboard
    }

    ConfirmDialog {
        id: confirm
        objectName: "roomConfirm"
        onConfirmed: name => Busy.run(qsTr("Saving …"), () => root.message = root.editor.deleteRoom(name))
    }
}
