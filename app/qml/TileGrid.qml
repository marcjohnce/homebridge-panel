import QtQuick

GridView {
    id: grid
    objectName: "tileGrid"

    signal openDetail(string id)

    readonly property int columns: Math.max(2, Math.floor(width / 172))
    readonly property bool showRooms: panel.currentRoom === "" && panel.rooms.length > 1

    model: panel.devices
    cellWidth: width / columns
    cellHeight: Math.max(118, Math.round(cellWidth * 5 / 6))
    boundsBehavior: Flickable.StopAtBounds
    clip: true
    keyNavigationEnabled: true

    delegate: DeviceTile {
        width: grid.cellWidth - 2
        height: grid.cellHeight - 2
        columns: grid.columns
        count: grid.count
        showRoom: grid.showRooms
        onOpenDetail: id => grid.openDetail(id)
    }

    Text {
        anchors.centerIn: parent
        width: parent.width * 0.8
        visible: grid.count === 0
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: qsTr("No devices yet. Enter your Homebridge address, port and PIN in Settings.")
        color: Theme.muted
        font.pixelSize: 18
    }
}
