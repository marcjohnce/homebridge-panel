import QtQuick
import QtQuick.Layouts

// Wide screens: sidebar on the left. Square and portrait screens (e.g. 720×720):
// header on top, so the tile grid gets the full width.
Item {
    id: root

    signal openDetail(string id)
    signal openSettings

    readonly property bool topLayout: width / height < 1.4
    readonly property bool compact: height < 520

    Loader {
        anchors.fill: parent
        sourceComponent: root.topLayout ? topComponent : sideComponent
    }

    Component {
        id: sideComponent

        RowLayout {
            spacing: 0

            SideBar {
                Layout.preferredWidth: root.compact ? 196 : Theme.s(220)
                Layout.maximumWidth: Layout.preferredWidth
                Layout.fillWidth: false
                Layout.fillHeight: true
                Layout.leftMargin: root.compact ? 22 : Theme.s(30)
                Layout.rightMargin: root.compact ? 14 : Theme.s(22)
                Layout.topMargin: root.compact ? 18 : Theme.s(28)
                Layout.bottomMargin: 14
                compact: root.compact
                onOpenSettings: root.openSettings()
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.topMargin: root.compact ? 12 : Theme.s(20)
                Layout.rightMargin: Theme.s(24)
                Layout.leftMargin: 6
                spacing: Theme.s(12)

                RoomTabs {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Theme.s(44)
                }
                TileGrid {
                    visible: panel.category !== "scenes"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    onOpenDetail: id => root.openDetail(id)
                }
                SceneGrid {
                    visible: panel.category === "scenes"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                }
            }
        }
    }

    Component {
        id: topComponent

        ColumnLayout {
            spacing: 10

            TopBar {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 18
                Layout.topMargin: 12
                roomy: root.height > root.width * 1.2
                onOpenSettings: root.openSettings()
            }
            RoomTabs {
                Layout.fillWidth: true
                Layout.preferredHeight: 44
                Layout.leftMargin: 24
                Layout.rightMargin: 24
            }
            TileGrid {
                visible: panel.category !== "scenes"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                onOpenDetail: id => root.openDetail(id)
            }
            SceneGrid {
                visible: panel.category === "scenes"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
            }
        }
    }
}
