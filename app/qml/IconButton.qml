import QtQuick

// Flat square button with a line icon, for rows inside a tile (move, rename, delete)
Item {
    id: root

    property string iconName
    property string label
    signal clicked

    implicitWidth: Theme.s(48)
    implicitHeight: Theme.s(48)
    opacity: enabled ? 1 : 0.3
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: label
    Keys.onSpacePressed: root.clicked()
    Keys.onReturnPressed: root.clicked()

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: mouse.pressed ? Theme.tilePress : "transparent"
        border.color: Theme.gold
        border.width: root.activeFocus ? 2 : 0
    }
    LineIcon {
        anchors.centerIn: parent
        width: Theme.s(22)
        height: Theme.s(22)
        lineWidth: 1.5
        name: root.iconName
        color: Theme.ink
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        onClicked: root.clicked()
    }
}
