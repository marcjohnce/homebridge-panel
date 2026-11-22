import QtQuick
import QtQuick.Layouts
import "Categories.js" as Categories

// Menu of the sidebar: Favorites, Lights, Scenes, Climate, Security with a short status on the right
ColumnLayout {
    id: root

    property bool compact: false
    property real maxEntryHeight: Infinity      // set by the sidebar: the whole menu must fit
    readonly property int count: Categories.shown(panel.hasEnergy, panel.hasWeather).length
    readonly property var labels: ({ favorites: qsTr("Favorites"), light: qsTr("Lights"), scenes: qsTr("Scenes"),
                                     climate: qsTr("Climate"), weather: qsTr("Weather"),
                                     energy: qsTr("Energy"), security: qsTr("Security") })

    objectName: "categoryMenu"
    spacing: compact ? 0 : 6

    Repeater {
        model: Categories.shown(panel.hasEnergy, panel.hasWeather)
        Rectangle {
            id: entry
            required property string modelData
            readonly property bool selected: panel.category === modelData
            readonly property string detail: panel.summary[modelData] || ""
            readonly property bool warn: modelData === "security" && panel.securityCount > 0

            objectName: "category:" + modelData
            Layout.fillWidth: true
            Layout.leftMargin: -14
            Layout.preferredHeight: Math.max(30, Math.min(root.compact ? 38 : Theme.s(52), root.maxEntryHeight))
            radius: 12
            color: selected ? Theme.goldSoft : (mouse.pressed ? Theme.tilePress : "transparent")
            border.color: Theme.gold
            border.width: activeFocus ? 2 : 0
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: detail !== "" ? qsTr("%1: %2").arg(root.labels[modelData]).arg(detail) : root.labels[modelData]
            Accessible.checked: selected
            Keys.onReturnPressed: panel.selectCategory(modelData)
            Keys.onSpacePressed: panel.selectCategory(modelData)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 12
                spacing: 14
                LineIcon {
                    Layout.preferredWidth: Theme.s(24)
                    Layout.preferredHeight: Theme.s(24)
                    lineWidth: 1.4
                    name: Categories.icons[entry.modelData]
                    color: entry.selected ? Theme.gold : Theme.muted
                }
                Text {
                    Layout.fillWidth: true
                    text: root.labels[entry.modelData]
                    color: Theme.ink
                    font.pixelSize: Theme.s(18)
                    font.weight: entry.selected ? Font.Medium : Font.Normal
                    elide: Text.ElideRight
                }
                Text {
                    objectName: "categoryDetail:" + entry.modelData
                    text: entry.detail
                    visible: text !== ""
                    color: entry.warn ? Theme.err : Theme.muted
                    font.pixelSize: Theme.s(13)
                    font.weight: entry.warn ? Font.Medium : Font.Normal
                }
            }
            MouseArea {
                id: mouse
                anchors.fill: parent
                onClicked: panel.selectCategory(entry.modelData)
            }
        }
    }
}
