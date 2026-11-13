import QtQuick

Rectangle {
    id: root

    property string text
    property bool primary: false
    signal clicked

    implicitWidth: label.implicitWidth + 44
    implicitHeight: 48
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

    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        color: root.primary ? Theme.goldInk : Theme.ink
        font.pixelSize: 16
        font.weight: root.primary ? Font.Medium : Font.Normal
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        onClicked: root.clicked()
    }
}
