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
    required property bool reachable
    required property bool heating
    required property string stateText
    required property bool hasDetail
    required property real targetTemp
    required property real minTemp
    required property real maxTemp
    required property bool modeOff

    property bool showRoom: false
    property int columns: 4
    property int count: 1
    signal openDetail(string id)

    readonly property bool thermostat: type === "thermostat"

    objectName: "tile:" + deviceId
    readonly property int lastRowStart: Math.floor((count - 1) / columns) * columns
    readonly property real cornerRadius: 14

    topLeftRadius: index === 0 ? cornerRadius : 0
    topRightRadius: index === Math.min(columns, count) - 1 ? cornerRadius : 0
    bottomLeftRadius: index === lastRowStart ? cornerRadius : 0
    bottomRightRadius: (index === count - 1 || (index === lastRowStart - 1 && count % columns !== 0)) ? cornerRadius : 0
    color: isOn ? Theme.gold : (mouse.pressed ? Theme.tilePress : Theme.tile)
    opacity: reachable ? 1 : 0.45

    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: qsTr("%1: %2").arg(shortName).arg(stateText)
    Accessible.checkable: !thermostat
    Accessible.checked: isOn
    Keys.onSpacePressed: activate()
    Keys.onReturnPressed: activate()

    Behavior on color { ColorAnimation { duration: 200 } }

    function activate() {
        if (thermostat)
            root.openDetail(deviceId);
        else
            panel.toggle(deviceId);
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        onClicked: root.activate()
        onPressAndHold: if (root.hasDetail) root.openDetail(root.deviceId)
    }

    LineIcon {
        x: 18
        y: 18
        width: 34
        height: 34
        lineWidth: 1.15
        visible: !root.thermostat
        name: root.icon
        color: root.isOn ? Theme.goldInk : Theme.muted
    }

    Item {
        visible: root.thermostat
        x: 12
        y: 12
        width: root.height < 136 ? 52 : 58
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
            font.pixelSize: parent.width < 56 ? 15 : 17
            font.weight: Font.Light
        }
    }

    Column {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 18
        anchors.bottomMargin: 16
        spacing: 2

        Text {
            visible: root.showRoom
            width: parent.width
            text: root.room
            elide: Text.ElideRight
            font.pixelSize: 13
            color: root.isOn ? Theme.goldInk : Theme.muted
            opacity: root.isOn ? 0.65 : 1
        }
        Text {
            width: parent.width
            text: root.shortName
            elide: Text.ElideRight
            maximumLineCount: 2
            wrapMode: Text.Wrap
            font.pixelSize: 17
            font.weight: Font.Medium
            color: root.isOn ? Theme.goldInk : Theme.ink
        }
        Text {
            width: parent.width
            text: root.stateText
            elide: Text.ElideRight
            font.pixelSize: 14
            color: root.isOn ? Theme.goldInk : (root.heating ? Theme.heat2 : Theme.muted)
            opacity: root.isOn ? 0.72 : 1
        }
    }

    Item {
        objectName: "more:" + root.deviceId
        visible: root.hasDetail && !root.thermostat
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 6
        width: 44
        height: 44
        Accessible.role: Accessible.Button
        Accessible.name: qsTr("Open controls for %1").arg(root.shortName)

        LineIcon {
            anchors.centerIn: parent
            width: 20
            height: 20
            name: "chevron"
            color: root.isOn ? Theme.goldInk : Theme.muted
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
        border.color: root.isOn ? Theme.goldInk : Theme.gold
        border.width: 2
        visible: root.activeFocus
    }
}
