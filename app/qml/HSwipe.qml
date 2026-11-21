import QtQuick

// A horizontal swipe: swiped(+1) when the finger moves to the left (next), swiped(-1) to the
// right (previous). Controls that drag themselves (sliders, dials) keep their touches.
DragHandler {
    id: root

    property real distance: Theme.s(70)
    property real lastDx: 0
    signal swiped(int step)

    target: null
    maximumPointCount: 1
    xAxis.enabled: true
    yAxis.enabled: false

    onActiveTranslationChanged: if (active) lastDx = activeTranslation.x
    onActiveChanged: {
        if (active)
            lastDx = 0;
        else if (Math.abs(lastDx) > distance)
            swiped(lastDx < 0 ? 1 : -1);
    }
}
