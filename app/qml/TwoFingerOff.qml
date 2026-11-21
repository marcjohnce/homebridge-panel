import QtQuick

// Two fingers down over the tiles: the lights of the selected room off (every room under
// "All" and Favorites); the message offers to undo it.
DragHandler {
    id: root

    property real lastDy: 0
    signal lightsOff

    target: null
    minimumPointCount: 2
    maximumPointCount: 2
    xAxis.enabled: false
    yAxis.enabled: true

    onActiveTranslationChanged: if (active) lastDy = activeTranslation.y
    onActiveChanged: {
        if (active)
            lastDy = 0;
        else if (lastDy > Theme.s(90))
            root.lightsOff();
    }
}
