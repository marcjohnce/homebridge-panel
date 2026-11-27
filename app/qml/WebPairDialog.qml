import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// "Connect a browser" (Settings → System): the address of the web setup and a code that is
// valid for five minutes; the QR code opens the page with the code filled in. Closes itself
// once a browser has connected.
Popup {
    id: root

    property var code: ({})              // answer of panel.web.newCode
    readonly property bool wide: parent ? parent.width > parent.height : true
    readonly property real side: !parent ? 0
        : wide ? Math.min(parent.height - Theme.s(80), (parent.width - Theme.s(120)) * 0.45)
               : Math.min(parent.width - Theme.s(100), parent.height * 0.45)

    function show() {
        code = panel.web.newCode();
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

    Connections {
        target: panel.web
        function onPaired() {
            if (root.opened) {
                root.close();
                panel.toast(qsTr("Browser connected."));
            }
        }
    }
    Timer {
        interval: 300000             // the code is no longer valid
        running: root.opened
        onTriggered: root.close()
    }

    contentItem: GridLayout {
        columns: root.wide ? 2 : 1
        columnSpacing: Theme.s(32)
        rowSpacing: Theme.s(20)

        Text {
            objectName: "webError"
            visible: !!root.code.error
            Layout.preferredWidth: Theme.s(380)
            text: root.code.error || ""
            color: Theme.ink
            font.pixelSize: Theme.s(17)
            wrapMode: Text.WordWrap
        }

        Rectangle {
            visible: !!root.code.image
            Layout.preferredWidth: root.side
            Layout.preferredHeight: root.side
            Layout.alignment: Qt.AlignHCenter
            radius: Theme.s(14)
            color: "#ffffff"
            Image {
                objectName: "webQr"
                readonly property int modulePx: implicitWidth > 0 ? Math.max(1, Math.floor((root.side - Theme.s(12)) / implicitWidth)) : 1
                anchors.centerIn: parent
                width: implicitWidth * modulePx
                height: implicitHeight * modulePx
                source: root.code.image || ""
                smooth: false
                Accessible.name: qsTr("QR code of the web setup")
            }
        }

        ColumnLayout {
            Layout.preferredWidth: Theme.s(340)
            Layout.alignment: Qt.AlignVCenter
            spacing: Theme.s(6)
            Text {
                visible: !!root.code.url
                text: qsTr("Address")
                color: Theme.muted
                font.pixelSize: Theme.s(15)
            }
            Text {
                objectName: "webUrl"
                visible: !!root.code.url
                Layout.fillWidth: true
                text: root.code.url || ""
                color: Theme.ink
                font.pixelSize: Theme.s(22)
                wrapMode: Text.WrapAnywhere
            }
            Text {
                Layout.topMargin: Theme.s(14)
                visible: !!root.code.code
                text: qsTr("Code")
                color: Theme.muted
                font.pixelSize: Theme.s(15)
            }
            Text {
                objectName: "webCode"
                visible: !!root.code.code
                text: root.code.code || ""
                color: Theme.ink
                font.pixelSize: Theme.s(44)
                font.weight: Font.Light
                font.letterSpacing: 2
            }
            Text {
                visible: !!root.code.code
                Layout.fillWidth: true
                Layout.topMargin: Theme.s(10)
                text: qsTr("Open the address in a browser on a computer or phone in the same network and enter the code, or scan the QR code. The code is valid for 5 minutes.")
                color: Theme.muted
                font.pixelSize: Theme.s(15)
                wrapMode: Text.WordWrap
            }
            PillButton {
                objectName: "webClose"
                Layout.topMargin: Theme.s(12)
                text: qsTr("Close")
                onClicked: root.close()
            }
        }
    }
}
