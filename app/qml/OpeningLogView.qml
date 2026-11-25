import QtQuick
import QtQuick.Layouts

// Detail view of a window, door or garage door: when it opened and closed, by day, newest
// first (noted by the panel while it runs, kept 30 days)
Item {
    id: root
    objectName: "openingLog"

    required property string deviceId
    property var days: panel.openingLog(deviceId)

    Connections {
        target: panel
        function onDeviceUpdated(id) {
            if (id === root.deviceId)
                root.days = panel.openingLog(root.deviceId);
        }
    }
    Timer {                                     // "open for" of an opening still running
        interval: 60000
        running: true
        repeat: true
        onTriggered: root.days = panel.openingLog(root.deviceId)
    }

    Text {
        anchors.centerIn: parent
        width: parent.width * 0.8
        visible: root.days.length === 0
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: qsTr("Not opened in the last 30 days. The panel notes openings while it runs.")
        color: Theme.muted
        font.pixelSize: Theme.s(17)
    }

    Flickable {
        anchors.fill: parent
        anchors.topMargin: Theme.s(8)
        visible: root.days.length > 0
        contentHeight: list.implicitHeight + Theme.s(16)
        boundsBehavior: Flickable.StopAtBounds
        clip: true

        Column {
            id: list
            objectName: "openingDays"
            width: Math.min(parent.width, Theme.s(640))
            x: (parent.width - width) / 2
            spacing: Theme.s(14)

            Repeater {
                model: root.days
                Column {
                    id: dayBlock
                    required property var modelData
                    width: list.width
                    spacing: 0
                    Text {
                        bottomPadding: Theme.s(6)
                        text: dayBlock.modelData.day
                        color: Theme.muted
                        font.pixelSize: Theme.s(15)
                    }
                    Rectangle {
                        width: parent.width
                        height: rows.implicitHeight
                        radius: 12
                        color: Theme.tile
                        Column {
                            id: rows
                            width: parent.width
                            Repeater {
                                model: dayBlock.modelData.rows
                                Item {
                                    id: entry
                                    required property var modelData
                                    required property int index
                                    width: rows.width
                                    height: Theme.s(50)
                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 16
                                        anchors.rightMargin: 16
                                        spacing: 12
                                        Rectangle {
                                            Layout.preferredWidth: 10
                                            Layout.preferredHeight: 10
                                            radius: 5
                                            color: entry.modelData.open ? Theme.err : Theme.line
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: entry.modelData.open ? qsTr("Open since %1").arg(entry.modelData.from)
                                                                       : qsTr("%1 to %2").arg(entry.modelData.from).arg(entry.modelData.to)
                                            color: Theme.ink
                                            font.pixelSize: Theme.s(17)
                                        }
                                        Text {
                                            text: entry.modelData.duration
                                            color: Theme.muted
                                            font.pixelSize: Theme.s(15)
                                        }
                                    }
                                    Rectangle {
                                        visible: entry.index > 0
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
                }
            }
        }
    }
}
