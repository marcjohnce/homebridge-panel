import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root

    readonly property var rows: [
        { label: qsTr("Connection"), value: panel.statusDetail !== "" ? panel.statusDetail : panel.statusText },
        { label: qsTr("Devices"), value: String(panel.deviceCount) },
        { label: qsTr("Rooms, scenes, schedules"), value: panel.configPath !== "" ? panel.configPath : qsTr("no config.yaml found") },
        { label: qsTr("Settings file"), value: panel.settings.path },
        { label: qsTr("Version"), value: panel.version }
    ]

    spacing: 10

    Text {
        Layout.leftMargin: 4
        Layout.topMargin: 14
        text: qsTr("Info")
        color: Theme.muted
        font.pixelSize: 15
        Accessible.role: Accessible.Heading
    }

    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: infoColumn.implicitHeight
        radius: 14
        color: Theme.tile

        Column {
            id: infoColumn
            width: parent.width
            Repeater {
                model: root.rows
                Column {
                    id: infoRow
                    required property var modelData
                    required property int index
                    width: infoColumn.width

                    Rectangle {
                        visible: infoRow.index > 0
                        width: parent.width - 36
                        x: 18
                        height: 1
                        color: Theme.line
                    }
                    RowLayout {
                        width: parent.width
                        height: Math.max(52, valueText.implicitHeight + 24)
                        spacing: 16
                        Text {
                            Layout.leftMargin: 18
                            text: infoRow.modelData.label
                            color: Theme.ink
                            font.pixelSize: 16
                        }
                        Text {
                            id: valueText
                            Layout.fillWidth: true
                            Layout.rightMargin: 18
                            horizontalAlignment: Text.AlignRight
                            text: infoRow.modelData.value
                            color: Theme.muted
                            font.pixelSize: 14
                            wrapMode: Text.WrapAnywhere
                        }
                    }
                }
            }
        }
    }
}
