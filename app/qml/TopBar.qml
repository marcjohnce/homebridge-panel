import QtQuick
import QtQuick.Layouts

// Header for square and portrait screens: one slim row with the clock, the menu as icon
// buttons, status and settings. Date and temperatures only where there is room (portrait).
RowLayout {
    id: root

    property date now: new Date()
    property bool roomy: false
    signal openSettings

    spacing: 12

    Timer {
        interval: 5000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.now = new Date()
    }

    Text {
        objectName: "clock"
        text: Qt.formatTime(root.now, "hh:mm")
        color: Theme.ink
        font.pixelSize: root.roomy ? 52 : 40
        font.weight: Font.ExtraLight
    }

    ColumnLayout {
        visible: root.roomy
        Layout.fillWidth: true
        spacing: 2
        Text {
            objectName: "date"
            Layout.fillWidth: true
            text: Theme.date(root.now)
            color: Theme.muted
            font.pixelSize: 15
            elide: Text.ElideRight
        }
        Text {
            objectName: "climate"
            Layout.fillWidth: true
            visible: panel.indoorTemp !== ""
            text: qsTr("%1 °C indoors").arg(panel.indoorTemp)
            color: Theme.ink
            font.pixelSize: 17
            font.weight: Font.Light
            elide: Text.ElideRight
        }
    }

    Item {
        visible: !root.roomy
        Layout.fillWidth: true
    }

    CategoryBar {
        Layout.alignment: Qt.AlignVCenter
    }

    Item {
        visible: !root.roomy
        Layout.fillWidth: true
    }

    Rectangle {
        objectName: "statusDot"
        Layout.preferredWidth: 8
        Layout.preferredHeight: 8
        radius: 4
        color: panel.statusOk ? Theme.ok : Theme.err
        Accessible.role: Accessible.StaticText
        Accessible.name: panel.statusText
    }
    Item {
        objectName: "settingsButton"
        Layout.preferredWidth: 44
        Layout.preferredHeight: 44
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: qsTr("Settings")
        Keys.onReturnPressed: root.openSettings()

        LineIcon {
            anchors.centerIn: parent
            width: 24
            height: 24
            name: "sliders"
            color: parent.activeFocus ? Theme.gold : Theme.muted
        }
        MouseArea {
            anchors.fill: parent
            onClicked: root.openSettings()
        }
    }
}
