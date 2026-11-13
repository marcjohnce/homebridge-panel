import QtQuick
import "Icons.js" as Icons

// Runs a scene. List row in the sidebar, or a rounded chip in the top bar (chip: true).
Item {
    id: root

    property string sceneId
    property string label
    property string iconName
    property bool compact: false
    property bool chip: false
    property bool running: false

    readonly property real iconX: chip ? 14 : 2
    readonly property real textX: chip ? 44 : 38

    implicitWidth: textX + labelText.implicitWidth + (chip ? 18 : 0)
    implicitHeight: chip ? 44 : (compact ? 42 : 48)
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: qsTr("Run scene %1").arg(label)
    Keys.onReturnPressed: run()

    function run() {
        panel.runScene(sceneId);
        running = true;
        flash.restart();
    }

    Timer {
        id: flash
        interval: 900
        onTriggered: root.running = false
    }

    Rectangle {
        visible: !root.chip
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: root.running ? Theme.goldSoft : "transparent" }
            GradientStop { position: 0.8; color: "transparent" }
        }
    }

    Rectangle {
        visible: root.chip
        anchors.fill: parent
        radius: height / 2
        color: root.running ? Theme.goldSoft : (mouse.pressed ? Theme.tilePress : "transparent")
        border.color: Theme.line
        border.width: 1
    }

    LineIcon {
        anchors.verticalCenter: parent.verticalCenter
        x: root.iconX
        width: 22
        height: 22
        name: Icons.has(root.iconName) ? root.iconName : "power"
        color: root.running || mouse.pressed ? Theme.gold : Theme.muted
    }
    Text {
        id: labelText
        anchors.verticalCenter: parent.verticalCenter
        x: root.textX
        text: root.label
        color: Theme.ink
        font.pixelSize: root.chip ? 16 : 17
    }
    Rectangle {
        visible: !root.chip
        anchors.bottom: parent.bottom
        width: parent.width
        height: 1
        color: Theme.line
    }
    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.color: Theme.gold
        border.width: 2
        radius: root.chip ? height / 2 : 6
        visible: root.activeFocus
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        onClicked: root.run()
    }
}
