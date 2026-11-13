import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: window

    property string openDevice: ""
    property bool settingsOpen: false
    property bool idle: false

    width: initialWidth
    height: initialHeight
    visible: true
    visibility: panel.fullscreen ? Window.FullScreen : Window.Windowed
    title: qsTr("Smart Home Panel")
    color: Theme.page
    font.family: Theme.fontFamily
    font.pixelSize: 16

    Binding {
        target: Theme
        property: "dark"
        value: panel.theme === "dark"
    }

    HomeScreen {
        anchors.fill: parent
        onOpenDetail: id => window.openDevice = id
        onOpenSettings: window.settingsOpen = true
    }

    Loader {
        anchors.fill: parent
        active: window.openDevice !== ""
        sourceComponent: DetailSheet {
            deviceId: window.openDevice
            onClosed: window.openDevice = ""
        }
    }

    Loader {
        anchors.fill: parent
        active: window.settingsOpen
        sourceComponent: SettingsPage {
            onClosed: window.settingsOpen = false
        }
    }

    Loader {
        anchors.fill: parent
        active: window.idle
        sourceComponent: IdleScreen {
            onWoken: window.idle = false
        }
    }

    Toast {
        id: toast
    }

    Timer {
        id: idleTimer
        interval: Math.max(1, panel.idleSeconds) * 1000
        running: panel.idleSeconds > 0 && !window.idle
        onTriggered: {
            window.openDevice = "";
            window.settingsOpen = false;
            window.idle = true;
        }
    }

    Connections {
        target: panel
        function onUserActivity() {
            idleTimer.restart();
        }
        function onToast(message) {
            toast.show(message);
        }
    }
}
