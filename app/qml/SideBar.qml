import QtQuick
import QtQuick.Layouts

// Left column: clock, indoor temperature, scenes, status and access to settings
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

    Text {
        visible: panel.scenes.length > 0
        Layout.topMargin: root.compact ? 16 : Theme.s(28)
        Layout.bottomMargin: 4
        text: qsTr("Scenes")
        color: Theme.muted
        font.pixelSize: Theme.s(14)
    }

    Flickable {
        id: sceneFlick
        objectName: "scenes"
        layer.enabled: GraphicsInfo.api === GraphicsInfo.Software   // see TileGrid.qml

        // opaque background for the layer above (transparent layers render black in software mode)
        Rectangle {
            parent: sceneFlick
            anchors.fill: parent
            z: -1
            visible: sceneFlick.layer.enabled
            color: Theme.page
        }

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
