import QtQuick
import QtQuick.Layouts

// A section of the settings page. "instant": save immediately, otherwise via "Apply" (bottom bar).
ColumnLayout {
    id: root

    required property var section
    property var draft: ({})
    property var errors: ({})
    signal edit(string key, var value)
    signal editRequested(var field, var value)

    spacing: 10

    function current(f) {
        return draft.hasOwnProperty(f.key) ? draft[f.key] : f.value;
    }

    Text {
        Layout.leftMargin: 4
        Layout.topMargin: 14
        text: root.section.title
        color: Theme.muted
        font.pixelSize: 15
        Accessible.role: Accessible.Heading
    }

    Rectangle {
        objectName: "section:" + root.section.id
        Layout.fillWidth: true
        Layout.preferredHeight: fieldColumn.implicitHeight
        radius: 14
        color: Theme.tile

        Column {
            id: fieldColumn
            width: parent.width
            Repeater {
                model: root.section.fields
                Column {
                    id: fieldItem
                    required property var modelData
                    required property int index
                    width: fieldColumn.width

                    Rectangle {
                        visible: fieldItem.index > 0
                        width: parent.width - 36
                        x: 18
                        height: 1
                        color: Theme.line
                    }
                    SettingRow {
                        objectName: "row:" + fieldItem.modelData.key
                        width: parent.width
                        field: fieldItem.modelData
                        value: root.current(fieldItem.modelData)
                        error: root.errors[fieldItem.modelData.key] || ""
                        onEdited: value => root.edit(fieldItem.modelData.key, value)
                        onEditRequested: root.editRequested(fieldItem.modelData, root.current(fieldItem.modelData))
                    }
                }
            }
        }
    }
}
