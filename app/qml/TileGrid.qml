import QtQuick

GridView {
    id: grid
    objectName: "tileGrid"

    signal openDetail(string id)

    readonly property int columns: Math.max(2, Math.floor(width / Theme.s(172)))
    readonly property bool showRooms: panel.currentRoom === "" && panel.rooms.length > 1

    model: panel.devices
    cellWidth: width / columns
    // Tiles are 6:5. If the rows almost fit on screen, flatten the tiles slightly (max. 15%,
    // and never below 160 px × scale) so that only whole rows are visible, e.g. three rows on 720×720.
    readonly property real naturalHeight: Math.round(cellWidth * 5 / 6)
    readonly property int rowsNeeded: Math.ceil(count / columns)
    readonly property int rowsFit: Math.max(1, Math.round(height / naturalHeight))
    readonly property bool fitRows: rowsNeeded * naturalHeight > height && height / rowsFit >= naturalHeight * 0.85
                                    && height / rowsFit >= Theme.s(160)
    cellHeight: Math.max(118, fitRows ? Math.floor(height / rowsFit) : naturalHeight)
    boundsBehavior: Flickable.StopAtBounds
    clip: true
    // The software renderer does not clip vector icons (Shape) at the edge of a scroll area;
    // rendering into a layer cuts them off. Not needed with GPU rendering.
    layer.enabled: GraphicsInfo.api === GraphicsInfo.Software

    // opaque background for the layer above (transparent layers render black in software mode)
    Rectangle {
        parent: grid
        anchors.fill: parent
        z: -1
        visible: grid.layer.enabled
        color: Theme.page
    }

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
        text: panel.deviceCount === 0 ? qsTr("No devices yet. Enter your Homebridge address, port and PIN in Settings.")
            : panel.category === "light" ? qsTr("No lights, switches or blinds here.")
            : panel.category === "climate" ? qsTr("No heating or climate sensors here.")
            : qsTr("No window, door, contact, glass break or leak sensors here.")
        color: Theme.muted
        font.pixelSize: Theme.s(18)
    }
}
