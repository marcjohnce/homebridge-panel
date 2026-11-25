import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Edit a device in Settings → Rooms and devices: display name, kind (contact and motion
// sensors: window, door, glass break …), room, favorite, outdoor sensor and hidden. Saved with "Save".
Popup {
    id: root

    property var device: ({})
    property var keyboard: null          // TextKeyboard of the page
    property string draftName
    property string draftKind
    property string draftRoom
    property bool draftHidden
    property bool draftFavorite
    property bool draftOutdoor
    property bool draftQuiet
    property bool draftMeasureOnly
    property bool draftMainMeter
    // window, door, contact, motion and presence sensors can be kept out of security alerts (not alarms)
    // (devices without a kind, e.g. garage doors and motorized windows, always can)
    readonly property bool canQuiet: !!device.canQuiet && (!(draftKind || device.kind)
        || ["window", "door", "contact", "motion", "presence"].indexOf(draftKind || device.kind) >= 0)
    property string draftArea
    property string error

    function edit(d) {
        device = d;
        draftName = d.name;
        draftKind = d.kind || "";
        draftRoom = d.room;
        draftHidden = !!d.hidden;
        draftFavorite = !!d.favorite;
        draftOutdoor = !!d.outdoor;
        draftQuiet = !!d.quiet;
        draftMeasureOnly = !!d.measureOnly;
        draftMainMeter = !!d.mainMeter;
        draftArea = d.area || "";
        error = "";
        open();
    }
    function save() {
        Busy.run(qsTr("Saving …"), saveNow);
    }
    function saveNow() {
        const err = panel.roomEditor.saveDevice(device.id, {
            name: draftName, kind: draftKind, room: draftRoom, area: draftArea,
            hidden: draftHidden, favorite: draftFavorite, outdoor: draftOutdoor, quiet: canQuiet ? draftQuiet : false,
            measureOnly: draftMeasureOnly, mainMeter: draftMainMeter
        });
        if (err !== "")
            error = err;
        else
            close();
    }
    function editName() {
        keyboard.edit(qsTr("Display name"), draftName, text => {
            root.draftName = text.trim() === "" ? root.device.baseName : text.trim().replace(/\s+/g, " ");
            return "";
        }, { hint: qsTr("Leave empty to use the name from Homebridge"), maxLength: 40 });
    }
    function newRoom() {
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

    // scrolls when the dialog is taller than the screen (720 × 720, many rooms)
    height: Math.min(implicitHeight, parent ? parent.height - 40 : implicitHeight)
    contentItem: ColumnLayout {
        spacing: Theme.s(12)

        Flickable {
            objectName: "deviceEditorFlick"
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

                ToggleRow {
                    width: parent.width
                    label: qsTr("Favorite")
                    help: qsTr("Shown under Favorites, the start page of the panel")
                    checked: root.draftFavorite
                    toggleName: "favoriteToggle"
                    onToggled: root.draftFavorite = !root.draftFavorite
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
                            iconName: modelData.icon
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
                    topPadding: 4
                    text: qsTr("Show under")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                }
                Flow {
                    objectName: "areaChoices"
                    width: parent.width
                    spacing: 10
                    Repeater {
                        model: root.device.areas || []
                        PillButton {
                            required property var modelData
                            objectName: "area:" + (modelData.value || "auto")
                            text: modelData.label
                            primary: modelData.value === root.draftArea
                            onClicked: root.draftArea = modelData.value
                        }
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
                    objectName: "alertsRow"
                    visible: root.canQuiet
                    width: parent.width
                    label: qsTr("Security alerts")
                    help: qsTr("Off: only shown, e.g. a motion sensor used for automations – no alert, no red dot")
                    checked: !root.draftQuiet
                    toggleName: "alertsToggle"
                    onToggled: root.draftQuiet = !root.draftQuiet
                }
                ToggleRow {
                    objectName: "measureOnlyRow"
                    visible: !!root.device.canMeasureOnly && !root.draftMainMeter
                    width: parent.width
                    label: qsTr("Only measure")
                    help: qsTr("The panel shows the power but never switches it, e.g. a fridge or a server")
                    checked: root.draftMeasureOnly
                    toggleName: "measureOnlyToggle"
                    onToggled: root.draftMeasureOnly = !root.draftMeasureOnly
                }
                ToggleRow {
                    objectName: "mainMeterRow"
                    visible: !!root.device.canMainMeter
                    width: parent.width
                    label: qsTr("Main meter")
                    help: qsTr("Measures the whole house, e.g. a smart meter: its power is the total under Energy")
                    checked: root.draftMainMeter
                    toggleName: "mainMeterToggle"
                    onToggled: root.draftMainMeter = !root.draftMainMeter
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
            }
        }

        Row {
            Layout.alignment: Qt.AlignRight
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
