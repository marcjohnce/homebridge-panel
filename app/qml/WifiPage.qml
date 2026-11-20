import QtQuick
import QtQuick.Layouts

// Settings → Wi-Fi for guests → Wi-Fi QR code: after the PIN, a QR code of the Wi-Fi that guests
// scan with the phone camera, with name and password for typing. Hidden again after two minutes.
Rectangle {
    id: root

    signal closed

    property var code: null              // answer of panel.wifiCode once the PIN was right
    property string error: ""
    readonly property bool wide: width > height
    readonly property bool pinSet: panel.alarmPinSet

    function show() {
        if (pad.entry.length < 4)
            return;
        const pin = pad.entry;
        Busy.run(qsTr("Reading the Wi-Fi …"), () => {
            const res = panel.wifiCode(pin);
            pad.entry = "";
            if (res.error !== "") {
                pad.forceActiveFocus();
                if (res.wrong_pin)
                    pad.error = res.error;
                else
                    root.error = res.error;
            } else {
                root.error = "";
                root.code = res;
                hideTimer.restart();
            }
        });
    }
    function hide() {
        code = null;
        pad.forceActiveFocus();
    }

    color: Theme.page
    focus: true
    Keys.onEscapePressed: root.closed()
    Component.onCompleted: pad.forceActiveFocus()

    Timer {
        id: hideTimer
        interval: 120000
        onTriggered: root.hide()
    }

    MouseArea {
        anchors.fill: parent
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 28
        anchors.rightMargin: 28
        anchors.topMargin: 18
        anchors.bottomMargin: 18
        spacing: Theme.s(10)

        BackHeader {
            Layout.fillWidth: true
            backText: qsTr("Settings")
            title: qsTr("Wi-Fi QR code")
            onBack: root.closed()
        }

        // PIN first
        GridLayout {
            visible: root.code === null
            Layout.fillWidth: true
            Layout.topMargin: Theme.s(10)
            columns: root.wide ? 2 : 1
            columnSpacing: Theme.s(48)
            rowSpacing: Theme.s(20)

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: Theme.s(12)
                Text {
                    Layout.fillWidth: true
                    text: root.pinSet ? qsTr("Enter the PIN to show the QR code of the Wi-Fi. Guests scan it with the phone camera to join.")
                                      : qsTr("The Wi-Fi code is protected with the PIN of the panel. Set a PIN under Security first.")
                    color: Theme.ink
                    font.pixelSize: Theme.s(17)
                    wrapMode: Text.WordWrap
                }
                Text {
                    objectName: "wifiError"
                    Layout.fillWidth: true
                    visible: root.error !== ""
                    text: root.error
                    color: Theme.err
                    font.pixelSize: Theme.s(15)
                    wrapMode: Text.WordWrap
                }
            }

            ColumnLayout {
                visible: root.pinSet
                Layout.preferredWidth: Theme.s(330)
                Layout.alignment: Qt.AlignTop | (root.wide ? Qt.AlignRight : Qt.AlignHCenter)
                spacing: Theme.s(12)
                PinPad {
                    id: pad
                    objectName: "wifiPin"
                    Layout.fillWidth: true
                    onSubmitted: root.show()
                    onEntryChanged: if (entry !== "") root.error = ""
                }
                PillButton {
                    objectName: "wifiShow"
                    Layout.alignment: Qt.AlignRight
                    primary: true
                    text: qsTr("Show code")
                    enabled: pad.entry.length >= 4
                    onClicked: root.show()
                }
            }
        }

        Item {
            visible: root.code === null
            Layout.fillHeight: true
        }

        // the code
        GridLayout {
            visible: root.code !== null
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: root.wide ? 2 : 1
            columnSpacing: Theme.s(48)
            rowSpacing: Theme.s(20)

            Rectangle {
                id: card
                // white around the code in every theme, so phones read it reliably; the size comes
                // from the page (not the layout), about half of it
                readonly property real side: root.wide ? Math.min(root.height - Theme.s(150), (root.width - 56) * 0.5)
                                                       : Math.min(root.width - 56, root.height * 0.5)
                Layout.preferredWidth: side
                Layout.preferredHeight: side
                Layout.alignment: Qt.AlignTop | Qt.AlignHCenter
                radius: Theme.s(14)
                color: "#ffffff"
                Image {
                    id: qr
                    objectName: "wifiQr"
                    // whole pixels per module: every square of the code the same size
                    readonly property int modulePx: implicitWidth > 0 ? Math.max(1, Math.floor((card.side - Theme.s(12)) / implicitWidth)) : 1
                    anchors.centerIn: parent
                    width: implicitWidth * modulePx
                    height: implicitHeight * modulePx
                    source: root.code ? root.code.image : ""
                    smooth: false
                    Accessible.name: qsTr("Wi-Fi QR code")
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: Theme.s(6)
                Text {
                    text: qsTr("Network")
                    color: Theme.muted
                    font.pixelSize: Theme.s(15)
                }
                Text {
                    objectName: "wifiSsid"
                    Layout.fillWidth: true
                    text: root.code ? root.code.ssid : ""
                    color: Theme.ink
                    font.pixelSize: Theme.s(24)
                    font.weight: Font.Medium
                    wrapMode: Text.WrapAnywhere
                }
                Text {
                    Layout.topMargin: Theme.s(14)
                    visible: !!root.code && root.code.password !== ""
                    text: qsTr("Password")
                    color: Theme.muted
                    font.pixelSize: Theme.s(15)
                }
                Text {
                    objectName: "wifiPassword"
                    Layout.fillWidth: true
                    visible: !!root.code && root.code.password !== ""
                    text: root.code ? root.code.password : ""
                    color: Theme.ink
                    font.pixelSize: Theme.s(24)
                    font.weight: Font.Medium
                    wrapMode: Text.WrapAnywhere
                }
                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: Theme.s(14)
                    text: qsTr("Point the phone camera at the code and tap the notification. The code disappears after two minutes.")
                    color: Theme.muted
                    font.pixelSize: Theme.s(15)
                    wrapMode: Text.WordWrap
                }
                PillButton {
                    objectName: "wifiHide"
                    Layout.topMargin: Theme.s(12)
                    text: qsTr("Hide")
                    onClicked: root.hide()
                }
            }
        }
    }
}
