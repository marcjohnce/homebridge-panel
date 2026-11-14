import QtQuick
import QtQuick.Layouts

// Switch group: one large field per switch (only one is on), "All off" below if allowed
ColumnLayout {
    id: root

    property var dev
    readonly property var options: dev.meta ? dev.meta.options : []
    readonly property string active: dev.state ? (dev.state.active || "") : ""
    readonly property int columns: width < Theme.s(700) ? 2 : Math.min(4, Math.max(2, options.length))

    spacing: Theme.s(24)

    Item {
        Layout.fillHeight: true
    }

    GridLayout {
        objectName: "choiceOptions"
        Layout.alignment: Qt.AlignHCenter
        Layout.fillWidth: true
        Layout.maximumWidth: root.columns * Theme.s(240) + (root.columns - 1) * columnSpacing
        columns: root.columns
        columnSpacing: Theme.s(14)
        rowSpacing: Theme.s(14)

        Repeater {
            model: root.options
            Rectangle {
                id: option
                required property var modelData
                readonly property bool on: modelData.id === root.active
                objectName: "choice:" + modelData.id
                Layout.fillWidth: true
                Layout.preferredHeight: Theme.s(root.width < Theme.s(700) ? 120 : 140)
                radius: 16
                color: on ? Theme.gold : (mouse.pressed ? Theme.tilePress : Theme.tile)
                opacity: modelData.reachable ? 1 : 0.45
                border.color: activeFocus ? Theme.ink : "transparent"
                border.width: 2
                activeFocusOnTab: true
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData.name
                Accessible.checked: on
                Keys.onSpacePressed: panel.setAttrs(root.dev.id, { select: modelData.id })

                Behavior on color { ColorAnimation { duration: 150 } }

                LineIcon {
                    x: Theme.s(18)
                    y: Theme.s(18)
                    width: Theme.s(30)
                    height: Theme.s(30)
                    lineWidth: 1.3
                    name: option.on ? "radioOn" : "radioOff"
                    color: option.on ? Theme.goldInk : Theme.muted
                }
                Column {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: Theme.s(18)
                    anchors.bottomMargin: Theme.s(16)
                    spacing: 2
                    Text {
                        width: parent.width
                        text: option.modelData.name
                        elide: Text.ElideRight
                        font.pixelSize: Theme.s(19)
                        font.weight: Font.Medium
                        color: option.on ? Theme.goldInk : Theme.ink
                    }
                    Text {
                        text: !option.modelData.reachable ? qsTr("Not reachable") : option.on ? qsTr("On") : qsTr("Off")
                        font.pixelSize: Theme.s(15)
                        color: option.on ? Theme.goldInk : Theme.muted
                        opacity: option.on ? 0.72 : 1
                    }
                }
                MouseArea {
                    id: mouse
                    anchors.fill: parent
                    enabled: option.modelData.reachable
                    onClicked: panel.setAttrs(root.dev.id, { select: option.modelData.id })
                }
            }
        }
    }

    Item {
        Layout.fillHeight: true
    }

    ColumnLayout {
        visible: !!(root.dev.meta && root.dev.meta.allow_off)
        Layout.alignment: Qt.AlignHCenter
        spacing: 6
        CircleButton {
            objectName: "choiceOff"
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: Theme.s(68)
            implicitHeight: Theme.s(68)
            iconName: "power"
            iconSize: Theme.s(30)
            label: qsTr("All off")
            onClicked: panel.setAttrs(root.dev.id, { on: false })
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("All off")
            color: Theme.muted
            font.pixelSize: Theme.s(14)
        }
    }
}
