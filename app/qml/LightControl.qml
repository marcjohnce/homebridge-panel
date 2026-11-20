import QtQuick
import QtQuick.Layouts

// Lights, fans, switches and plugs: brightness/speed, color, white tone, power draw and power button
ColumnLayout {
    id: root

    required property var dev
    required property Item sheet

    readonly property var st: dev.state || ({})
    readonly property var meta: dev.meta || ({})
    readonly property var caps: dev.capabilities || []
    readonly property string levelKey: caps.indexOf("brightness") >= 0 ? "brightness" : (caps.indexOf("speed") >= 0 ? "speed" : "")
    readonly property bool hasColor: caps.indexOf("color") >= 0
    readonly property bool hasCt: caps.indexOf("color_temp") >= 0
    // Sizes follow the available space: bar and wheel grow on 1280×800 and 720×720
    readonly property real barHeight: Math.max(180, Math.min(460, height - Theme.s(170)))
    readonly property real barWidth: Math.max(104, Math.min(140, Math.round(barHeight * 0.3)))
    readonly property real gap: Math.min(Theme.s(64), Math.round(width * 0.08))
    readonly property real wheelSize: Math.max(180, Math.min(420,
        height - Theme.s(68) - 50 - (hasCt ? 90 : 0),
        width - (levelKey !== "" ? barWidth + gap : 0) - 56))

    spacing: 10

    function interacting(active) {
        if (active)
            sheet.interactionStarted();
        else
            sheet.interactionEnded();
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: 0

        Item { Layout.fillWidth: true }

        // plugs that measure: power now and total consumption
        Row {
            objectName: "powerReadings"
            visible: root.st.power !== undefined && root.st.power !== null
            Layout.alignment: Qt.AlignVCenter
            spacing: Theme.s(72)
            Repeater {
                model: [{ key: "power", label: qsTr("Power now"),
                          value: Theme.num(root.st.power || 0, (root.st.power || 0) < 10 ? 1 : 0), unit: "W" },
                        { key: "energy", label: qsTr("Total consumption"),
                          value: Theme.num(root.st.energy || 0, 1), unit: "kWh" }]
                    .filter(r => root.st[r.key] !== undefined && root.st[r.key] !== null)
                Column {
                    required property var modelData
                    objectName: "reading:" + modelData.key
                    spacing: Theme.s(4)
                    Row {
                        spacing: Theme.s(8)
                        Text {
                            text: modelData.value
                            color: Theme.ink
                            font.pixelSize: Theme.s(60)
                            font.weight: Font.Light
                        }
                        Text {
                            anchors.baseline: parent.children[0].baseline
                            text: modelData.unit
                            color: Theme.muted
                            font.pixelSize: Theme.s(22)
                        }
                    }
                    Text {
                        text: modelData.label
                        color: Theme.muted
                        font.pixelSize: Theme.s(16)
                    }
                }
            }
        }

        BrightnessBar {
            objectName: "brightnessBar"
            visible: root.levelKey !== ""
            Layout.alignment: Qt.AlignVCenter
            barHeight: root.barHeight
            barWidth: root.barWidth
            serverValue: root.st[root.levelKey] || 0
            off: !root.st.on
            label: root.levelKey === "speed" ? qsTr("Speed") : qsTr("Brightness")
            iconName: root.levelKey === "speed" ? "fan" : "sun"
            onInteracting: active => root.interacting(active)
            onCommitted: value => {
                const attrs = { on: true };
                attrs[root.levelKey] = value;
                panel.setAttrs(root.dev.id, attrs);
            }
        }

        Item {
            visible: root.levelKey !== "" && (root.hasColor || root.hasCt)
            Layout.preferredWidth: root.gap
        }

        ColumnLayout {
            visible: root.hasColor || root.hasCt
            Layout.alignment: Qt.AlignVCenter
            spacing: 30

            ColorWheel {
                objectName: "colorWheel"
                visible: root.hasColor
                readonly property real size: root.wheelSize
                Layout.preferredWidth: size
                Layout.preferredHeight: size
                Layout.alignment: Qt.AlignHCenter
                hue: root.st.hue || 0
                saturation: root.st.saturation || 0
                lit: !!root.st.on
                onInteracting: active => root.interacting(active)
                onCommitted: (hue, saturation) => panel.setAttrs(root.dev.id, { on: true, hue: hue, saturation: saturation })
            }

            ColorTempSlider {
                objectName: "colorTemp"
                visible: root.hasCt
                Layout.preferredWidth: root.hasColor ? root.wheelSize : Theme.s(320)
                Layout.alignment: Qt.AlignHCenter
                serverValue: root.st.color_temp || 300
                minMired: root.meta.min_mired || 140
                maxMired: root.meta.max_mired || 500
                onInteracting: active => root.interacting(active)
                onCommitted: mired => panel.setAttrs(root.dev.id, { on: true, color_temp: mired })
            }
        }

        Item { Layout.fillWidth: true }
    }

    CircleButton {
        objectName: "powerButton"
        Layout.alignment: Qt.AlignHCenter
        implicitWidth: Theme.s(68)
        implicitHeight: Theme.s(68)
        iconName: "power"
        iconSize: Theme.s(30)
        highlighted: !!root.st.on
        label: root.st.on ? qsTr("Turn off %1").arg(root.dev.name) : qsTr("Turn on %1").arg(root.dev.name)
        onClicked: panel.toggle(root.dev.id)
    }
}
