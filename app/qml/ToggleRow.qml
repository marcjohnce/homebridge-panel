import QtQuick

// Label and help on the left, switch on the right
Item {
    id: row
    property string label
    property string help
    property bool checked
    property string toggleName
    signal toggled

    height: Math.max(Theme.s(52), texts.implicitHeight + 8)

    Column {
        id: texts
        anchors.left: parent.left
        anchors.right: toggle.left
        anchors.rightMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        Text {
            width: parent.width
            text: row.label
            color: Theme.ink
            font.pixelSize: Theme.s(16)
            wrapMode: Text.WordWrap
        }
        Text {
            width: parent.width
            text: row.help
            color: Theme.muted
            font.pixelSize: Theme.s(13)
            wrapMode: Text.WordWrap
        }
    }
    Rectangle {
        id: toggle
        objectName: row.toggleName
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: Theme.s(54)
        height: Theme.s(32)
        radius: height / 2
        color: row.checked ? Theme.gold : Theme.line
        border.color: activeFocus ? Theme.ink : "transparent"
        border.width: 2
        activeFocusOnTab: true
        Accessible.role: Accessible.CheckBox
        Accessible.name: row.label
        Accessible.checked: row.checked
        Keys.onSpacePressed: row.toggled()

        Behavior on color { ColorAnimation { duration: 150 } }

        Rectangle {
            width: parent.height - 6
            height: parent.height - 6
            radius: height / 2
            y: 3
            x: row.checked ? parent.width - width - 3 : 3
            color: Theme.knob
            Behavior on x { NumberAnimation { duration: 150 } }
        }
        MouseArea {
            anchors.fill: parent
            anchors.margins: -8
            onClicked: row.toggled()
        }
    }
}
