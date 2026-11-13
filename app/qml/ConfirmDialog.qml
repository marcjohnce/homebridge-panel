import QtQuick
import QtQuick.Controls.Basic

// Asks before running an action such as a restart
Popup {
    id: root

    property var field: ({})
    signal confirmed(string key)

    function ask(f) {
        field = f;
        open();
    }

    anchors.centerIn: Overlay.overlay
    width: Math.min(Theme.s(440), parent ? parent.width - 40 : Theme.s(440))
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

    contentItem: Column {
        spacing: Theme.s(16)
        focus: true
        Keys.onReturnPressed: confirmButton.clicked()

        Text {
            width: parent.width
            text: root.field.label || ""
            color: Theme.ink
            font.pixelSize: Theme.s(19)
            font.weight: Font.Medium
            Accessible.role: Accessible.Heading
        }
        Text {
            width: parent.width
            text: root.field.confirm || ""
            color: Theme.muted
            font.pixelSize: Theme.s(16)
            wrapMode: Text.WordWrap
        }
        Row {
            anchors.right: parent.right
            spacing: 10
            PillButton {
                objectName: "confirmCancel"
                text: qsTr("Cancel")
                onClicked: root.close()
            }
            PillButton {
                id: confirmButton
                objectName: "confirmOk"
                primary: true
                text: root.field.button || qsTr("OK")
                onClicked: {
                    root.close();
                    root.confirmed(root.field.key);
                }
            }
        }
    }
}
