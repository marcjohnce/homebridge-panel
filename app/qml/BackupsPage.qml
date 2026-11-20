import QtQuick
import QtQuick.Layouts

// Settings → System → Backups: save the panel settings (rooms, names, favorites, groups,
// virtual devices, display, connection) and put them back later; restoring restarts the app.
Rectangle {
    id: root

    property string message
    property bool messageError: false
    signal closed

    readonly property var backups: panel.settings.backups

    function create() {
        Busy.run(qsTr("Saving …"), () => {
            const err = panel.settings.createBackup();
            root.messageError = err !== "";
            root.message = err !== "" ? err : qsTr("Backup created.");
        });
    }
    function created(iso) {
        return new Date(iso).toLocaleString(Theme.locale, "dddd, d MMMM yyyy, HH:mm");
    }

    color: Theme.page
    focus: true
    Keys.onEscapePressed: root.closed()

    MouseArea {
        anchors.fill: parent
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 28
        anchors.rightMargin: 28
        anchors.topMargin: 18
        spacing: 4

        BackHeader {
            Layout.fillWidth: true
            backText: qsTr("Settings")
            title: qsTr("Backups")
            onBack: root.closed()
        }

        Flickable {
            objectName: "backupsFlick"
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: content.implicitHeight + Theme.s(24)
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            ColumnLayout {
                id: content
                width: Math.min(parent.width, Theme.s(760))
                x: (parent.width - width) / 2
                spacing: Theme.s(12)

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: Theme.s(10)
                    leftPadding: 4
                    text: qsTr("A backup holds rooms, device names, favorites, groups, virtual devices and all settings of this page. Restoring one replaces the current settings and restarts the app.")
                    color: Theme.muted
                    font.pixelSize: Theme.s(15)
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.s(16)
                    PillButton {
                        objectName: "createBackup"
                        primary: true
                        iconName: "plus"
                        text: qsTr("Create backup")
                        onClicked: root.create()
                    }
                    Text {
                        objectName: "backupMessage"
                        Layout.fillWidth: true
                        text: root.message
                        color: root.messageError ? Theme.err : Theme.muted
                        font.pixelSize: Theme.s(15)
                        wrapMode: Text.WordWrap
                    }
                }

                Text {
                    visible: root.backups.length === 0
                    Layout.fillWidth: true
                    Layout.topMargin: Theme.s(10)
                    leftPadding: 4
                    text: qsTr("No backups yet.")
                    color: Theme.muted
                    font.pixelSize: Theme.s(17)
                }

                Rectangle {
                    visible: root.backups.length > 0
                    Layout.fillWidth: true
                    Layout.preferredHeight: list.implicitHeight
                    radius: 14
                    color: Theme.tile

                    Column {
                        id: list
                        width: parent.width
                        Repeater {
                            model: root.backups
                            Item {
                                id: row
                                required property var modelData
                                required property int index
                                objectName: "backup:" + modelData.name
                                width: list.width
                                height: Math.max(Theme.s(72), texts.implicitHeight + 20)

                                Rectangle {
                                    visible: row.index > 0
                                    x: 18
                                    width: parent.width - 36
                                    height: 1
                                    color: Theme.line
                                }
                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 18
                                    anchors.rightMargin: 10
                                    spacing: 12
                                    Column {
                                        id: texts
                                        Layout.fillWidth: true
                                        spacing: 2
                                        Text {
                                            width: parent.width
                                            text: root.created(row.modelData.created)
                                            elide: Text.ElideRight
                                            color: Theme.ink
                                            font.pixelSize: Theme.s(17)
                                        }
                                        Text {
                                            width: parent.width
                                            text: row.modelData.text
                                            elide: Text.ElideRight
                                            color: Theme.muted
                                            font.pixelSize: Theme.s(13)
                                        }
                                    }
                                    PillButton {
                                        objectName: "restore:" + row.modelData.name
                                        text: qsTr("Restore")
                                        onClicked: confirm.ask({
                                            key: "restore:" + row.modelData.name,
                                            label: qsTr("Restore backup"),
                                            button: qsTr("Restore"),
                                            confirm: qsTr("Restore the backup of %1? The current settings are replaced and the app restarts.")
                                                     .arg(root.created(row.modelData.created))
                                        })
                                    }
                                    IconButton {
                                        objectName: "deleteBackup:" + row.modelData.name
                                        iconName: "trash"
                                        label: qsTr("Delete backup of %1").arg(root.created(row.modelData.created))
                                        onClicked: confirm.ask({
                                            key: "delete:" + row.modelData.name,
                                            label: qsTr("Delete backup"),
                                            button: qsTr("Delete"),
                                            confirm: qsTr("Delete the backup of %1?").arg(root.created(row.modelData.created))
                                        })
                                    }
                                }
                            }
                        }
                    }
                }

                Text {
                    visible: root.backups.length > 0
                    Layout.fillWidth: true
                    leftPadding: 4
                    text: qsTr("Folder: %1").arg(panel.settings.backupFolder)
                    color: Theme.muted
                    font.pixelSize: Theme.s(13)
                    wrapMode: Text.WrapAnywhere
                }
            }
        }
    }

    ConfirmDialog {
        id: confirm
        objectName: "backupConfirm"
        onConfirmed: key => {
            const name = key.substring(key.indexOf(":") + 1);
            if (key.startsWith("restore:"))
                Busy.run(qsTr("Restoring …"), () => {
                    root.message = panel.settings.restoreBackup(name);
                    root.messageError = root.message !== "";
                });
            else
                panel.settings.deleteBackup(name);
        }
    }
}
