import QtQuick
import QtQuick.Controls.Basic

// White tone from cool (left) to warm (right), values in mired; below it shades of white to pick
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

    // shades of white to pick directly (absolute kelvin), cool to warm like the slider above;
    // those the light cannot show are greyed out
    readonly property var presets: [
        { name: qsTr("Cool white"), kelvin: 7000, swatch: "#E4EEFF" },
        { name: qsTr("Daylight white"), kelvin: 5500, swatch: "#FFF7EF" },
        { name: qsTr("White"), kelvin: 4000, swatch: "#FFE9CF" },
        { name: qsTr("Soft white"), kelvin: 2700, swatch: "#FFC987" },
        { name: qsTr("Warm white"), kelvin: 2200, swatch: "#FFB15E" }
    ]
    function pick(kelvin) {
        const mired = Math.round(1e6 / kelvin);
        slider.value = mired;
        commit.stop();
        root.committed(mired);
        release.restart();
    }

    Item {
        width: parent.width
        height: Theme.s(6)
    }
    Row {
        id: presetRow
        objectName: "whitePresets"
        width: parent.width
        readonly property real cell: width / root.presets.length
        Repeater {
            model: root.presets
            Item {
                id: preset
                required property var modelData
                readonly property int mired: Math.round(1e6 / modelData.kelvin)
                // a little tolerance: lights often stop at 153 mired (6500 K) or 454 (2200 K)
                readonly property bool possible: mired >= root.minMired - 4 && mired <= root.maxMired + 4
                readonly property bool current: Math.abs(slider.value - mired) <= 3
                objectName: "whitePreset:" + modelData.kelvin
                width: presetRow.cell
                height: column.implicitHeight + 8
                opacity: possible ? 1 : 0.35
                activeFocusOnTab: possible
                Accessible.role: Accessible.Button
                Accessible.name: qsTr("%1, %2 K").arg(modelData.name).arg(modelData.kelvin)
                Accessible.checked: current
                Keys.onReturnPressed: if (possible) root.pick(modelData.kelvin)
                Keys.onSpacePressed: if (possible) root.pick(modelData.kelvin)

                Column {
                    id: column
                    width: parent.width
                    spacing: 4
                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: Theme.s(40)
                        height: width
                        radius: width / 2
                        color: preset.modelData.swatch
                        border.color: preset.current ? Theme.gold : (preset.activeFocus ? Theme.ink : Theme.line)
                        border.width: preset.current || preset.activeFocus ? 3 : 1
                    }
                    Text {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: preset.modelData.name
                        color: preset.current ? Theme.ink : Theme.muted
                        font.pixelSize: Theme.s(12)
                        font.weight: preset.current ? Font.Medium : Font.Normal
                        wrapMode: Text.WordWrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                    }
                    Text {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: qsTr("%1 K").arg(preset.modelData.kelvin)
                        color: Theme.muted
                        font.pixelSize: Theme.s(11)
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: preset.possible
                    onClicked: root.pick(preset.modelData.kelvin)
                }
            }
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
