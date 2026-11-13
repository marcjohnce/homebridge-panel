import QtQuick

Rectangle {
    id: root

    property string text
    property bool primary: false
    property string iconName          // optional line icon before the text
    signal clicked

    implicitWidth: content.implicitWidth + Theme.s(iconName !== "" ? 36 : 44)
    implicitHeight: Theme.s(48)
    radius: 24
    color: primary ? (mouse.pressed ? Qt.darker(Theme.gold, 1.1) : Theme.gold) : (mouse.pressed ? Theme.tilePress : "transparent")
    border.color: activeFocus ? Theme.ink : (primary ? Theme.gold : Theme.line)
    border.width: activeFocus ? 2 : 1
    opacity: enabled ? 1 : 0.4

    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: text
    Keys.onReturnPressed: if (enabled) root.clicked()
    Keys.onSpacePressed: if (enabled) root.clicked()

    Row {
        id: content
        anchors.centerIn: parent
        spacing: 8
        LineIcon {
            visible: root.iconName !== ""
            anchors.verticalCenter: parent.verticalCenter
            width: Theme.s(22)
            height: Theme.s(22)
            name: root.iconName || "power"
            color: root.primary ? Theme.goldInk : Theme.muted
        }
        Text {
            id: label
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            color: root.primary ? Theme.goldInk : Theme.ink
            font.pixelSize: Theme.s(16)
            font.weight: root.primary ? Font.Medium : Font.Normal
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        onClicked: root.clicked()
    }
}
