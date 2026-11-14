import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Virtual device: the value of an MQTT topic with a name, unit and icon (Settings → Rooms and devices).
// edit(null) creates one; edit(device) changes it.
Popup {
    id: root

    property var device: null
    property var keyboard: null          // TextKeyboard of the page
    property string draftName
    property string draftUnit
    property string draftTopic
    property string draftJsonKey
    property int draftDecimals: 1
    property string draftIcon: "gauge"
    property string draftRoom
    property string error
    property string lastValue

    readonly property var icons: [
        { value: "none", label: qsTr("No icon") }, { value: "gauge", label: qsTr("Measurement") },
        { value: "thermostat", label: qsTr("Temperature") }, { value: "drop", label: qsTr("Humidity") },
        { value: "power", label: qsTr("Power") }, { value: "sun", label: qsTr("Light level") }
    ]

    function edit(d) {
        device = d;
        const v = d ? d.virtual : null;
        draftName = v ? v.name : "";
        draftUnit = v ? v.unit : "";
        draftTopic = v ? v.topic : "";
        draftJsonKey = v ? v.json_key : "";
        draftDecimals = v ? v.decimals : 1;
        draftIcon = v ? v.icon : "gauge";
        draftRoom = d ? d.room : (panel.roomEditor.rooms.find(r => r.isDefault) || { name: "" }).name;
        lastValue = d ? panel.roomEditor.lastValue(d.id) : "";
        error = "";
        open();
    }
    function save() {
        const err = panel.roomEditor.saveVirtual({
            id: device ? device.virtual.id : "", name: draftName, unit: draftUnit, topic: draftTopic,
            jsonKey: draftJsonKey, decimals: draftDecimals, icon: draftIcon, room: draftRoom
        });
        if (err !== "")
            error = err;
        else
            close();
    }
    function editText(label, value, accept, opts) {
        keyboard.edit(label, value, text => {
            accept(text.trim());
            return "";
        }, opts);
    }

    anchors.centerIn: Overlay.overlay
    width: Math.min(parent ? parent.width - 40 : Theme.s(680), Theme.s(680))
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
                    text: root.device ? qsTr("Virtual device (MQTT)") : qsTr("New virtual device (MQTT)")
                    color: Theme.ink
                    font.pixelSize: Theme.s(19)
                    font.weight: Font.Medium
                    Accessible.role: Accessible.Heading
                }
                Text {
                    width: parent.width
                    visible: !panel.settings.sections.find(s => s.id === "mqtt").fields.find(f => f.key === "mqtt_enabled").value
                    text: qsTr("MQTT is switched off. Set up the broker under Settings → MQTT.")
                    color: Theme.err
                    font.pixelSize: Theme.s(14)
                    wrapMode: Text.WordWrap
                }

                Row {
                    width: parent.width
                    spacing: 12
                    EditField {
                        objectName: "virtualName"
                        width: (parent.width - 12) * 0.62
                        label: qsTr("Name")
                        value: root.draftName
                        onTapped: root.editText(qsTr("Name"), root.draftName, t => root.draftName = t, { maxLength: 40 })
                    }
                    EditField {
                        objectName: "virtualUnit"
                        width: (parent.width - 12) * 0.38
                        label: qsTr("Unit")
                        value: root.draftUnit
                        onTapped: root.editText(qsTr("Unit"), root.draftUnit, t => root.draftUnit = t,
                                                { maxLength: 10, autoCapitalize: false, hint: qsTr("e.g. bar, kWh, %") })
                    }
                }
                EditField {
                    objectName: "virtualTopic"
                    width: parent.width
                    label: qsTr("MQTT topic")
                    value: root.draftTopic
                    note: root.lastValue
                    onTapped: root.editText(qsTr("MQTT topic"), root.draftTopic, t => root.draftTopic = t,
                                            { maxLength: 200, autoCapitalize: false, hint: qsTr("e.g. boiler/pressure") })
                }
                EditField {
                    objectName: "virtualJsonKey"
                    width: parent.width
                    label: qsTr("Value from JSON (optional)")
                    value: root.draftJsonKey
                    note: qsTr("Key of the value if the topic sends JSON, e.g. pressure or data.pressure")
                    onTapped: root.editText(qsTr("Value from JSON (optional)"), root.draftJsonKey,
                                            t => root.draftJsonKey = t, { maxLength: 80, autoCapitalize: false })
                }

                Text {
                    topPadding: 4
                    text: qsTr("Decimal places")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                }
                Flow {
                    width: parent.width
                    spacing: 10
                    Repeater {
                        model: [0, 1, 2, 3]
                        PillButton {
                            required property int modelData
                            text: String(modelData)
                            primary: modelData === root.draftDecimals
                            onClicked: root.draftDecimals = modelData
                        }
                    }
                }

                Text {
                    topPadding: 4
                    text: qsTr("Icon")
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                }
                Flow {
                    objectName: "virtualIcons"
                    width: parent.width
                    spacing: 10
                    Repeater {
                        model: root.icons
                        PillButton {
                            required property var modelData
                            objectName: "virtualIcon:" + modelData.value
                            text: modelData.label
                            iconName: modelData.value === "none" ? "" : modelData.value
                            primary: modelData.value === root.draftIcon
                            onClicked: root.draftIcon = modelData.value
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
                    width: parent.width
                    spacing: 10
                    Repeater {
                        model: panel.roomEditor.rooms
                        PillButton {
                            required property var modelData
                            text: modelData.name
                            primary: modelData.name === root.draftRoom
                            onClicked: root.draftRoom = modelData.name
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
                    panel.roomEditor.deleteVirtual(root.device.virtual.id);
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
                objectName: "virtualSave"
                primary: true
                text: qsTr("Save")
                onClicked: root.save()
            }
        }
    }

    // label above a box that opens the keyboard
    component EditField: Column {
        id: field
        property string label
        property string value
        property string note
        signal tapped

        spacing: 6
        Text {
            text: field.label
            color: Theme.muted
            font.pixelSize: Theme.s(14)
        }
        Rectangle {
            width: parent.width
            height: Theme.s(50)
            radius: 10
            color: Theme.page
            border.color: activeFocus ? Theme.gold : Theme.line
            border.width: activeFocus ? 2 : 1
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Change %1, currently %2").arg(field.label).arg(field.value)
            Keys.onReturnPressed: field.tapped()

            Text {
                anchors.verticalCenter: parent.verticalCenter
                x: 14
                width: parent.width - 52
                text: field.value
                elide: Text.ElideMiddle
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
                onClicked: field.tapped()
            }
        }
        Text {
            width: parent.width
            visible: text !== ""
            text: field.note
            color: Theme.muted
            font.pixelSize: Theme.s(13)
            wrapMode: Text.WordWrap
        }
    }
}
