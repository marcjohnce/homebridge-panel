import QtQuick

// Screen saver: large clock; the first touch only wakes the panel
Rectangle {
    id: root

    property date now: new Date()
    readonly property var weather: panel.weather.idle
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
            color: Theme.idleInk
            font.pixelSize: Math.min(200, root.height * 0.28)
            font.weight: Font.ExtraLight
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: Theme.date(root.now)
            color: Theme.muted
            font.pixelSize: 22
        }
        // the weather of the default place (Settings → Weather)
        Row {
            objectName: "idleWeather"
            anchors.horizontalCenter: parent.horizontalCenter
            topPadding: 18
            spacing: 12
            visible: root.weather.temp !== undefined
            LineIcon {
                anchors.verticalCenter: parent.verticalCenter
                width: 34
                height: 34
                name: root.weather.kind === "clear" ? (root.weather.night ? "moon" : "sun")
                    : root.weather.kind === "partly" ? "weather" : (root.weather.kind || "cloud")
                color: Theme.gold
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: qsTr("%1 °C, %2").arg(root.weather.temp).arg(root.weather.text)
                color: Theme.idleInk
                font.pixelSize: 26
                font.weight: Font.Light
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: qsTr("%1, today %2° / %3°").arg(root.weather.name).arg(root.weather.max).arg(root.weather.min)
                color: Theme.muted
                font.pixelSize: 20
            }
        }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            topPadding: root.weather.temp !== undefined ? 0 : 18
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
                color: Theme.idleInk
                font.pixelSize: 24
                font.weight: Font.Light
            }
        }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            topPadding: panel.outdoorTemp === "" && root.weather.temp === undefined ? 18 : 0
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
                color: Theme.idleInk
                font.pixelSize: 24
                font.weight: Font.Light
            }
        }
    }

    // With a scene for the double tap, the first tap waits a moment for a second one; a dark
    // display (switched off) always just wakes up.
    property bool displayOff: false
    readonly property bool doubleTap: panel.idleScene.id !== undefined && !displayOff
    signal runScene(string id, string name)

    Timer {
        id: secondTap
        interval: 350
        onTriggered: root.woken()
    }
    MouseArea {
        objectName: "idleTouch"
        anchors.fill: parent
        onPressed: {
            if (!root.doubleTap) {
                root.woken();
            } else if (secondTap.running) {
                secondTap.stop();
                root.runScene(panel.idleScene.id, panel.idleScene.name);
            } else {
                secondTap.start();
            }
        }
    }
}
