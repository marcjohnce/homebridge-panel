import QtQuick

// Grid tile: tap toggles, "›" or a long press opens the detail view
Rectangle {
    id: root

    required property int index
    required property string deviceId
    required property string shortName
    required property string room
    required property string type
    required property string icon
    required property bool isOn
    property bool flashing: false        // a scene tile right after it was run
    readonly property bool lit: isOn || flashing
    required property bool reachable
    required property bool heating
    required property string stateText
    required property bool hasDetail
    required property real targetTemp
    required property real minTemp
    required property real maxTemp
    required property bool modeOff
    required property int alertLevel     // security: 2 alarm, 1 open / motion
    required property bool warning       // sensors: bad air quality or high CO₂
    required property bool batteryLow    // battery below 10 % or reported as low
    required property string adjustKind  // hold and drag: "brightness", "position" or ""
    required property int level          // brightness (0 when off) or blind position

    property bool showRoom: false
    property int columns: 4
    property int count: 1
    signal openDetail(string id)

    readonly property bool thermostat: type === "thermostat"
    readonly property bool sensor: type === "sensor"
    readonly property bool security: type === "security"
    readonly property bool alarm: alertLevel === 2
    readonly property color ink: lit ? Theme.goldInk : alarm ? Theme.alarmInk : Theme.ink
    readonly property color sub: lit ? Theme.goldInk : alarm ? Theme.alarmInk : Theme.muted

    objectName: "tile:" + deviceId
    readonly property int lastRowStart: Math.floor((count - 1) / columns) * columns
    readonly property real cornerRadius: 14

    topLeftRadius: index === 0 ? cornerRadius : 0
    topRightRadius: index === Math.min(columns, count) - 1 ? cornerRadius : 0
    bottomLeftRadius: index === lastRowStart ? cornerRadius : 0
    bottomRightRadius: (index === count - 1 || (index === lastRowStart - 1 && count % columns !== 0)) ? cornerRadius : 0
    color: adjusting ? Theme.tile : lit ? Theme.gold : alarm ? Theme.alarm : (mouse.pressed ? Theme.tilePress : Theme.tile)
    opacity: reachable ? 1 : 0.45

    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: batteryLow ? qsTr("%1: %2, battery almost empty").arg(shortName).arg(stateText)
                                : qsTr("%1: %2").arg(shortName).arg(stateText)
    Accessible.checkable: !thermostat && !sensor && !security && type !== "scene"
    Accessible.checked: isOn
    Keys.onSpacePressed: activate()
    Keys.onReturnPressed: activate()

    Behavior on color { ColorAnimation { duration: 200 } }

    function activate() {
        if (type === "scene") {         // a scene among the favorites: run it
            panel.toggle(deviceId);
            flashing = true;
            flash.restart();
            return;
        }
        if (security || type === "value")
            return;                  // read-only
        if (thermostat || sensor || type === "alarm")     // alarm system: choose the mode in the detail view
            root.openDetail(deviceId);
        else
            panel.toggle(deviceId);
    }

    Timer {
        id: flash
        interval: 900
        onTriggered: root.flashing = false
    }

    // Hold, then drag up or down: brightness or blind position, set when letting go. Holding
    // without moving opens the detail view, as before.
    property bool adjusting: false
    property bool adjusted: false
    property real adjustValue: 0
    property real adjustStartY: 0
    property real adjustStart: 0

    MouseArea {
        id: mouse
        anchors.fill: parent
        onClicked: root.activate()
        onPressAndHold: mouse => {
            if (root.adjustKind === "") {
                if (root.hasDetail)
                    root.openDetail(root.deviceId);
                return;
            }
            preventStealing = true;             // the grid must not scroll, no swipe to the next room
            root.adjusting = true;
            root.adjusted = false;
            root.adjustStartY = mouse.y;
            root.adjustStart = root.level;
            root.adjustValue = root.level;
        }
        onPositionChanged: mouse => {
            if (!root.adjusting)
                return;
            const dy = root.adjustStartY - mouse.y;
            if (Math.abs(dy) > 6)
                root.adjusted = true;
            root.adjustValue = Math.round(Math.max(0, Math.min(100, root.adjustStart + dy / (root.height * 1.2) * 100)));
        }
        onReleased: {
            if (!root.adjusting)
                return;
            preventStealing = false;
            root.adjusting = false;
            const v = root.adjustValue;
            if (!root.adjusted) {
                if (root.hasDetail)
                    root.openDetail(root.deviceId);
            } else if (root.adjustKind === "position") {
                panel.setAttrs(root.deviceId, { position: v });
            } else {
                panel.setAttrs(root.deviceId, v > 0 ? { on: true, brightness: v } : { on: false });
            }
        }
        onCanceled: {
            preventStealing = false;
            root.adjusting = false;
        }
    }

    // the value while dragging: a level rising from the bottom and the percentage
    Rectangle {
        objectName: "adjust:" + root.deviceId
        visible: root.adjusting
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: parent.height * root.adjustValue / 100
        color: Qt.rgba(Theme.gold.r, Theme.gold.g, Theme.gold.b, 0.55)
        bottomLeftRadius: root.bottomLeftRadius
        bottomRightRadius: root.bottomRightRadius
    }
    Text {
        visible: root.adjusting
        anchors.centerIn: parent
        text: root.adjustKind === "position" ? qsTr("%1 % open").arg(root.adjustValue) : root.adjustValue + " %"
        color: Theme.ink
        font.pixelSize: Theme.s(30)
        font.weight: Font.Light
    }

    LineIcon {
        x: Theme.s(18)
        y: Theme.s(18)
        width: Theme.s(34)
        height: Theme.s(34)
        lineWidth: 1.15
        visible: !root.thermostat && root.icon !== "none"     // virtual devices can go without an icon
        name: root.icon
        color: root.alertLevel === 1 ? Theme.err : root.sub
    }

    Item {
        visible: root.thermostat
        x: Theme.s(12)
        y: Theme.s(12)
        width: root.height < Theme.s(136) ? Theme.s(52) : Theme.s(58)
        height: width

        ArcGauge {
            anchors.fill: parent
            from: root.minTemp
            to: root.maxTemp
            value: root.targetTemp
            active: !root.modeOff && root.reachable
            lineWidth: 3
        }
        Text {
            anchors.centerIn: parent
            text: Theme.fmt(root.targetTemp)
            color: Theme.ink
            font.pixelSize: parent.width < Theme.s(56) ? Theme.s(15) : Theme.s(17)
            font.weight: Font.Light
        }
    }

    Column {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Theme.s(18)
        anchors.bottomMargin: Theme.s(16)
        spacing: 2

        Text {
            visible: root.showRoom
            width: parent.width
            text: root.room
            elide: Text.ElideRight
            font.pixelSize: Theme.s(13)
            color: root.sub
            opacity: root.lit || root.alarm ? 0.72 : 1
        }
        Text {
            width: parent.width
            text: root.shortName
            elide: Text.ElideRight
            maximumLineCount: root.showRoom ? 1 : 2       // keep clear of the icon
            wrapMode: Text.Wrap
            font.pixelSize: Theme.s(17)
            font.weight: Font.Medium
            color: root.ink
        }
        Text {
            width: parent.width
            text: root.stateText
            elide: Text.ElideRight
            font.pixelSize: Theme.s(14)
            font.weight: root.alertLevel > 0 ? Font.Medium : Font.Normal
            color: root.alertLevel === 1 || root.warning ? Theme.err : root.heating && !root.lit ? Theme.heat2 : root.sub
            opacity: root.lit ? 0.72 : 1
        }
    }

    // battery almost empty: small red battery top right (left of the arrow if there is one)
    LineIcon {
        objectName: "battery:" + root.deviceId
        visible: root.batteryLow
        anchors.top: parent.top
        anchors.topMargin: Theme.s(16)
        anchors.right: parent.right
        anchors.rightMargin: root.hasDetail && !root.thermostat && !root.sensor ? Theme.s(48) : Theme.s(14)
        width: Theme.s(26)
        height: Theme.s(26)
        lineWidth: 1.5
        name: "battery"
        color: root.lit || root.alarm ? root.ink : Theme.err
    }

    Item {
        objectName: "more:" + root.deviceId
        visible: root.hasDetail && !root.thermostat && !root.sensor
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 6
        width: Theme.s(44)
        height: Theme.s(44)
        Accessible.role: Accessible.Button
        Accessible.name: qsTr("Open controls for %1").arg(root.shortName)

        LineIcon {
            anchors.centerIn: parent
            width: Theme.s(20)
            height: Theme.s(20)
            name: "chevron"
            color: root.lit ? Theme.goldInk : Theme.muted
        }
        MouseArea {
            anchors.fill: parent
            onClicked: root.openDetail(root.deviceId)
        }
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: 3
        radius: 10
        color: "transparent"
        border.color: root.lit ? Theme.goldInk : Theme.gold
        border.width: 2
        visible: root.activeFocus
    }
}
