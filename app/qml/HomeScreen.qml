import QtQuick
import QtQuick.Layouts

RowLayout {
    id: root

    signal openDetail(string id)
    signal openSettings

    readonly property bool compact: height < 520
    spacing: 0

    SideBar {
        Layout.preferredWidth: root.compact ? 196 : 220
        Layout.maximumWidth: Layout.preferredWidth
        Layout.fillWidth: false
        Layout.fillHeight: true
        Layout.leftMargin: root.compact ? 22 : 30
        Layout.rightMargin: root.compact ? 14 : 22
        Layout.topMargin: root.compact ? 18 : 28
        Layout.bottomMargin: 14
        compact: root.compact
        onOpenSettings: root.openSettings()
    }

    ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.topMargin: root.compact ? 12 : 20
        Layout.rightMargin: 24
        Layout.leftMargin: 6
        spacing: 12

        RoomTabs {
            Layout.fillWidth: true
            Layout.preferredHeight: 44
        }
        TileGrid {
            Layout.fillWidth: true
            Layout.fillHeight: true
            onOpenDetail: id => root.openDetail(id)
        }
    }
}
