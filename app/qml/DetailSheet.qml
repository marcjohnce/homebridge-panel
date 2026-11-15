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
    readonly property bool isChoice: !!(dev.meta && dev.meta.choice)
    readonly property bool isAlarm: dev.type === "alarm"
    readonly property bool isValve: dev.type === "valve"
    readonly property bool isTv: dev.type === "tv"
    readonly property bool isSpeaker: dev.type === "speaker"
    readonly property bool isPurifier: dev.type === "purifier"
    readonly property bool isHumidifier: dev.type === "humidifier"
    readonly property bool heatingNow: isThermostat && dev.reachable && dev.state.heating
    // temperature chart from the Eve history of the device
    readonly property bool hasHistory: !!(dev.meta && dev.meta.history)
    property bool showHistory: false

    color: Theme.page
    focus: true
    Keys.onEscapePressed: root.closed()

    // refresh() assigns dev directly, so follow device changes explicitly as well
    onDeviceIdChanged: {
        busy = false;
        showHistory = false;
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
                : root.dev.batteryLow ? qsTr("%1 – replace soon").arg(root.dev.batteryText)
                : root.heatingNow ? qsTr("Heating now")
                : (root.isBlind && root.dev.state.obstructed) ? qsTr("Obstructed")
                : (root.isSensor && root.dev.meta && root.dev.meta.outdoor) ? qsTr("Outdoors") : ""
            noteColor: root.dev.reachable && root.dev.batteryLow ? Theme.err : root.heatingNow ? Theme.heat2 : (root.isBlind && root.dev.state.obstructed) ? Theme.err : Theme.muted
            onBack: root.closed()
        }

        Row {
            visible: root.hasHistory
            spacing: Theme.s(28)
            UnderlineButton {
                objectName: "detailNow"
                text: qsTr("Now")
                selected: !root.showHistory
                onClicked: root.showHistory = false
            }
            UnderlineButton {
                objectName: "detailHistory"
                text: qsTr("History")
                selected: root.showHistory
                onClicked: root.showHistory = true
            }
        }

        Loader {
            Layout.fillWidth: true
            Layout.fillHeight: true
            sourceComponent: root.hasHistory && root.showHistory ? historyComponent
                           : root.isAlarm ? alarmComponent : root.isValve ? valveComponent
                           : root.isTv ? tvComponent : root.isSpeaker ? speakerComponent
                           : root.isPurifier ? purifierComponent : root.isHumidifier ? humidifierComponent : root.isChoice ? choiceComponent
                           : root.isThermostat ? thermostatComponent : root.isSensor ? sensorComponent
                           : root.isBlind ? blindComponent : lightComponent
        }
    }

    Component {
        id: historyComponent
        HistoryChart {
            deviceId: root.deviceId
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
        id: speakerComponent
        SpeakerControl {
            dev: root.dev
            sheet: root
        }
    }
    Component {
        id: purifierComponent
        PurifierControl {
            dev: root.dev
            sheet: root
        }
    }
    Component {
        id: humidifierComponent
        HumidifierControl {
            dev: root.dev
        }
    }
    Component {
        id: tvComponent
        TvControl {
            dev: root.dev
        }
    }
    Component {
        id: valveComponent
        ValveControl {
            dev: root.dev
        }
    }
    Component {
        id: alarmComponent
        AlarmControl {
            dev: root.dev
        }
    }
    Component {
        id: choiceComponent
        ChoiceControl {
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
