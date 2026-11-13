import QtQuick

// Screen saver: large clock; the first touch only wakes the panel
Rectangle {
    id: root

    property date now: new Date()
    signal woken

    color: Theme.page

    Timer {
        interval: 5000
        running: root.visible
        repeat: true
        triggeredOnStart: true
        onTriggered: root.now = new Date()
    }

    OpacityAnimator on opacity {
        running: root.visible
        from: 0
        to: 1
        duration: 800
    }

    Column {
        anchors.centerIn: parent
        spacing: 10

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Qt.formatTime(root.now, "hh:mm")
            color: Theme.dark ? "#BEB9B0" : Theme.ink
            font.pixelSize: Math.min(200, root.height * 0.28)
            font.weight: Font.ExtraLight
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.now.toLocaleDateString(Qt.locale("en_GB"), "dddd, d MMMM")
            color: Theme.muted
            font.pixelSize: 22
        }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            topPadding: 18
            spacing: 10
            visible: panel.outdoorTemp !== ""
            LineIcon {
                width: 26
                height: 26
                name: "weather"
                color: Theme.gold
            }
            Text {
                text: qsTr("%1 °C outdoors").arg(panel.outdoorTemp)
                color: Theme.dark ? "#BEB9B0" : Theme.ink
                font.pixelSize: 24
                font.weight: Font.Light
            }
        }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            topPadding: panel.outdoorTemp === "" ? 18 : 0
            spacing: 10
            visible: panel.indoorTemp !== ""
            LineIcon {
                width: 26
                height: 26
                name: "thermostat"
                color: Theme.gold
            }
            Text {
                text: qsTr("%1 °C indoors").arg(panel.indoorTemp)
                color: Theme.dark ? "#BEB9B0" : Theme.ink
                font.pixelSize: 24
                font.weight: Font.Light
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        onPressed: root.woken()
    }
}
