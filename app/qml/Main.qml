import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: window

    property string openDevice: ""
    property var sceneDraft: null      // the scene editor is open (panel.sceneDraft)
    property bool settingsOpen: false
    property bool idle: false
    property bool displayOff: false    // switched off some time after the screen saver started
    // After waking up every touch is swallowed for a moment: the display needs a while to light
    // up, and a second tap in the dark (or a bouncing finger) must not switch a tile blindly.
    property bool shielded: false

    // the first touch on the screen saver: wake up, keep touches away from the tiles for now
    function wake() {
        shielded = true;
        shieldTimer.interval = displayOff ? 2500 : 400;    // a display that was off: until it is on (see below)
        shieldTimer.restart();
        idle = false;
    }

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
        covered: window.openDevice !== "" || window.settingsOpen || !!window.sceneDraft || window.idle
        onEditScene: id => window.sceneDraft = panel.sceneDraft(id)
        onLightsOff: {
            const r = panel.lightsOff();
            toast.show(r.text, r.count > 0 ? qsTr("Undo") : "", () => panel.undoLightsOff());
        }
    }

    // below the detail view: a device of the scene is changed there
    Loader {
        anchors.fill: parent
        active: !!window.sceneDraft
        sourceComponent: SceneEditor {
            draft: window.sceneDraft
            detailOpen: window.openDevice !== ""
            onOpenDevice: id => window.openDevice = id
            onClosed: window.sceneDraft = null
        }
    }

    Loader {
        anchors.fill: parent
        active: window.openDevice !== ""
        sourceComponent: DetailSheet {
            deviceId: window.openDevice
            swipeEnabled: !window.sceneDraft        // from the scene editor: that one device only
            onClosed: window.openDevice = ""
            onSwitchTo: id => window.openDevice = id
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
            displayOff: window.displayOff
            onWoken: window.wake()
            onRunScene: (id, name) => {         // double tap: stays on the screen saver
                panel.runScene(id);
                toast.show(qsTr("Scene “%1”").arg(name));
            }
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
            window.sceneDraft = null;
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
        onTriggered: {
            window.displayOff = true;
            panel.setDisplayPower(false);
        }
    }
    onIdleChanged: if (!idle) panel.setDisplayPower(true)

    Timer {
        id: shieldTimer
        onTriggered: window.shielded = false
    }
    // swallows every touch while shielded; touching again keeps it up a little longer
    MouseArea {
        objectName: "wakeShield"
        anchors.fill: parent
        z: 1000
        enabled: window.shielded
        visible: window.shielded
        onPressed: shieldTimer.restart()
        onReleased: shieldTimer.restart()
    }

    Connections {
        target: panel
        function onUserActivity() {
            idleTimer.restart();
        }
        // the display is lit again: touches reach the tiles one second later
        function onDisplayPowered(on) {
            if (!on)
                return;
            window.displayOff = false;      // also after an alarm switched it on
            if (window.shielded) {
                shieldTimer.interval = 1000;
                shieldTimer.restart();
            }
        }
        function onToast(message) {
            toast.show(message);
        }
        // leak, glass break, smoke or CO: wake up, show "Security" and the message
        function onSecurityAlarm(message) {
            window.idle = false;
            window.openDevice = "";
            window.sceneDraft = null;
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
        function onWifiRequested() {
            wifiCode.show();
        }
        function onRestarting(message) {
            restartOverlay.message = message;
        }
    }

    OpenCloseConfirm {
        id: openCloseConfirm
        objectName: "openCloseDialog"
    }

    WifiCodeDialog {
        id: wifiCode
        objectName: "wifiDialog"
    }

    // spinner while a page is built or something is saved (Busy.run)
    BusyPopup {
        id: busyPopup
    }
}
