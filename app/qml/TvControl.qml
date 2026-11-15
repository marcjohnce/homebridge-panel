import QtQuick
import QtQuick.Layouts

// Television: power, input sources, volume and the remote keys (only what the device offers)
ColumnLayout {
    id: root

    property var dev
    readonly property var st: dev.state || ({})
    readonly property var caps: dev.capabilities || []
    readonly property var inputs: dev.meta && dev.meta.inputs ? dev.meta.inputs : []
    readonly property bool narrow: width < Theme.s(700)
    readonly property bool hasRemote: caps.indexOf("remote") >= 0
    readonly property bool hasVolume: caps.indexOf("volume") >= 0 || caps.indexOf("mute") >= 0

    function key(k) {
        panel.setAttrs(dev.id, { remote: k });
    }

    spacing: Theme.s(root.narrow ? 14 : 22)

    Text {
        objectName: "tvState"
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: Theme.s(root.narrow ? 4 : 16)
        text: root.dev.stateText || ""
        color: Theme.ink
        font.pixelSize: Theme.s(root.narrow ? 24 : 30)
        font.weight: Font.Light
    }

    // input sources
    Flow {
        objectName: "tvInputs"
        visible: root.inputs.length > 0
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredWidth: Math.min(root.width, implicitInputsWidth)
        readonly property real implicitInputsWidth: {
            let w = 0;
            for (let i = 0; i < inputRepeater.count; i++)
                w += inputRepeater.itemAt(i) ? inputRepeater.itemAt(i).implicitWidth + spacing : 0;
            return Math.max(0, w - spacing);
        }
        spacing: 10
        Repeater {
            id: inputRepeater
            model: root.inputs
            PillButton {
                required property var modelData
                objectName: "input:" + modelData.id
                text: modelData.name
                primary: root.st.on && root.st.input === modelData.id
                onClicked: panel.setAttrs(root.dev.id, { input: modelData.id })
            }
        }
    }

    Item {
        Layout.fillHeight: true
    }

    // remote keys and volume side by side (stacked when narrow)
    GridLayout {
        Layout.alignment: Qt.AlignHCenter
        columns: 2
        columnSpacing: Theme.s(root.narrow ? 28 : 64)
        rowSpacing: Theme.s(16)

        Grid {
            objectName: "tvRemote"
            visible: root.hasRemote
            columns: 3
            spacing: Theme.s(10)
            Repeater {
                model: ["", "up", "", "left", "select", "right", "back", "down", "play_pause"]
                Item {
                    required property string modelData
                    width: Theme.s(root.narrow ? 58 : 64)
                    height: width
                    CircleButton {
                        anchors.fill: parent
                        visible: parent.modelData !== ""
                        objectName: "remote:" + parent.modelData
                        iconName: ({ up: "up", down: "down", left: "back", right: "chevron", select: "dot",
                                     back: "returnKey", play_pause: "playPause" })[parent.modelData] || "dot"
                        iconSize: Theme.s(24)
                        highlighted: parent.modelData === "select"
                        label: ({ up: qsTr("Up"), down: qsTr("Down"), left: qsTr("Left"), right: qsTr("Right"),
                                  select: qsTr("OK"), back: qsTr("Back"), play_pause: qsTr("Play / pause") })[parent.modelData] || ""
                        onClicked: root.key(parent.modelData)
                    }
                }
            }
        }

        ColumnLayout {
            objectName: "tvVolume"
            visible: root.hasVolume
            spacing: Theme.s(10)
            CircleButton {
                visible: root.caps.indexOf("volume") >= 0
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: Theme.s(root.narrow ? 58 : 64)
                implicitHeight: implicitWidth
                iconName: "volumeUp"
                iconSize: Theme.s(24)
                label: qsTr("Louder")
                onClicked: panel.setAttrs(root.dev.id, { volume_step: 1 })
            }
            CircleButton {
                visible: root.caps.indexOf("mute") >= 0
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: Theme.s(root.narrow ? 58 : 64)
                implicitHeight: implicitWidth
                iconName: "mute"
                iconSize: Theme.s(24)
                highlighted: !!root.st.mute
                label: root.st.mute ? qsTr("Sound on") : qsTr("Mute")
                onClicked: panel.setAttrs(root.dev.id, { mute: !root.st.mute })
            }
            CircleButton {
                visible: root.caps.indexOf("volume") >= 0
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: Theme.s(root.narrow ? 58 : 64)
                implicitHeight: implicitWidth
                iconName: "volumeDown"
                iconSize: Theme.s(24)
                label: qsTr("Quieter")
                onClicked: panel.setAttrs(root.dev.id, { volume_step: -1 })
            }
        }
    }

    Item {
        Layout.fillHeight: true
    }

    CircleButton {
        objectName: "tvPower"
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
