import QtQuick
import QtQuick.Layouts

// Scene editor (full screen): name, and for each light, switch and blind of the room the state
// the scene sets. Unchecked devices are left as they are. Tapping a device opens its detail view
// to change it; its new state is taken over when it comes back. draft: panel.sceneDraft(id).
Rectangle {
    id: root
    objectName: "sceneEditor"

    property var draft: ({ id: "", name: "", room: "", devices: [] })
    property bool detailOpen: false     // the detail view of a device is shown on top
    signal openDevice(string id)
    signal closed

    property string draftName: draft.name
    property bool draftFavorite: !!draft.favorite
    property var rows: draft.devices
    property string adjusting           // device changed in its detail view
    property string error
    readonly property bool isNew: draft.id === ""
    readonly property int includedCount: rows.filter(r => r.included).length

    color: Theme.page
    focus: true
    Keys.onEscapePressed: root.closed()

    Component.onCompleted: if (isNew) Qt.callLater(editName)

    function editName() {
        keyboard.edit(qsTr("Name of the scene"), draftName, text => {
            root.draftName = text.trim();
            root.error = "";
            return "";
        });
    }
    function setRow(i, changes) {
        const r = rows.slice();
        r[i] = Object.assign({}, r[i], changes);
        rows = r;
    }
    function capture(i) {
        const c = panel.sceneCapture(rows[i].id);
        if (c.attrs !== undefined)
            setRow(i, { attrs: c.attrs, stateText: c.stateText });
    }
    function captureAll() {
        for (let i = 0; i < rows.length; i++)
            capture(i);
    }
    function adjust(i) {
        adjusting = rows[i].id;
        setRow(i, { included: true });
        root.openDevice(rows[i].id);
    }
    function save() {
        Busy.run(qsTr("Saving …"), () => {
            const devices = {};
            for (const r of rows) {
                if (r.included)
                    devices[r.id] = r.attrs;
            }
            const err = panel.saveScene(draft.id, draftName, draft.room, devices, draftFavorite);
            if (err !== "")
                error = err;
            else
                root.closed();
        });
    }

    // the device was changed in its detail view: the scene takes its new state
    onDetailOpenChanged: if (!detailOpen && adjusting !== "") recaptureAdjusted()
    function recaptureAdjusted() {
        const i = rows.findIndex(r => r.id === adjusting);
        if (i >= 0)
            capture(i);
    }
    Connections {
        target: panel
        function onDeviceUpdated(id) {
            if (id === root.adjusting)
                root.recaptureAdjusted();
        }
    }

    MouseArea {
        anchors.fill: parent
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 28
        anchors.rightMargin: 28
        anchors.topMargin: 18
        anchors.bottomMargin: 18
        spacing: Theme.s(12)

        BackHeader {
            Layout.fillWidth: true
            backText: qsTr("Scenes")
            title: root.isNew ? qsTr("New scene") : root.draft.name
            note: root.draft.room
            onBack: root.closed()
        }

        Flickable {
            id: flick
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: form.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: true
            layer.enabled: GraphicsInfo.api === GraphicsInfo.Software   // see TileGrid.qml

            Rectangle {
                parent: flick
                anchors.fill: parent
                z: -1
                visible: flick.layer.enabled
                color: Theme.page
            }

            Column {
                id: form
                width: parent.width
                spacing: Theme.s(12)

                Text {
                    text: qsTr("Name")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                }
                Rectangle {
                    objectName: "sceneName"
                    width: parent.width
                    height: Theme.s(50)
                    radius: 10
                    color: Theme.tile
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
                    width: parent.width
                    text: qsTr("Checked devices are set to the state shown, the others stay as they are. Tap a device to change its state.")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                    wrapMode: Text.WordWrap
                }
                Rectangle {
                    objectName: "sceneDevices"
                    width: parent.width
                    height: deviceColumn.implicitHeight
                    radius: 12
                    color: Theme.tile

                    Column {
                        id: deviceColumn
                        width: parent.width
                        Text {
                            visible: root.rows.length === 0
                            padding: 16
                            text: qsTr("No lights, switches or blinds in this room.")
                            color: Theme.muted
                            font.pixelSize: Theme.s(15)
                        }
                        Repeater {
                            model: root.rows
                            Item {
                                id: row
                                required property var modelData
                                required property int index
                                objectName: "sceneDevice:" + modelData.id
                                width: deviceColumn.width
                                height: Theme.s(58)

                                Item {
                                    id: check
                                    objectName: "sceneCheck:" + row.modelData.id
                                    width: Theme.s(58)
                                    height: parent.height
                                    activeFocusOnTab: true
                                    Accessible.role: Accessible.CheckBox
                                    Accessible.name: qsTr("%1 in the scene").arg(row.modelData.name)
                                    Accessible.checked: row.modelData.included
                                    Keys.onSpacePressed: root.setRow(row.index, { included: !row.modelData.included })

                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 26
                                        height: 26
                                        radius: 7
                                        color: row.modelData.included ? Theme.gold : "transparent"
                                        border.color: row.modelData.included || check.activeFocus ? Theme.gold : Theme.line
                                        border.width: 2
                                        LineIcon {
                                            anchors.centerIn: parent
                                            visible: row.modelData.included
                                            width: 18
                                            height: 18
                                            lineWidth: 2
                                            name: "check"
                                            color: Theme.goldInk
                                        }
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: root.setRow(row.index, { included: !row.modelData.included })
                                    }
                                }

                                Item {
                                    id: body
                                    objectName: "sceneAdjust:" + row.modelData.id
                                    anchors.left: check.right
                                    anchors.right: parent.right
                                    height: parent.height
                                    activeFocusOnTab: true
                                    Accessible.role: Accessible.Button
                                    Accessible.name: qsTr("%1: %2").arg(row.modelData.name).arg(stateLabel.text)
                                    Keys.onReturnPressed: root.adjust(row.index)

                                    Rectangle {
                                        anchors.fill: parent
                                        color: bodyMouse.pressed ? Theme.tilePress : "transparent"
                                        border.color: Theme.gold
                                        border.width: body.activeFocus ? 2 : 0
                                        radius: 8
                                    }
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.rightMargin: 14
                                        spacing: 14
                                        LineIcon {
                                            Layout.preferredWidth: Theme.s(22)
                                            Layout.preferredHeight: Theme.s(22)
                                            name: row.modelData.icon
                                            color: row.modelData.included ? Theme.ink : Theme.muted
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: row.modelData.name
                                            color: row.modelData.included ? Theme.ink : Theme.muted
                                            font.pixelSize: Theme.s(16)
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            id: stateLabel
                                            text: row.modelData.included ? row.modelData.stateText : qsTr("Not changed")
                                            color: Theme.muted
                                            font.pixelSize: Theme.s(15)
                                            font.italic: !row.modelData.included
                                        }
                                        LineIcon {
                                            Layout.preferredWidth: 18
                                            Layout.preferredHeight: 18
                                            name: "chevron"
                                            color: Theme.muted
                                        }
                                    }
                                    MouseArea {
                                        id: bodyMouse
                                        anchors.fill: parent
                                        onClicked: root.adjust(row.index)
                                    }
                                }

                                Rectangle {
                                    visible: row.index > 0
                                    anchors.top: parent.top
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.leftMargin: 14
                                    anchors.rightMargin: 14
                                    height: 1
                                    color: Theme.line
                                }
                            }
                        }
                    }
                }

                ToggleRow {
                    width: parent.width
                    label: qsTr("Favorite")
                    help: qsTr("Shown under Favorites, the start page of the panel")
                    checked: root.draftFavorite
                    toggleName: "sceneFavorite"
                    onToggled: root.draftFavorite = !root.draftFavorite
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
                objectName: "sceneDelete"
                visible: !root.isNew
                text: qsTr("Delete")
                onClicked: confirm.ask({
                    key: "deleteScene",
                    label: qsTr("Delete scene"),
                    button: qsTr("Delete"),
                    confirm: qsTr("Delete the scene “%1”? The devices stay as they are.").arg(root.draft.name)
                })
            }
            PillButton {
                objectName: "sceneCapture"
                visible: !root.isNew
                text: qsTr("Use current state")
                onClicked: root.captureAll()
            }
            Item {
                Layout.fillWidth: true
            }
            PillButton {
                text: qsTr("Cancel")
                onClicked: root.closed()
            }
            PillButton {
                objectName: "sceneSave"
                primary: true
                enabled: root.includedCount > 0 || !root.isNew
                text: qsTr("Save")
                onClicked: root.save()
            }
        }
    }

    TextKeyboard {
        id: keyboard
        objectName: "sceneKeyboard"
    }

    ConfirmDialog {
        id: confirm
        onConfirmed: Busy.run(qsTr("Saving …"), () => {
            panel.deleteScene(root.draft.id);
            root.closed();
        })
    }
}
