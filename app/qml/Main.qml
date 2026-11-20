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
        property: "name"
        value: panel.theme
    }
    Binding {
        target: Theme
        property: "localeName"
        value: panel.localeName
    }
    Binding {
        target: Theme
        property: "dateFormat"
        value: panel.dateFormat
    }
    // 1.0 up to 1024×600 and on square/portrait screens; grows on larger landscape
    // screens (1280×800 → 1.25), capped at 1.3
    Binding {
        target: Theme
        property: "scale"
        value: Math.max(1, Math.min(1.3, window.width / 1024, window.height / 600))
    }

    // Upside down (Settings → Display): the whole window content including popups turns by 180°.
    // Qt maps touches and clicks through the rotation. Rotating here is much cheaper than
    // rotating the screen in the desktop, which then has to redraw every frame turned.
    property Item rootItem: null                 // the window's root item: popups turn too
    Component.onCompleted: {
        rootItem = contentItem.Window.contentItem;
        Busy.popup = busyPopup;
    }
    Binding {
        target: window.rootItem
        when: window.rootItem !== null
        property: "rotation"
        value: panel.upsideDown ? 180 : 0
    }

    HomeScreen {
        anchors.fill: parent
        onOpenDetail: id => window.openDevice = id
        onOpenSettings: Busy.run(qsTr("Loading settings …"), () => window.settingsOpen = true)
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
            objectName: "settingsPage"
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
        objectName: "toast"
    }

    // Shown while the app or the device restarts
    Rectangle {
        id: restartOverlay
        property string message
        anchors.fill: parent
        visible: message !== ""
        color: Theme.page
        Accessible.role: Accessible.AlertMessage
        Accessible.name: message

        Text {
            anchors.centerIn: parent
            text: restartOverlay.message
            color: Theme.ink
            font.pixelSize: Theme.s(24)
            font.weight: Font.Light
        }
        MouseArea {
            anchors.fill: parent
        }
    }

    Timer {
        id: idleTimer
        interval: Math.max(1, panel.idleSeconds) * 1000
        running: panel.idleSeconds > 0 && !window.idle
        onTriggered: {
            window.openDevice = "";
            window.settingsOpen = false;
            window.idle = true;
            panel.selectStart();      // after waking up: favorites (if any) or lights
        }
    }

    // display off some time after the screen saver started (Settings → Display); a touch ends
    // the screen saver and with it switches the display on again, as does an alarm
    Timer {
        id: displayOffTimer
        objectName: "displayOffTimer"
        interval: Math.max(1, panel.displayOffSeconds) * 1000
        running: window.idle && panel.displayOffSeconds > 0
        onTriggered: panel.setDisplayPower(false)
    }
    onIdleChanged: if (!idle) panel.setDisplayPower(true)

    Connections {
        target: panel
        function onUserActivity() {
            idleTimer.restart();
        }
        function onToast(message) {
            toast.show(message);
        }
        // leak, glass break, smoke or CO: wake up, show "Security" and the message
        function onSecurityAlarm(message) {
            window.idle = false;
            window.openDevice = "";
            window.settingsOpen = false;
            panel.selectCategory("security");
            panel.selectRoom("");               // the alarm may be in any room
            toast.show(message);
        }
        function onDetailRequested(id) {
            window.openDevice = id;
        }
        function onConfirmRequested(id) {
            openCloseConfirm.ask(id);
        }
        function onRestarting(message) {
            restartOverlay.message = message;
        }
    }

    OpenCloseConfirm {
        id: openCloseConfirm
        objectName: "openCloseDialog"
    }

    // spinner while a page is built or something is saved (Busy.run)
    BusyPopup {
        id: busyPopup
    }
}
