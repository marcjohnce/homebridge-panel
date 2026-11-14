import QtQuick
import QtQuick.Layouts

// Left column: clock, indoor temperature, menu (lights, climate, security), status, settings
ColumnLayout {
    id: root

    property date now: new Date()
    property bool compact: false
    signal openSettings

    spacing: 0

    Timer {
        interval: 5000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.now = new Date()
    }

    Text {
        objectName: "clock"
        text: Qt.formatTime(root.now, "hh:mm")
        color: Theme.ink
        font.pixelSize: root.compact ? 60 : Theme.s(84)
        font.weight: Font.ExtraLight
        lineHeight: 0.95
    }
    Text {
        objectName: "date"
        Layout.topMargin: 6
        text: Theme.date(root.now)
        color: Theme.muted
        font.pixelSize: Theme.s(17)
    }

    ColumnLayout {
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
                Column {
                    Text {
                        text: qsTr("%1 °C").arg(parent.parent.modelData.temp)
                        color: Theme.ink
                        font.pixelSize: root.compact ? 22 : Theme.s(28)
                        font.weight: Font.Light
                    }
                    Text {
                        text: parent.parent.modelData.label
                        color: Theme.muted
                        font.pixelSize: Theme.s(14)
                    }
                }
            }
        }
    }

    CategoryMenu {
        Layout.fillWidth: true
        Layout.topMargin: root.compact ? 8 : Theme.s(30)
        compact: root.compact
    }

    Item {
        Layout.fillHeight: true
    }

    RowLayout {
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
