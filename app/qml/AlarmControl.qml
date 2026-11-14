import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Alarm system: current state on top, one large field per mode; disarming asks for the PIN
// if one is set in the settings
ColumnLayout {
    id: root

    property var dev
    readonly property var st: dev.state || ({})
    readonly property var modes: dev.meta && dev.meta.modes ? dev.meta.modes : []
    readonly property bool narrow: width < Theme.s(700)
    readonly property int columns: narrow ? 2 : Math.max(2, modes.length)
    readonly property var labels: ({ stay: qsTr("Home"), away: qsTr("Away"), night: qsTr("Night"), off: qsTr("Disarmed") })
    readonly property var icons: ({ stay: "modeHome", away: "modeAway", night: "modeNight", off: "modeOff" })

    function choose(mode) {
        if (mode === st.target)
            return;
        if (mode === "off" && panel.alarmPinSet)
            pinPrompt.ask();
        else if (mode === "off")
            panel.disarm(dev.id, "");
        else
            panel.setAttrs(dev.id, { mode: mode });
    }

    spacing: Theme.s(20)

    Item {
        Layout.fillHeight: true
    }

    ColumnLayout {
        Layout.alignment: Qt.AlignHCenter
        spacing: Theme.s(10)
        LineIcon {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.s(root.narrow ? 56 : 72)
            Layout.preferredHeight: Theme.s(root.narrow ? 56 : 72)
            lineWidth: 1.1
            name: root.st.armed ? "alarm" : "alarmOff"
            color: root.st.triggered ? Theme.err : root.st.armed ? Theme.gold : Theme.muted
        }
        Text {
            objectName: "alarmState"
            Layout.alignment: Qt.AlignHCenter
            text: root.dev.stateText || ""
            color: root.st.triggered ? Theme.err : Theme.ink
            font.pixelSize: Theme.s(root.narrow ? 26 : 32)
            font.weight: root.st.triggered ? Font.Normal : Font.Light
        }
    }

    GridLayout {
        objectName: "alarmModes"
        Layout.alignment: Qt.AlignHCenter
        Layout.fillWidth: true
        Layout.maximumWidth: root.columns * Theme.s(210) + (root.columns - 1) * columnSpacing
        Layout.topMargin: Theme.s(root.narrow ? 12 : 30)
        columns: root.columns
        columnSpacing: Theme.s(14)
        rowSpacing: Theme.s(14)

        Repeater {
            model: root.modes
            Rectangle {
                id: mode
                required property string modelData
                readonly property bool on: modelData === root.st.target
                objectName: "alarmMode:" + modelData
                Layout.fillWidth: true
                Layout.preferredHeight: Theme.s(root.narrow ? 120 : 140)
                radius: 16
                color: on ? (root.st.triggered ? Theme.alarm : Theme.gold) : (mouse.pressed ? Theme.tilePress : Theme.tile)
                border.color: activeFocus ? Theme.ink : "transparent"
                border.width: 2
                activeFocusOnTab: true
                Accessible.role: Accessible.RadioButton
                Accessible.name: root.labels[modelData] || modelData
                Accessible.checked: on
                Keys.onSpacePressed: root.choose(modelData)

                Behavior on color { ColorAnimation { duration: 150 } }

                readonly property color ink: on ? (root.st.triggered ? Theme.alarmInk : Theme.goldInk) : Theme.ink

                LineIcon {
                    x: Theme.s(18)
                    y: Theme.s(18)
                    width: Theme.s(30)
                    height: Theme.s(30)
                    lineWidth: 1.3
                    name: root.icons[mode.modelData] || "alarm"
                    color: mode.on ? mode.ink : Theme.muted
                }
                Text {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: Theme.s(18)
                    text: root.labels[mode.modelData] || mode.modelData
                    elide: Text.ElideRight
                    font.pixelSize: Theme.s(19)
                    font.weight: Font.Medium
                    color: mode.ink
                }
                MouseArea {
                    id: mouse
                    anchors.fill: parent
                    enabled: root.dev.reachable
                    onClicked: root.choose(mode.modelData)
                }
            }
        }
    }

    Item {
        Layout.fillHeight: true
    }

    // PIN entry for disarming
    Popup {
        id: pinPrompt
        objectName: "alarmPin"
        property string entry: ""
        property string error: ""

        function ask() {
            entry = "";
            error = "";
            open();
        }
        function press(k) {
            error = "";
            if (k === "⌫")
                entry = entry.slice(0, -1);
            else if (k !== "" && entry.length < 8)
                entry += k;
        }
        function submit() {
            const err = panel.disarm(root.dev.id, entry);
            if (err !== "") {
                error = err;
                entry = "";
            } else {
                close();
            }
        }

        parent: Overlay.overlay
        anchors.centerIn: Overlay.overlay
        width: Theme.s(372)
        padding: 22
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
            spacing: 14
            focus: true
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Backspace)
                    pinPrompt.press("⌫");
                else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                    pinPrompt.submit();
                else if (/^[0-9]$/.test(event.text))
                    pinPrompt.press(event.text);
                else
                    return;
                event.accepted = true;
            }

            Text {
                text: qsTr("Enter the PIN to disarm")
                color: Theme.ink
                font.pixelSize: Theme.s(18)
                font.weight: Font.Medium
            }
            Rectangle {
                objectName: "alarmPinDisplay"
                width: parent.width
                height: Theme.s(58)
                radius: 10
                color: Theme.page
                border.color: pinPrompt.error !== "" ? Theme.err : Theme.line
                Text {
                    anchors.centerIn: parent
                    text: "•".repeat(pinPrompt.entry.length)
                    color: Theme.ink
                    font.pixelSize: Theme.s(30)
                    font.letterSpacing: 6
                }
            }
            Text {
                width: parent.width
                visible: pinPrompt.error !== ""
                text: pinPrompt.error
                color: Theme.err
                font.pixelSize: Theme.s(14)
            }
            Grid {
                columns: 3
                spacing: 8
                Repeater {
                    model: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"]
                    Rectangle {
                        required property string modelData
                        width: (pinPrompt.availableWidth - 16) / 3
                        height: Theme.s(56)
                        radius: 12
                        color: keyMouse.pressed ? Theme.tilePress : Theme.page
                        // an empty key keeps its place in the grid (hidden items would shift the keys after it)
                    opacity: modelData !== "" ? 1 : 0
                    enabled: modelData !== ""
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData === "⌫" ? qsTr("Delete") : modelData
                        Text {
                            anchors.centerIn: parent
                            visible: parent.modelData !== "⌫"
                            text: parent.modelData
                            color: Theme.ink
                            font.pixelSize: Theme.s(24)
                            font.weight: Font.Light
                        }
                        LineIcon {
                            anchors.centerIn: parent
                            visible: parent.modelData === "⌫"
                            width: 26
                            height: 26
                            name: "backspace"
                            color: Theme.ink
                        }
                        MouseArea {
                            id: keyMouse
                            anchors.fill: parent
                            onClicked: pinPrompt.press(parent.modelData)
                        }
                    }
                }
            }
            Row {
                anchors.right: parent.right
                spacing: 10
                PillButton {
                    text: qsTr("Cancel")
                    onClicked: pinPrompt.close()
                }
                PillButton {
                    objectName: "alarmPinDisarm"
                    primary: true
                    text: qsTr("Disarm")
                    enabled: pinPrompt.entry.length >= 4
                    onClicked: pinPrompt.submit()
                }
            }
        }
    }
}
