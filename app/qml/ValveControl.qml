import QtQuick
import QtQuick.Layouts

// Valve with a run time: state, run time to choose, open / close
ColumnLayout {
    id: root

    property var dev
    readonly property var st: dev.state || ({})
    readonly property var durations: [5, 10, 15, 30, 60]       // minutes

    spacing: Theme.s(24)

    Item {
        Layout.fillHeight: true
    }

    ColumnLayout {
        Layout.alignment: Qt.AlignHCenter
        spacing: Theme.s(10)
        LineIcon {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.s(72)
            Layout.preferredHeight: Theme.s(72)
            lineWidth: 1.1
            name: root.dev.icon || "valve"
            color: root.st.on ? Theme.gold : Theme.muted
        }
        Text {
            objectName: "valveState"
            Layout.alignment: Qt.AlignHCenter
            text: root.dev.stateText || ""
            color: Theme.ink
            font.pixelSize: Theme.s(30)
            font.weight: Font.Light
        }
    }

    Text {
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: Theme.s(12)
        text: qsTr("Run time")
        color: Theme.muted
        font.pixelSize: Theme.s(15)
    }
    // a row of equally wide buttons: the bold selected one must not change widths or wrap
    Row {
        objectName: "valveDurations"
        Layout.alignment: Qt.AlignHCenter
        spacing: 10
        Repeater {
            model: root.durations
            PillButton {
                required property int modelData
                objectName: "duration:" + modelData
                implicitWidth: Math.min(Theme.s(104), (root.width - 40) / root.durations.length)
                text: qsTr("%1 min").arg(modelData)
                primary: Math.round((root.st.duration || 0) / 60) === modelData
                onClicked: panel.setAttrs(root.dev.id, { duration: modelData * 60 })
            }
        }
    }

    Item {
        Layout.fillHeight: true
    }

    CircleButton {
        objectName: "valvePower"
        Layout.alignment: Qt.AlignHCenter
        implicitWidth: Theme.s(68)
        implicitHeight: Theme.s(68)
        iconName: "power"
        iconSize: Theme.s(30)
        highlighted: !!root.st.on
        label: root.st.on ? qsTr("Close %1").arg(root.dev.name) : qsTr("Open %1").arg(root.dev.name)
        onClicked: panel.toggle(root.dev.id)
    }
}
