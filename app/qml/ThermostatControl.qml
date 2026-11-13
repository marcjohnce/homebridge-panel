import QtQuick
import QtQuick.Layouts
import "Geometry.js" as Geo

ColumnLayout {
    id: root

    required property var dev
    required property Item sheet

    readonly property var st: dev.state || ({})
    readonly property var meta: dev.meta || ({})
    readonly property real minT: meta.min_temp !== undefined ? meta.min_temp : 10
    readonly property real maxT: meta.max_temp !== undefined ? meta.max_temp : 30
    readonly property real step: meta.temp_step || 0.5
    readonly property bool active: st.mode !== "off" && dev.reachable
    readonly property real serverValue: st.target_temp !== undefined && st.target_temp !== null ? st.target_temp : 20
    property bool holding: false
    property real local: 20
    readonly property real shown: holding ? local : serverValue

    spacing: 6

    function setTarget(v) {
        v = Math.max(minT, Math.min(maxT, Math.round(v / step) * step));
        local = v;
        holding = true;
        release.stop();
        commit.restart();
    }

    Timer {
        id: commit
        interval: 600
        onTriggered: {
            const attrs = { target_temp: root.local };
            if (root.st.mode === "off")
                attrs.mode = "heat";
            panel.setAttrs(root.dev.id, attrs);
            release.restart();
        }
    }
    Timer {
        id: release
        interval: 1500
        onTriggered: root.holding = false
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: 24

        Item { Layout.fillWidth: true }

        CircleButton {
            objectName: "minusButton"
            iconName: "minus"
            label: qsTr("Cooler")
            onClicked: root.setTarget(root.shown - root.step)
        }

        Item {
            id: dial
            objectName: "dial"
            readonly property real size: Math.min(340, root.height - 64)
            Layout.preferredWidth: size
            Layout.preferredHeight: size
            Layout.alignment: Qt.AlignVCenter
            activeFocusOnTab: true
            Accessible.role: Accessible.Slider
            Accessible.name: qsTr("Target temperature %1 degrees").arg(Theme.fmt(root.shown))
            Keys.onUpPressed: root.setTarget(root.shown + root.step)
            Keys.onRightPressed: root.setTarget(root.shown + root.step)
            Keys.onDownPressed: root.setTarget(root.shown - root.step)
            Keys.onLeftPressed: root.setTarget(root.shown - root.step)

            ArcGauge {
                anchors.fill: parent
                from: root.minT
                to: root.maxT
                value: root.shown
                active: root.active
                lineWidth: 6
                knob: true
                labels: true
                ticks: (root.maxT - root.minT) / root.step <= 60 ? Math.round((root.maxT - root.minT) / root.step) : Math.round(root.maxT - root.minT)
            }

            Column {
                anchors.centerIn: parent
                Row {
                    anchors.horizontalCenter: parent.horizontalCenter
                    Text {
                        text: Theme.fmt(root.shown)
                        color: Theme.ink
                        font.pixelSize: Math.min(88, dial.size * 0.26)
                        font.weight: Font.ExtraLight
                    }
                    Text {
                        y: 10
                        text: "°C"
                        color: Theme.muted
                        font.pixelSize: 20
                    }
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: qsTr("Now %1 °C").arg(Theme.fmt(root.st.current_temp))
                    color: Theme.muted
                    font.pixelSize: 16
                }
            }

            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: "transparent"
                border.color: Theme.gold
                border.width: 2
                visible: dial.activeFocus
            }

            MouseArea {
                anchors.fill: parent
                preventStealing: true
                function apply(mx, my) {
                    root.setTarget(root.minT + Geo.fractionAt(width / 2, height / 2, mx, my) * (root.maxT - root.minT));
                }
                onPressed: mouse => {
                    root.sheet.interactionStarted();
                    apply(mouse.x, mouse.y);
                }
                onPositionChanged: mouse => apply(mouse.x, mouse.y)
                onReleased: root.sheet.interactionEnded()
                onCanceled: root.sheet.interactionEnded()
            }
        }

        CircleButton {
            objectName: "plusButton"
            iconName: "plus"
            label: qsTr("Warmer")
            onClicked: root.setTarget(root.shown + root.step)
        }

        Item { Layout.fillWidth: true }
    }

    Row {
        objectName: "modes"
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredHeight: 52
        spacing: 26
        Repeater {
            model: root.meta.modes || ["off", "heat", "auto"]
            UnderlineButton {
                required property string modelData
                readonly property var labels: ({ off: qsTr("Off"), heat: qsTr("Heat"), cool: qsTr("Cool"), auto: qsTr("Auto") })
                text: labels[modelData] || modelData
                centered: true
                selected: root.st.mode === modelData
                onClicked: panel.setAttrs(root.dev.id, { mode: modelData })
            }
        }
    }
}
