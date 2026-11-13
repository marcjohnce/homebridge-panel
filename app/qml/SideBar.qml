import QtQuick
import QtQuick.Layouts

// Linke Spalte: Uhr, Innentemperatur, Szenen, Status und Zugang zu den Einstellungen
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
        text: Qt.formatTime(root.now, "hh:mm")
        color: Theme.ink
        font.pixelSize: root.compact ? 60 : 84
        font.weight: Font.ExtraLight
        lineHeight: 0.95
    }
    Text {
        Layout.topMargin: 6
        text: root.now.toLocaleDateString(Qt.locale("de_DE"), "dddd, d. MMMM")
        color: Theme.muted
        font.pixelSize: 17
    }

    RowLayout {
        visible: panel.indoorTemp !== ""
        Layout.topMargin: root.compact ? 16 : 26
        spacing: 10
        LineIcon {
            Layout.preferredWidth: 30
            Layout.preferredHeight: 30
            name: "thermostat"
            color: Theme.gold
        }
        Column {
            Text {
                text: qsTr("%1 °C").arg(panel.indoorTemp)
                color: Theme.ink
                font.pixelSize: 28
                font.weight: Font.Light
            }
            Text {
                text: qsTr("innen")
                color: Theme.muted
                font.pixelSize: 14
            }
        }
    }

    Text {
        visible: panel.scenes.length > 0
        Layout.topMargin: root.compact ? 16 : 28
        Layout.bottomMargin: 4
        text: qsTr("Szenen")
        color: Theme.muted
        font.pixelSize: 14
    }

    Flickable {
        Layout.fillWidth: true
        Layout.fillHeight: true
        contentHeight: sceneColumn.height
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Column {
            id: sceneColumn
            width: parent.width
            Repeater {
                model: panel.scenes
                SceneButton {
                    required property var modelData
                    width: sceneColumn.width
                    sceneId: modelData.id
                    label: modelData.name
                    iconName: modelData.icon
                    compact: root.compact
                }
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.topMargin: 12
        spacing: 8

        Rectangle {
            Layout.preferredWidth: 8
            Layout.preferredHeight: 8
            radius: 4
            color: panel.statusOk ? Theme.ok : Theme.err
        }
        Text {
            Layout.fillWidth: true
            text: panel.statusText
            color: Theme.muted
            font.pixelSize: 14
            elide: Text.ElideRight
        }
        Item {
            Layout.preferredWidth: 44
            Layout.preferredHeight: 44
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Einstellungen")
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
