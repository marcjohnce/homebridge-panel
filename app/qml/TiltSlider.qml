import QtQuick
import QtQuick.Controls.Basic

// Slat angle of a blind in degrees
Column {
    id: root

    property real serverValue: 0
    property real minAngle: -90
    property real maxAngle: 90
    signal committed(int angle)
    signal interacting(bool active)

    spacing: 4

    Row {
        width: parent.width
        Text {
            width: parent.width / 2
            text: qsTr("Slat angle")
            color: Theme.muted
            font.pixelSize: Theme.s(14)
        }
        Text {
            width: parent.width / 2
            horizontalAlignment: Text.AlignRight
            text: qsTr("%1°").arg(Math.round(slider.value))
            color: Theme.muted
            font.pixelSize: Theme.s(14)
        }
    }

    Slider {
        id: slider
        width: parent.width
        from: root.minAngle
        to: root.maxAngle
        stepSize: 5
        Accessible.name: qsTr("Slat angle")

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
            height: 4
            radius: 2
            color: Theme.line
            Rectangle {     // mark for 0° (slats level)
                x: parent.width * (0 - root.minAngle) / (root.maxAngle - root.minAngle) - 1
                y: -4
                width: 2
                height: 12
                color: Theme.muted
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
