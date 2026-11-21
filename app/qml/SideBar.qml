import QtQuick
import QtQuick.Layouts

// Left column: clock, indoor temperature, menu (favorites, lights, scenes, climate, security), status, settings
ColumnLayout {
    id: root

    property date now: new Date()
    property bool compact: false
    property real fitHeight: height     // height the sidebar gets (set from outside: no layout loop)
    signal openSettings

    spacing: 0

    Timer {
        interval: 5000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.now = new Date()
    }

    // room left for the menu entries (the clock, temperatures and status come first)
    readonly property real menuSpace: fitHeight - clockText.implicitHeight - dateText.implicitHeight - 6
                                      - (climate.visible ? climate.implicitHeight + climate.Layout.topMargin : 0)
                                      - menu.Layout.topMargin - statusRow.implicitHeight - statusRow.Layout.topMargin

    Text {
        id: clockText
        objectName: "clock"
        text: Qt.formatTime(root.now, "hh:mm")
        color: Theme.ink
        font.pixelSize: root.compact ? 52 : Theme.s(72)
        font.weight: Font.ExtraLight
        lineHeight: 0.95
    }
    Text {
        id: dateText
        objectName: "date"
        Layout.topMargin: 6
        text: Theme.date(root.now)
        color: Theme.muted
        font.pixelSize: Theme.s(17)
    }

    ColumnLayout {
        id: climate
        objectName: "climate"
        visible: panel.indoorTemp !== "" || panel.outdoorTemp !== ""
        Layout.topMargin: root.compact ? 16 : Theme.s(26)
        spacing: root.compact ? 6 : Theme.s(12)

        Repeater {
            model: [
                { temp: panel.indoorTemp, label: qsTr("indoors"), icon: "thermostat" },
                { temp: panel.outdoorTemp, label: qsTr("outdoors"), icon: "weather" }
            ]
            RowLayout {
                required property var modelData
                visible: modelData.temp !== ""
                spacing: 10
                LineIcon {
                    Layout.preferredWidth: Theme.s(30)
                    Layout.preferredHeight: Theme.s(30)
                    name: parent.modelData.icon
                    color: Theme.gold
                }
                // value and label on one line: room for the menu below
                Row {
                    spacing: 8
                    Text {
                        id: tempValue
                        text: qsTr("%1 °C").arg(parent.parent.modelData.temp)
                        color: Theme.ink
                        font.pixelSize: root.compact ? 22 : Theme.s(28)
                        font.weight: Font.Light
                    }
                    Text {
                        anchors.baseline: tempValue.baseline
                        text: parent.parent.modelData.label
                        color: Theme.muted
                        font.pixelSize: Theme.s(14)
                    }
                }
            }
        }
    }

    CategoryMenu {
        id: menu
        Layout.fillWidth: true
        maxEntryHeight: (root.menuSpace - spacing * (count - 1)) / count
        Layout.topMargin: root.compact ? 8 : Theme.s(30)
        compact: root.compact
    }

    Item {
        Layout.fillHeight: true
    }

    RowLayout {
        id: statusRow
        Layout.fillWidth: true
        Layout.topMargin: 12
        spacing: 8

        Rectangle {
            objectName: "statusDot"
            Layout.preferredWidth: 8
            Layout.preferredHeight: 8
            radius: 4
            color: panel.statusOk ? Theme.ok : Theme.err
        }
        Text {
            objectName: "statusText"
            Layout.fillWidth: true
            text: panel.statusText
            color: Theme.muted
            font.pixelSize: Theme.s(14)
            elide: Text.ElideRight
        }
        Item {
            objectName: "settingsButton"
            Layout.preferredWidth: Theme.s(44)
            Layout.preferredHeight: Theme.s(44)
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Settings")
            Keys.onReturnPressed: root.openSettings()

            LineIcon {
                anchors.centerIn: parent
                width: 24
                height: 24
                name: "sliders"
                color: parent.activeFocus ? Theme.gold : Theme.muted
            }
            MouseArea {
                anchors.fill: parent
                onClicked: root.openSettings()
            }
        }
    }
}
