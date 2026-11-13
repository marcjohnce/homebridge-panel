import QtQuick

GridView {
    id: grid
    objectName: "tileGrid"

    signal openDetail(string id)

    readonly property int columns: Math.max(2, Math.floor(width / Theme.s(172)))
    readonly property bool showRooms: panel.currentRoom === "" && panel.rooms.length > 1

    model: panel.devices
    cellWidth: width / columns
    // Tiles are 6:5. If the rows almost fit on screen, flatten the tiles slightly (max. 15%)
    // so that only whole rows are visible, e.g. three rows on 720×720.
    readonly property real naturalHeight: Math.round(cellWidth * 5 / 6)
    readonly property int rowsNeeded: Math.ceil(count / columns)
    readonly property int rowsFit: Math.max(1, Math.round(height / naturalHeight))
    readonly property bool fitRows: rowsNeeded * naturalHeight > height && height / rowsFit >= naturalHeight * 0.85
    cellHeight: Math.max(118, fitRows ? Math.floor(height / rowsFit) : naturalHeight)
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
        font.pixelSize: Theme.s(18)
    }
}
