import QtQuick

// Swipe left / right over the tiles: next / previous room tab ("All" comes last).
// Not under Favorites, which has no room tabs.
DragHandler {
    id: root

    property real lastDx: 0
    readonly property var tabs: panel.rooms.concat([""])

    function step(delta) {
        const i = tabs.indexOf(panel.currentRoom);
        const j = Math.max(0, Math.min(tabs.length - 1, i + delta));
        if (i >= 0 && j !== i)
            panel.selectRoom(tabs[j]);
    }

    target: null
    xAxis.enabled: true
    yAxis.enabled: false
    enabled: panel.category !== "favorites" && panel.rooms.length > 0

    onActiveTranslationChanged: if (active) lastDx = activeTranslation.x
    onActiveChanged: {
        if (active) {
            lastDx = 0;
        } else if (Math.abs(lastDx) > Theme.s(70)) {
            step(lastDx < 0 ? 1 : -1);      // finger to the left: next room
        }
    }
}
