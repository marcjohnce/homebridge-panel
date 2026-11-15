import QtQuick
import QtQuick.Layouts

// Speaker / smart speaker: volume bar, play/pause/stop (smart speakers), mute
ColumnLayout {
    id: root

    required property var dev
    required property Item sheet
    readonly property var st: dev.state || ({})
    readonly property var caps: dev.capabilities || []
    readonly property bool hasMedia: caps.indexOf("media") >= 0
    readonly property real barHeight: Math.max(180, Math.min(420, height - Theme.s(200)))

    spacing: Theme.s(16)

    Text {
        objectName: "speakerState"
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
            objectName: "volumeBar"
            visible: root.caps.indexOf("volume") >= 0
            Layout.alignment: Qt.AlignVCenter
            barHeight: root.barHeight
            barWidth: Math.max(104, Math.min(140, Math.round(root.barHeight * 0.3)))
            serverValue: root.st.volume || 0
            off: !!root.st.mute
            label: qsTr("Volume")
            iconName: "volumeUp"
            onInteracting: active => active ? root.sheet.interactionStarted() : root.sheet.interactionEnded()
            onCommitted: value => panel.setAttrs(root.dev.id, { volume: value })
        }

        ColumnLayout {
            Layout.alignment: Qt.AlignVCenter
            spacing: Theme.s(14)
            Row {
                objectName: "mediaButtons"
                visible: root.hasMedia
                spacing: Theme.s(14)
                CircleButton {
                    iconName: root.st.media === "playing" ? "pause" : "play"
                    iconSize: Theme.s(26)
                    highlighted: root.st.media === "playing"
                    label: root.st.media === "playing" ? qsTr("Pause") : qsTr("Play")
                    onClicked: panel.setAttrs(root.dev.id, { media: root.st.media === "playing" ? "pause" : "play" })
                }
                CircleButton {
                    iconName: "stop"
                    iconSize: Theme.s(22)
                    label: qsTr("Stop")
                    onClicked: panel.setAttrs(root.dev.id, { media: "stop" })
                }
            }
            CircleButton {
                objectName: "muteButton"
                visible: root.caps.indexOf("mute") >= 0
                Layout.alignment: Qt.AlignHCenter
                iconName: "mute"
                iconSize: Theme.s(24)
                highlighted: !!root.st.mute
                label: root.st.mute ? qsTr("Sound on") : qsTr("Mute")
                onClicked: panel.setAttrs(root.dev.id, { mute: !root.st.mute })
            }
        }

        Item { Layout.fillWidth: true }
    }
}
