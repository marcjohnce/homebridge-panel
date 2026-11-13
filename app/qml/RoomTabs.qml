import QtQuick

ListView {
    id: tabs

    orientation: ListView.Horizontal
    spacing: 28
    implicitHeight: 44
    boundsBehavior: Flickable.StopAtBounds
    model: [""].concat(panel.rooms)

    delegate: UnderlineButton {
        required property string modelData
        text: modelData === "" ? qsTr("Alle") : modelData
        selected: panel.currentRoom === modelData
        onClicked: panel.selectRoom(modelData)
    }
}
