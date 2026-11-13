import QtQuick
import "Icons.js" as Icons

Item {
    id: root

    property string sceneId
    property string label
    property string iconName
    property bool compact: false
    property bool running: false

    implicitHeight: compact ? 42 : 48
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: qsTr("Szene %1 ausführen").arg(label)
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
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: root.running ? Theme.goldSoft : "transparent" }
            GradientStop { position: 0.8; color: "transparent" }
        }
    }

    LineIcon {
        anchors.verticalCenter: parent.verticalCenter
        x: 2
        width: 22
        height: 22
        name: Icons.has(root.iconName) ? root.iconName : "power"
        color: root.running || mouse.pressed ? Theme.gold : Theme.muted
    }
    Text {
        anchors.verticalCenter: parent.verticalCenter
        x: 38
        text: root.label
        color: Theme.ink
        font.pixelSize: 17
    }
    Rectangle {
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
        radius: 6
        visible: root.activeFocus
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        onClicked: root.run()
    }
}
