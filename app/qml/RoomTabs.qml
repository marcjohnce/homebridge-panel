import QtQuick

ListView {
    id: tabs
    objectName: "roomTabs"

    orientation: ListView.Horizontal
    spacing: Theme.s(28)
    implicitHeight: Theme.s(44)
    boundsBehavior: Flickable.StopAtBounds
    clip: true
    // The software renderer does not clip vector icons (Shape) at the edge of a scroll area;
    // rendering into a layer cuts them off. Not needed with GPU rendering.
    layer.enabled: GraphicsInfo.api === GraphicsInfo.Software

    // opaque background for the layer above (transparent layers render black in software mode)
    Rectangle {
        parent: tabs
        anchors.fill: parent
        z: -1
        visible: tabs.layer.enabled
        color: Theme.page
    }

    model: panel.rooms.concat([""])      // "All" comes last

    // a room chosen by swiping over the tiles: bring its tab into view
    function showCurrent() {
        const i = model.indexOf(panel.currentRoom);
        if (i >= 0)
            positionViewAtIndex(i, ListView.Contain);
    }
    Connections {
        target: panel
        function onCurrentRoomChanged() {
            Qt.callLater(tabs.showCurrent);
        }
    }

    delegate: UnderlineButton {
        required property string modelData
        text: modelData === "" ? qsTr("All") : modelData
        selected: panel.currentRoom === modelData
        mark: panel.roomMarks[modelData] ?? ""
        onClicked: panel.selectRoom(modelData)
    }
}
