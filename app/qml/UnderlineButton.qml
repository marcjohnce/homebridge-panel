import QtQuick

// Text button with a gold line under the active choice (rooms, modes, options)
Item {
    id: root

    property string text
    property bool selected: false
    property int pixelSize: Theme.s(18)
    property bool centered: false
    // dot before the text: "alert" (red, open window or alarm) or "on" (accent, lights on)
    property string mark: ""
    readonly property int dotSpace: mark !== "" ? Theme.s(16) : 0
    signal clicked

    implicitWidth: label.implicitWidth + dotSpace
    implicitHeight: label.implicitHeight + Theme.s(18)
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: mark === "alert" ? qsTr("%1, security warning").arg(text)
                     : mark === "on" ? qsTr("%1, lights on").arg(text) : text
    Accessible.checked: selected
    Keys.onSpacePressed: root.clicked()
    Keys.onReturnPressed: root.clicked()

    Rectangle {
        x: label.x - root.dotSpace
        anchors.verticalCenter: label.verticalCenter
        width: Theme.s(9)
        height: width
        radius: width / 2
        color: root.mark === "alert" ? Theme.err : Theme.gold
        visible: root.mark !== ""
    }

    Text {
        id: label
        y: 6
        x: root.centered ? (root.width - width + root.dotSpace) / 2 : root.dotSpace
        text: root.text
        color: root.selected ? Theme.ink : Theme.muted
        font.pixelSize: root.pixelSize
    }

    Rectangle {
        x: label.x
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
