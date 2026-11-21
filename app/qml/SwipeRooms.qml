import QtQuick

// Swipe left / right over the tiles: next / previous room tab ("All" comes last).
// Not under Favorites, which has no room tabs.
HSwipe {
    readonly property var tabs: panel.rooms.concat([""])

    onSwiped: step => {
        const i = tabs.indexOf(panel.currentRoom);
        const j = Math.max(0, Math.min(tabs.length - 1, i + step));
        if (i >= 0 && j !== i)
            panel.selectRoom(tabs[j]);
    }
}
