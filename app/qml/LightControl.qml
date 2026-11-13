import QtQuick
import QtQuick.Layouts

// Licht und Ventilator: Helligkeit/Stufe, Farbe, Weißton und Ein/Aus
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
        spacing: 64

        Item { Layout.fillWidth: true }

        BrightnessBar {
            visible: root.levelKey !== ""
            Layout.alignment: Qt.AlignVCenter
            barHeight: Math.min(300, root.height - 160)
            serverValue: root.st[root.levelKey] || 0
            off: !root.st.on
            label: root.levelKey === "speed" ? qsTr("Stufe") : qsTr("Helligkeit")
            iconName: root.levelKey === "speed" ? "fan" : "sun"
            onInteracting: active => root.interacting(active)
            onCommitted: value => {
                const attrs = { on: true };
                attrs[root.levelKey] = value;
                panel.setAttrs(root.dev.id, attrs);
            }
        }

        ColumnLayout {
            visible: root.hasColor || root.hasCt
            Layout.alignment: Qt.AlignVCenter
            spacing: 30

            ColorWheel {
                visible: root.hasColor
                readonly property real size: Math.min(250, root.height - 170)
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
                visible: root.hasCt
                Layout.preferredWidth: 250
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
        Layout.alignment: Qt.AlignHCenter
        implicitWidth: 68
        implicitHeight: 68
        iconName: "power"
        iconSize: 30
        highlighted: !!root.st.on
        label: root.st.on ? qsTr("%1 ausschalten").arg(root.dev.name) : qsTr("%1 einschalten").arg(root.dev.name)
        onClicked: panel.toggle(root.dev.id)
    }
}
