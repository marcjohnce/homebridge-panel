import QtQuick
import QtQuick.Controls.Basic

// White tone from cool (left) to warm (right), values in mired
Column {
    id: root

    property real serverValue: 300
    property real minMired: 140
    property real maxMired: 500
    signal committed(int mired)
    signal interacting(bool active)

    spacing: 4

    Row {
        width: parent.width
        Text {
            width: parent.width / 2
            text: qsTr("White tone")
            color: Theme.muted
            font.pixelSize: Theme.s(14)
        }
        Text {
            width: parent.width / 2
            horizontalAlignment: Text.AlignRight
            text: qsTr("%1 K").arg(Math.round(1e6 / slider.value / 50) * 50)
            color: Theme.muted
            font.pixelSize: Theme.s(14)
        }
    }

    Slider {
        id: slider
        width: parent.width
        from: root.minMired
        to: root.maxMired
        stepSize: 1
        Accessible.name: qsTr("White tone")

        Binding on value {
            when: !slider.pressed && !commit.running && !release.running
            value: root.serverValue
        }
        onMoved: commit.restart()
        onPressedChanged: root.interacting(pressed)

        background: Rectangle {
            x: slider.leftPadding
            y: slider.topPadding + slider.availableHeight / 2 - height / 2
            width: slider.availableWidth
            height: 6
            radius: 3
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "#CFE2FF" }
                GradientStop { position: 0.5; color: "#FFF6E6" }
                GradientStop { position: 1; color: "#FFB75A" }
            }
        }
        handle: Rectangle {
            x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
            y: slider.topPadding + slider.availableHeight / 2 - height / 2
            width: 28
            height: 28
            radius: 14
            color: Theme.knob
            border.color: slider.activeFocus ? Theme.gold : Theme.line
            border.width: slider.activeFocus ? 2 : 1
        }
    }

    Timer {
        id: commit
        interval: 300
        onTriggered: {
            root.committed(Math.round(slider.value));
            release.restart();
        }
    }
    Timer {
        id: release
        interval: 1500
    }
}
