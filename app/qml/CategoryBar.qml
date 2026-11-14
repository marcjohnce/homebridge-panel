import QtQuick
import "Categories.js" as Categories

// Menu for the top bar (square and portrait screens): icon-only buttons, a red count on Security
Row {
    id: root

    readonly property var labels: ({ light: qsTr("Lights"), climate: qsTr("Climate"),
                                     security: qsTr("Security") })

    objectName: "categoryMenu"
    spacing: 8

    Repeater {
        model: Categories.keys
        Rectangle {
            id: button
            required property string modelData
            readonly property bool selected: panel.category === modelData
            readonly property int alerts: modelData === "security" ? panel.securityCount : 0

            objectName: "category:" + modelData
            width: 56
            height: 52
            radius: 14
            color: selected ? Theme.goldSoft : (mouse.pressed ? Theme.tilePress : "transparent")
            border.color: selected || activeFocus ? Theme.gold : "transparent"
            border.width: activeFocus ? 2 : 1
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: alerts > 0 ? qsTr("%1: %2").arg(root.labels[modelData]).arg(panel.summary.security)
                                        : root.labels[modelData]
            Accessible.checked: selected
            Keys.onReturnPressed: panel.selectCategory(modelData)
            Keys.onSpacePressed: panel.selectCategory(modelData)

            LineIcon {
                anchors.centerIn: parent
                width: 26
                height: 26
                lineWidth: 1.4
                name: Categories.icons[button.modelData]
                color: button.selected ? Theme.gold : Theme.muted
            }
            Rectangle {
                visible: button.alerts > 0
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: 4
                width: Math.max(18, badgeText.implicitWidth + 8)
                height: 18
                radius: 9
                color: Theme.err
                Text {
                    id: badgeText
                    anchors.centerIn: parent
                    text: button.alerts
                    color: Theme.alarmInk
                    font.pixelSize: 11
                    font.weight: Font.Medium
                }
            }
            MouseArea {
                id: mouse
                anchors.fill: parent
                onClicked: panel.selectCategory(button.modelData)
            }
        }
    }
}
