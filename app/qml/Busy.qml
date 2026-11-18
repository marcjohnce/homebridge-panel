pragma Singleton
import QtQuick

// Busy.run(text, fn): runs fn (building a page, saving) with visible feedback – see BusyPopup.
// Main.qml sets the popup.
QtObject {
    property var popup: null

    function run(text, fn) {
        if (popup)
            popup.run(text, fn);
        else
            fn();
    }
}
