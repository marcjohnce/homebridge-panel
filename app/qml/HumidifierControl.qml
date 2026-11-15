import QtQuick
import QtQuick.Layouts

// Humidifier / dehumidifier: current humidity, mode, target humidity (−/+), water level, power
ColumnLayout {
    id: root

    property var dev
    readonly property var st: dev.state || ({})
    readonly property var caps: dev.capabilities || []
    readonly property var modes: dev.meta && dev.meta.modes ? dev.meta.modes : []
    readonly property var labels: ({ auto: qsTr("Automatic"), humidify: qsTr("Humidify"), dehumidify: qsTr("Dehumidify") })

    spacing: Theme.s(18)

    Item { Layout.fillHeight: true }

    Text {
        objectName: "humidityNow"
        Layout.alignment: Qt.AlignHCenter
        text: root.st.humidity !== undefined && root.st.humidity !== null ? Theme.num(root.st.humidity, 0) + " %" : "–"
        color: Theme.ink
        font.pixelSize: Theme.s(72)
        font.weight: Font.Light
    }
    Text {
        objectName: "humidifierActivity"
        Layout.alignment: Qt.AlignHCenter
        text: !root.st.on ? qsTr("Off") : root.st.activity === "humidifying" ? qsTr("Humidifying")
            : root.st.activity === "dehumidifying" ? qsTr("Dehumidifying") : qsTr("Idle")
        color: Theme.muted
        font.pixelSize: Theme.s(17)
    }

    Row {
        objectName: "humidifierModes"
        visible: root.modes.length > 1
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: Theme.s(10)
        spacing: 10
        Repeater {
            model: root.modes
            PillButton {
                required property string modelData
                text: root.labels[modelData] || modelData
                primary: root.st.mode === modelData
                onClicked: panel.setAttrs(root.dev.id, { on: true, mode: modelData })
            }
        }
    }

    // target humidity: humidify up to …, dehumidify down to … (both in automatic mode)
    Repeater {
        model: [
            { key: "humidify_target", label: qsTr("Humidify up to"), show: root.st.mode !== "dehumidify" },
            { key: "dehumidify_target", label: qsTr("Dehumidify down to"), show: root.st.mode !== "humidify" }
        ]
        RowLayout {
            required property var modelData
            objectName: "target:" + modelData.key
            visible: modelData.show && root.caps.indexOf(modelData.key) >= 0
            Layout.alignment: Qt.AlignHCenter
            spacing: Theme.s(18)
            Text {
                Layout.preferredWidth: Theme.s(190)
                horizontalAlignment: Text.AlignRight
                text: parent.modelData.label
                color: Theme.muted
                font.pixelSize: Theme.s(16)
            }
            CircleButton {
                iconName: "minus"
                iconSize: Theme.s(22)
                label: qsTr("Less")
                onClicked: panel.setAttrs(root.dev.id, ({ [parent.modelData.key]: Math.max(0, (root.st[parent.modelData.key] || 0) - 5) }))
            }
            Text {
                Layout.preferredWidth: Theme.s(80)
                horizontalAlignment: Text.AlignHCenter
                text: (root.st[parent.modelData.key] || 0) + " %"
                color: Theme.ink
                font.pixelSize: Theme.s(26)
                font.weight: Font.Light
            }
            CircleButton {
                iconName: "plus"
                iconSize: Theme.s(22)
                label: qsTr("More")
                onClicked: panel.setAttrs(root.dev.id, ({ [parent.modelData.key]: Math.min(100, (root.st[parent.modelData.key] || 0) + 5) }))
            }
        }
    }

    Text {
        visible: root.st.water !== undefined
        Layout.alignment: Qt.AlignHCenter
        text: qsTr("Water level %1 %").arg(root.st.water)
        color: (root.st.water || 0) < 10 ? Theme.err : Theme.muted
        font.pixelSize: Theme.s(15)
    }

    Item { Layout.fillHeight: true }

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
