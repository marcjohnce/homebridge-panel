import QtQuick
import "Icons.js" as Icons

// "Scenes" menu: scenes of the selected room as tiles; tapping one runs it
GridView {
    id: grid
    objectName: "sceneGrid"

    readonly property int columns: Math.max(2, Math.floor(width / Theme.s(172)))
    readonly property bool showRooms: panel.currentRoom === ""

    model: panel.visibleScenes
    cellWidth: width / columns
    cellHeight: Math.max(118, Math.round(cellWidth * 5 / 6))
    boundsBehavior: Flickable.StopAtBounds
    clip: true
    layer.enabled: GraphicsInfo.api === GraphicsInfo.Software   // see TileGrid.qml

    Rectangle {
        parent: grid
        anchors.fill: parent
        z: -1
        visible: grid.layer.enabled
        color: Theme.page
    }

    delegate: Rectangle {
        id: tile
        required property var modelData
        required property int index
        property bool running: false
        readonly property int lastRowStart: Math.floor((grid.count - 1) / grid.columns) * grid.columns

        objectName: "scene:" + modelData.id
        width: grid.cellWidth - 2
        height: grid.cellHeight - 2
        topLeftRadius: index === 0 ? 14 : 0
        topRightRadius: index === Math.min(grid.columns, grid.count) - 1 ? 14 : 0
        bottomLeftRadius: index === lastRowStart ? 14 : 0
        bottomRightRadius: (index === grid.count - 1 || (index === lastRowStart - 1 && grid.count % grid.columns !== 0)) ? 14 : 0
        color: running ? Theme.gold : (mouse.pressed ? Theme.tilePress : Theme.tile)
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: qsTr("Run scene %1").arg(modelData.name)
        Keys.onReturnPressed: run()
        Keys.onSpacePressed: run()

        Behavior on color { ColorAnimation { duration: 200 } }

        function run() {
            panel.runScene(modelData.id);
            running = true;
            flash.restart();
        }
        Timer {
            id: flash
            interval: 900
            onTriggered: tile.running = false
        }

        LineIcon {
            x: Theme.s(18)
            y: Theme.s(18)
            width: Theme.s(34)
            height: Theme.s(34)
            lineWidth: 1.15
            name: Icons.has(tile.modelData.icon) ? tile.modelData.icon : "power"
            color: tile.running ? Theme.goldInk : Theme.muted
        }
        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: Theme.s(18)
            anchors.bottomMargin: Theme.s(16)
            spacing: 2
            Text {
                visible: grid.showRooms
                width: parent.width
                text: tile.modelData.room || qsTr("Whole house")
                elide: Text.ElideRight
                font.pixelSize: Theme.s(13)
                color: tile.running ? Theme.goldInk : Theme.muted
            }
            Text {
                width: parent.width
                text: tile.modelData.name
                elide: Text.ElideRight
                maximumLineCount: grid.showRooms ? 1 : 2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.s(17)
                font.weight: Font.Medium
                color: tile.running ? Theme.goldInk : Theme.ink
            }
            Text {
                width: parent.width
                text: tile.modelData.count === 1 ? qsTr("1 device") : qsTr("%1 devices").arg(tile.modelData.count)
                font.pixelSize: Theme.s(14)
                color: tile.running ? Theme.goldInk : Theme.muted
            }
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: 3
            radius: 10
            color: "transparent"
            border.color: tile.running ? Theme.goldInk : Theme.gold
            border.width: 2
            visible: tile.activeFocus
        }
        MouseArea {
            id: mouse
            anchors.fill: parent
            onClicked: tile.run()
        }
    }

    Text {
        anchors.centerIn: parent
        width: parent.width * 0.8
        visible: grid.count === 0
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: qsTr("No scenes here. Scenes are set up in config.yaml.")
        color: Theme.muted
        font.pixelSize: Theme.s(18)
    }
}
