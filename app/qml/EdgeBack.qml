import QtQuick

// Swipe in from the left edge: back, like the back button of the page. A round arrow follows
// the finger and turns gold once letting go goes back.
Item {
    id: root
    objectName: "edgeBack"

    signal back
    readonly property real distance: Theme.s(90)
    readonly property real pulled: drag.active ? Math.max(0, drag.activeTranslation.x) : 0

    anchors.left: parent.left
    anchors.top: parent.top
    anchors.bottom: parent.bottom
    width: Theme.s(26)
    z: 100

    DragHandler {
        id: drag
        target: null
        xAxis.enabled: true
        yAxis.enabled: false
        property real lastDx: 0
        onActiveTranslationChanged: if (active) lastDx = activeTranslation.x
        onActiveChanged: {
            if (active)
                lastDx = 0;
            else if (lastDx > root.distance)
                root.back();
        }
    }

    Rectangle {
        visible: drag.active
        width: Theme.s(48)
        height: width
        radius: width / 2
        x: Math.min(root.pulled, root.distance) - width / 2
        y: drag.centroid.position.y - height / 2
        color: root.pulled > root.distance ? Theme.gold : Theme.tile
        border.color: Theme.line
        opacity: Math.min(1, root.pulled / root.distance + 0.3)
        LineIcon {
            anchors.centerIn: parent
            width: Theme.s(24)
            height: width
            name: "back"
            color: root.pulled > root.distance ? Theme.goldInk : Theme.ink
        }
    }
}
