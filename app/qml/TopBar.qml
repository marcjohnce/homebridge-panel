import QtQuick
import QtQuick.Layouts

// Header for square and portrait screens: clock, date, indoor temperature, status and
// settings in one row, scenes as a horizontal strip below. Leaves the full width to the tiles.
ColumnLayout {
    id: root

    property date now: new Date()
    signal openSettings

    spacing: 12

    Timer {
        interval: 5000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.now = new Date()
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 16

        Text {
            objectName: "clock"
            text: Qt.formatTime(root.now, "hh:mm")
            color: Theme.ink
            font.pixelSize: Theme.s(52)
            font.weight: Font.ExtraLight
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Text {
                objectName: "date"
                Layout.fillWidth: true
                text: root.now.toLocaleDateString(Qt.locale("en_GB"), "dddd, d MMMM")
                color: Theme.muted
                font.pixelSize: Theme.s(15)
                elide: Text.ElideRight
            }
            RowLayout {
                objectName: "climate"
                visible: panel.indoorTemp !== "" || panel.outdoorTemp !== ""
                spacing: 6
                LineIcon {
                    visible: panel.indoorTemp !== ""
                    Layout.preferredWidth: 20
                    Layout.preferredHeight: 20
                    name: "thermostat"
                    color: Theme.gold
                }
                Text {
                    visible: panel.indoorTemp !== ""
                    text: qsTr("%1 °C indoors").arg(panel.indoorTemp)
                    color: Theme.ink
                    font.pixelSize: Theme.s(17)
                    font.weight: Font.Light
                }
                LineIcon {
                    visible: panel.outdoorTemp !== ""
                    Layout.leftMargin: panel.indoorTemp !== "" ? 10 : 0
                    Layout.preferredWidth: 20
                    Layout.preferredHeight: 20
                    name: "weather"
                    color: Theme.gold
                }
                Text {
                    visible: panel.outdoorTemp !== ""
                    text: qsTr("%1 °C outdoors").arg(panel.outdoorTemp)
                    color: Theme.ink
                    font.pixelSize: Theme.s(17)
                    font.weight: Font.Light
                }
            }
        }

        Rectangle {
            objectName: "statusDot"
            Layout.preferredWidth: 8
            Layout.preferredHeight: 8
            radius: 4
            color: panel.statusOk ? Theme.ok : Theme.err
        }
        Text {
            objectName: "statusText"
            Layout.maximumWidth: 150
            text: panel.statusText
            color: Theme.muted
            font.pixelSize: Theme.s(14)
            elide: Text.ElideRight
        }
        Item {
            objectName: "settingsButton"
            Layout.preferredWidth: 44
            Layout.preferredHeight: 44
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

    ListView {
        id: sceneList
        objectName: "scenes"
        layer.enabled: GraphicsInfo.api === GraphicsInfo.Software   // see TileGrid.qml

        // opaque background for the layer above (transparent layers render black in software mode)
        Rectangle {
            parent: sceneList
            anchors.fill: parent
            z: -1
            visible: sceneList.layer.enabled
            color: Theme.page
        }

        visible: panel.scenes.length > 0
        Layout.fillWidth: true
        Layout.preferredHeight: 44
        orientation: ListView.Horizontal
        spacing: 8
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        model: panel.scenes
        delegate: SceneButton {
            required property var modelData
            chip: true
            sceneId: modelData.id
            label: modelData.name
            iconName: modelData.icon
        }
    }
}
