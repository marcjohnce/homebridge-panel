import QtQuick

ListView {
    id: tabs
    objectName: "roomTabs"

    orientation: ListView.Horizontal
    spacing: Theme.s(28)
    implicitHeight: Theme.s(44)
    boundsBehavior: Flickable.StopAtBounds
    model: [""].concat(panel.rooms)

    delegate: UnderlineButton {
        required property string modelData
        text: modelData === "" ? qsTr("All") : modelData
        selected: panel.currentRoom === modelData
        onClicked: panel.selectRoom(modelData)
    }
}
