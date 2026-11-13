import QtQuick

// Runder Knopf mit Linien-Symbol (−/+, Ein/Aus)
Rectangle {
    id: root

    property string iconName: "plus"
    property string label
    property bool highlighted: false
    property real iconSize: 26
    signal clicked

    implicitWidth: 64
    implicitHeight: 64
    radius: width / 2
    color: mouse.pressed ? Theme.tilePress : Theme.tile
    border.color: highlighted ? Theme.gold : (activeFocus ? Theme.gold : "transparent")
    border.width: highlighted ? 1.5 : 2

    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: label
    Accessible.checked: highlighted
    Keys.onSpacePressed: root.clicked()
    Keys.onReturnPressed: root.clicked()

    LineIcon {
        anchors.centerIn: parent
        width: root.iconSize
        height: root.iconSize
        lineWidth: 1.5
        name: root.iconName
        color: root.highlighted ? Theme.gold : Theme.ink
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        onClicked: root.clicked()
    }
}
