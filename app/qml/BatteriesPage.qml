import QtQuick
import QtQuick.Layouts

// Settings → Batteries: every battery powered device, the emptiest first
Rectangle {
    id: root

    signal closed

    color: Theme.page
    focus: true
    Keys.onEscapePressed: root.closed()

    MouseArea {
        anchors.fill: parent
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 28
        anchors.rightMargin: 28
        anchors.topMargin: 18
        spacing: 4

        BackHeader {
            Layout.fillWidth: true
            backText: qsTr("Settings")
            title: qsTr("Batteries")
            onBack: root.closed()
        }

        Flickable {
            objectName: "batteriesFlick"
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: content.implicitHeight + Theme.s(24)
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            ColumnLayout {
                id: content
                width: Math.min(parent.width, Theme.s(760))
                x: (parent.width - width) / 2
                spacing: Theme.s(10)

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: Theme.s(10)
                    leftPadding: 4
                    text: panel.batteries.length > 0
                          ? qsTr("Below 10 % or when the device reports a low battery, it counts as almost empty.")
                          : qsTr("No device reports a battery level.")
                    color: Theme.muted
                    font.pixelSize: Theme.s(15)
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    visible: panel.batteries.length > 0
                    Layout.fillWidth: true
                    Layout.preferredHeight: list.implicitHeight
                    radius: 14
                    color: Theme.tile

                    Column {
                        id: list
                        width: parent.width
                        Repeater {
                            model: panel.batteries
                            Item {
                                id: item
                                required property var modelData
                                required property int index
                                objectName: "batteryRow:" + modelData.id
                                width: list.width
                                height: Theme.s(64)
                                Accessible.role: Accessible.StaticText
                                Accessible.name: modelData.name + ", " + modelData.room + ": " + modelData.text

                                Rectangle {
                                    visible: item.index > 0
                                    x: 18
                                    width: parent.width - 36
                                    height: 1
                                    color: Theme.line
                                }
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 18
                                    anchors.rightMargin: 18
                                    spacing: 16
                                    LineIcon {
                                        Layout.preferredWidth: Theme.s(26)
                                        Layout.preferredHeight: Theme.s(26)
                                        name: item.modelData.icon
                                        color: Theme.ink
                                    }
                                    Column {
                                        Layout.fillWidth: true
                                        spacing: 1
                                        Text {
                                            width: parent.width
                                            text: item.modelData.name
                                            elide: Text.ElideRight
                                            color: Theme.ink
                                            font.pixelSize: Theme.s(17)
                                        }
                                        Text {
                                            width: parent.width
                                            text: item.modelData.room
                                            elide: Text.ElideRight
                                            color: Theme.muted
                                            font.pixelSize: Theme.s(13)
                                        }
                                    }
                                    LineIcon {
                                        Layout.preferredWidth: Theme.s(24)
                                        Layout.preferredHeight: Theme.s(24)
                                        lineWidth: 1.5
                                        name: item.modelData.low ? "battery" : "batteryFull"
                                        color: item.modelData.low ? Theme.err : Theme.muted
                                    }
                                    Text {
                                        text: item.modelData.level >= 0 ? qsTr("%1 %").arg(item.modelData.level)
                                              : item.modelData.low ? qsTr("Low") : qsTr("OK")
                                        color: item.modelData.low ? Theme.err : Theme.muted
                                        font.pixelSize: Theme.s(16)
                                        font.weight: item.modelData.low ? Font.Medium : Font.Normal
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
