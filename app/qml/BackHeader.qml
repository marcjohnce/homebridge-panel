import QtQuick
import QtQuick.Layouts

// Kopfzeile „‹ Zurück | Titel“ für Detail- und Einstellungsseite
RowLayout {
    id: root

    property string backText
    property string title
    property string note
    property color noteColor: Theme.muted
    signal back

    spacing: 14

    Item {
        Layout.preferredWidth: backRow.implicitWidth + 12
        Layout.preferredHeight: 48
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: qsTr("Zurück zu %1").arg(root.backText)
        Keys.onReturnPressed: root.back()

        Row {
            id: backRow
            anchors.verticalCenter: parent.verticalCenter
            spacing: 4
            LineIcon {
                anchors.verticalCenter: parent.verticalCenter
                width: 22
                height: 22
                name: "back"
                color: Theme.muted
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: root.backText
                color: Theme.muted
                font.pixelSize: 17
            }
        }
        Rectangle {
            anchors.fill: parent
            radius: 6
            color: "transparent"
            border.color: Theme.gold
            border.width: 2
            visible: parent.activeFocus
        }
        MouseArea {
            anchors.fill: parent
            onClicked: root.back()
        }
    }

    Rectangle {
        Layout.preferredWidth: 1
        Layout.preferredHeight: 20
        color: Theme.line
    }

    Text {
        Layout.fillWidth: true
        text: root.title
        color: Theme.ink
        font.pixelSize: 20
        font.weight: Font.Medium
        elide: Text.ElideRight
        Accessible.role: Accessible.Heading
    }

    Text {
        text: root.note
        visible: text !== ""
        color: root.noteColor
        font.pixelSize: 15
    }
}
