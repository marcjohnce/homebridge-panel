import QtQuick
import QtQuick.Layouts

// Air purifier: speed bar, automatic / manual, power
ColumnLayout {
    id: root

    required property var dev
    required property Item sheet
    readonly property var st: dev.state || ({})
    readonly property var caps: dev.capabilities || []
    readonly property real barHeight: Math.max(180, Math.min(420, height - Theme.s(220)))

    spacing: Theme.s(16)

    Text {
        objectName: "purifierState"
        Layout.alignment: Qt.AlignHCenter
        text: root.dev.stateText || ""
        color: Theme.ink
        font.pixelSize: Theme.s(26)
        font.weight: Font.Light
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: Theme.s(56)

        Item { Layout.fillWidth: true }

        BrightnessBar {
            objectName: "speedBar"
            visible: root.caps.indexOf("speed") >= 0
            Layout.alignment: Qt.AlignVCenter
            barHeight: root.barHeight
            barWidth: Math.max(104, Math.min(140, Math.round(root.barHeight * 0.3)))
            serverValue: root.st.speed || 0
            off: !root.st.on
            label: qsTr("Speed")
            iconName: "fan"
            onInteracting: active => active ? root.sheet.interactionStarted() : root.sheet.interactionEnded()
            // a speed set by hand switches to manual
            onCommitted: value => panel.setAttrs(root.dev.id, root.caps.indexOf("auto") >= 0
                                                 ? { on: true, auto: false, speed: value } : { on: true, speed: value })
        }

        Row {
            objectName: "purifierModes"
            visible: root.caps.indexOf("auto") >= 0
            Layout.alignment: Qt.AlignVCenter
            spacing: 10
            PillButton {
                text: qsTr("Automatic")
                primary: !!root.st.auto
                onClicked: panel.setAttrs(root.dev.id, { on: true, auto: true })
            }
            PillButton {
                text: qsTr("Manual")
                primary: !root.st.auto
                onClicked: panel.setAttrs(root.dev.id, { on: true, auto: false })
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
