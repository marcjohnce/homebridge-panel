import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string deviceId
    property var dev: panel.device(deviceId)
    property bool busy: false
    signal closed

    readonly property bool isThermostat: dev.type === "thermostat"
    readonly property bool isSensor: dev.type === "sensor"
    readonly property bool isBlind: dev.type === "blind"
    readonly property bool heatingNow: isThermostat && dev.reachable && dev.state.heating

    color: Theme.page
    focus: true
    Keys.onEscapePressed: root.closed()

    // refresh() assigns dev directly, so follow device changes explicitly as well
    onDeviceIdChanged: {
        busy = false;
        dev = panel.device(deviceId);
    }

    function refresh() {
        if (busy)
            return;
        const d = panel.device(deviceId);
        if (d.id === undefined)
            root.closed();
        else
            dev = d;
    }
    function interactionStarted() {
        busy = true;
        settle.stop();
    }
    function interactionEnded() {
        settle.restart();
    }

    Timer {
        id: settle
        interval: 900
        onTriggered: {
            root.busy = false;
            root.refresh();
        }
    }

    Connections {
        target: panel
        function onDeviceUpdated(id) {
            if (id === root.deviceId)
                root.refresh();
        }
    }

    MouseArea {
        anchors.fill: parent
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 28
        anchors.rightMargin: 28
        anchors.topMargin: 18
        anchors.bottomMargin: 18
        spacing: 8

        BackHeader {
            Layout.fillWidth: true
            backText: root.dev.room || ""
            title: root.dev.name || ""
            note: !root.dev.reachable ? qsTr("Not reachable")
                : root.heatingNow ? qsTr("Heating now")
                : (root.isBlind && root.dev.state.obstructed) ? qsTr("Obstructed")
                : (root.isSensor && root.dev.meta && root.dev.meta.outdoor) ? qsTr("Outdoors") : ""
            noteColor: root.heatingNow ? Theme.heat2 : (root.isBlind && root.dev.state.obstructed) ? Theme.err : Theme.muted
            onBack: root.closed()
        }

        Loader {
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: root.isThermostat ? thermostatComponent : root.isSensor ? sensorComponent
                           : root.isBlind ? blindComponent : lightComponent
        }
    }

    Component {
        id: thermostatComponent
        ThermostatControl {
            dev: root.dev
            sheet: root
        }
    }
    Component {
        id: blindComponent
        BlindControl {
            dev: root.dev
            sheet: root
        }
    }
    Component {
        id: sensorComponent
        SensorView {
            dev: root.dev
        }
    }
    Component {
        id: lightComponent
        LightControl {
            dev: root.dev
            sheet: root
        }
    }
}
