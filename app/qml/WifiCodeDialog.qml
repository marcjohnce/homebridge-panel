import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// The guest Wi-Fi as a QR code (tile "Wi-Fi QR code" in the favorites): guests scan it with the
// phone camera; name and password for typing next to it.
Popup {
    id: root

    property var code: ({})              // answer of panel.wifiCode
    readonly property bool wide: parent ? parent.width > parent.height : true
    readonly property real side: !parent ? 0
        : wide ? Math.min(parent.height - Theme.s(80), (parent.width - Theme.s(120)) * 0.5)
               : Math.min(parent.width - Theme.s(100), parent.height * 0.5)

    function show() {
        code = panel.wifiCode();
        open();
    }

    anchors.centerIn: Overlay.overlay
    padding: Theme.s(24)
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    Overlay.modal: Rectangle {
        color: Qt.rgba(0, 0, 0, 0.35)
    }
    background: Rectangle {
        radius: 18
        color: Theme.tile
    }

    contentItem: GridLayout {
        columns: root.wide ? 2 : 1
        columnSpacing: Theme.s(32)
        rowSpacing: Theme.s(20)

        Text {
            objectName: "wifiError"
            visible: root.code.error !== undefined && root.code.error !== ""
            Layout.preferredWidth: Theme.s(380)
            text: root.code.error || ""
            color: Theme.ink
            font.pixelSize: Theme.s(17)
            wrapMode: Text.WordWrap
        }

        Rectangle {
            id: card
            // white around the code in every theme, so phones read it reliably
            visible: !!root.code.image
            Layout.preferredWidth: root.side
            Layout.preferredHeight: root.side
            Layout.alignment: Qt.AlignHCenter
            radius: Theme.s(14)
            color: "#ffffff"
            Image {
                objectName: "wifiQr"
                // whole pixels per module: every square of the code the same size
                readonly property int modulePx: implicitWidth > 0 ? Math.max(1, Math.floor((root.side - Theme.s(12)) / implicitWidth)) : 1
                anchors.centerIn: parent
                width: implicitWidth * modulePx
                height: implicitHeight * modulePx
                source: root.code.image || ""
                smooth: false
                Accessible.name: qsTr("Wi-Fi QR code")
            }
        }

        ColumnLayout {
            Layout.preferredWidth: Theme.s(300)
            Layout.alignment: Qt.AlignVCenter
            spacing: Theme.s(6)
            Text {
                visible: !!root.code.image
                text: qsTr("Network")
                color: Theme.muted
                font.pixelSize: Theme.s(15)
            }
            Text {
                objectName: "wifiSsid"
                visible: !!root.code.image
                Layout.fillWidth: true
                text: root.code.ssid || ""
                color: Theme.ink
                font.pixelSize: Theme.s(24)
                font.weight: Font.Medium
                wrapMode: Text.WrapAnywhere
            }
            Text {
                Layout.topMargin: Theme.s(14)
                visible: !!root.code.password
                text: qsTr("Password")
                color: Theme.muted
                font.pixelSize: Theme.s(15)
            }
            Text {
                objectName: "wifiPassword"
                visible: !!root.code.password
                Layout.fillWidth: true
                text: root.code.password || ""
                color: Theme.ink
                font.pixelSize: Theme.s(24)
                font.weight: Font.Medium
                wrapMode: Text.WrapAnywhere
            }
            Text {
                visible: !!root.code.image
                Layout.fillWidth: true
                Layout.topMargin: Theme.s(14)
                text: qsTr("Point the phone camera at the code and tap the notification.")
                color: Theme.muted
                font.pixelSize: Theme.s(15)
                wrapMode: Text.WordWrap
            }
            PillButton {
                objectName: "wifiClose"
                Layout.topMargin: Theme.s(12)
                text: qsTr("Close")
                onClicked: root.close()
            }
        }
    }
}
