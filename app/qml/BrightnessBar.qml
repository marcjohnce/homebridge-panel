import QtQuick

// Senkrechter Balken für Helligkeit oder Lüfterstufe (1–100 %)
Column {
    id: root

    property real serverValue: 0
    property bool off: false
    property string label
    property string iconName: "sun"
    property real barHeight: 300
    signal committed(int value)
    signal interacting(bool active)

    property bool holding: false
    property int local: 0
    readonly property real shown: holding ? local : serverValue

    spacing: 10

    function setValue(v) {
        local = Math.round(Math.max(1, Math.min(100, v)));
        holding = true;
        release.stop();
        commit.restart();
    }

    Timer {
        id: commit
        interval: 300
        onTriggered: {
            root.committed(root.local);
            release.restart();
        }
    }
    Timer {
        id: release
        interval: 1500
        onTriggered: root.holding = false
    }

    Rectangle {
        id: bar
        width: 104
        height: root.barHeight
        radius: 18
        color: Theme.tile
        clip: true
        activeFocusOnTab: true
        border.color: activeFocus ? Theme.gold : "transparent"
        border.width: 2
        Accessible.role: Accessible.Slider
        Accessible.name: qsTr("%1 %2 Prozent").arg(root.label).arg(Math.round(root.shown))
        Keys.onUpPressed: root.setValue(root.shown + 5)
        Keys.onDownPressed: root.setValue(root.shown - 5)

        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: parent.height * root.shown / 100
            color: root.off && !root.holding ? Theme.line : Theme.gold
        }
        LineIcon {
            anchors.horizontalCenter: parent.horizontalCenter
            y: 14
            width: 22
            height: 22
            name: root.iconName
            color: Theme.muted
        }
        MouseArea {
            anchors.fill: parent
            preventStealing: true
            onPressed: mouse => {
                root.interacting(true);
                root.setValue((1 - mouse.y / height) * 100);
            }
            onPositionChanged: mouse => root.setValue((1 - mouse.y / height) * 100)
            onReleased: root.interacting(false)
            onCanceled: root.interacting(false)
        }
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        text: qsTr("%1 %").arg(Math.round(root.shown))
        color: Theme.ink
        font.pixelSize: 22
        font.weight: Font.Light
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.label
        color: Theme.muted
        font.pixelSize: 14
    }
}
