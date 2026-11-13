import QtQuick
import QtQuick.Layouts

// One setting: label on the left, matching control on the right (depending on kind)
Item {
    id: root

    required property var field
    property var value
    property string error
    signal edited(var value)
    signal editRequested
    signal actionRequested

    implicitHeight: Math.max(Theme.s(68), row.implicitHeight + 24)

    RowLayout {
        id: row
        anchors.fill: parent
        anchors.leftMargin: 18
        anchors.rightMargin: 14
        spacing: 16

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Text {
                Layout.fillWidth: true
                text: root.field.label
                color: Theme.ink
                font.pixelSize: Theme.s(17)
                wrapMode: Text.WordWrap
            }
            Text {
                Layout.fillWidth: true
                visible: text !== ""
                text: root.error !== "" ? root.error : root.field.help
                color: root.error !== "" ? Theme.err : Theme.muted
                font.pixelSize: Theme.s(13)
                wrapMode: Text.WordWrap
            }
        }

        Loader {
            Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
            sourceComponent: root.field.kind === "choice" ? choiceComponent
                           : root.field.kind === "toggle" ? toggleComponent
                           : root.field.kind === "action" ? actionComponent : valueComponent
        }
    }

    Component {
        id: choiceComponent
        Row {
            spacing: 20
            Repeater {
                model: root.field.options
                UnderlineButton {
                    required property var modelData
                    text: modelData.label
                    pixelSize: Theme.s(16)
                    centered: true
                    selected: String(modelData.value) === String(root.value)
                    onClicked: root.edited(modelData.value)
                }
            }
        }
    }

    Component {
        id: toggleComponent
        Rectangle {
            width: Theme.s(54)
            height: Theme.s(32)
            radius: 16
            color: root.value ? Theme.gold : Theme.line
            border.color: activeFocus ? Theme.ink : "transparent"
            border.width: 2
            activeFocusOnTab: true
            Accessible.role: Accessible.CheckBox
            Accessible.name: root.field.label
            Accessible.checked: !!root.value
            Keys.onSpacePressed: root.edited(!root.value)

            Behavior on color { ColorAnimation { duration: 150 } }

            Rectangle {
                width: parent.height - 6
                height: parent.height - 6
                radius: height / 2
                y: 3
                x: root.value ? parent.width - width - 3 : 3
                color: Theme.knob
                Behavior on x { NumberAnimation { duration: 150 } }
            }
            MouseArea {
                anchors.fill: parent
                anchors.margins: -8
                onClicked: root.edited(!root.value)
            }
        }
    }

    Component {
        id: actionComponent
        PillButton {
            objectName: "action:" + root.field.key
            text: root.field.button || root.field.label
            onClicked: root.actionRequested()
        }
    }

    Component {
        id: valueComponent
        Item {
            implicitWidth: valueRow.implicitWidth + 16
            implicitHeight: Theme.s(48)
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: qsTr("Change %1, currently %2").arg(root.field.label).arg(String(root.value))
            Keys.onReturnPressed: root.editRequested()

            Row {
                id: valueRow
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right
                spacing: 6
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: String(root.value)
                    color: Theme.ink
                    font.pixelSize: Theme.s(18)
                    font.weight: Font.Light
                }
                LineIcon {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 20
                    height: 20
                    name: "chevron"
                    color: Theme.muted
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
                onClicked: root.editRequested()
            }
        }
    }
}
