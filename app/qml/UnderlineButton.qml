import QtQuick

// Text button with a gold line under the active choice (rooms, modes, options)
Item {
    id: root

    property string text
    property bool selected: false
    property int pixelSize: Theme.s(18)
    property bool centered: false
    signal clicked

    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight + Theme.s(18)
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.checked: selected
    Keys.onSpacePressed: root.clicked()
    Keys.onReturnPressed: root.clicked()

    Text {
        id: label
        y: 6
        anchors.horizontalCenter: root.centered ? parent.horizontalCenter : undefined
        text: root.text
        color: root.selected ? Theme.ink : Theme.muted
        font.pixelSize: root.pixelSize
    }

    Rectangle {
        x: root.centered ? (root.width - width) / 2 : 0
        anchors.bottom: parent.bottom
        width: 22
        height: 2
        radius: 1
        color: Theme.gold
        visible: root.selected
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: -4
        radius: 6
        color: "transparent"
        border.color: Theme.gold
        border.width: 2
        visible: root.activeFocus
    }

    MouseArea {
        anchors.fill: parent
        anchors.margins: -8
        onClicked: root.clicked()
    }
}
