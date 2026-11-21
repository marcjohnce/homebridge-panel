import QtQuick
import QtQuick.Layouts

// Settings → System → Backups: save the panel settings (rooms, names, favorites, groups,
// virtual devices, display, connection) and put them back later; restoring restarts the app.
// With MQTT set up, the shared part can also be saved on the broker and loaded by other panels.
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
    // Sharing over MQTT: look what is on the broker first, then ask before overwriting / loading
    function saveShared() {
        Busy.run(qsTr("Looking on the MQTT broker …"), () => {
            const info = panel.settings.sharedInfo();
            if (info.error !== "") {
                root.messageError = true;
                root.message = info.error;
            } else if (info.empty) {
                root.saveSharedNow();
            } else {
                confirm.ask({
                    key: "shareSave:",
                    label: qsTr("Save to MQTT"),
                    button: qsTr("Overwrite"),
                    confirm: qsTr("Overwrite the settings %1 saved on %2 (%3)?")
                             .arg(info.panel).arg(root.created(info.saved)).arg(info.text)
                });
            }
        });
    }
    function saveSharedNow() {
        Busy.run(qsTr("Saving …"), () => {
            const err = panel.settings.saveShared();
            root.messageError = err !== "";
            root.message = err !== "" ? err : qsTr("Saved on the MQTT broker. Other panels can load it now.");
        });
    }
    function loadShared() {
        Busy.run(qsTr("Looking on the MQTT broker …"), () => {
            const info = panel.settings.sharedInfo();
            if (info.error !== "" || info.empty) {
                root.messageError = info.error !== "";
                root.message = info.error !== "" ? info.error : qsTr("Nothing saved on the MQTT broker yet.");
                return;
            }
            confirm.ask({
                key: "shareLoad:",
                label: qsTr("Load from MQTT"),
                button: qsTr("Load"),
                confirm: qsTr("Load the settings %1 saved on %2 (%3)? Rooms, names, groups, virtual devices and scenes are replaced; favorites, display settings and PINs stay. A backup is made first, then the app restarts.")
                         .arg(info.panel).arg(root.created(info.saved)).arg(info.text)
            });
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
                    text: qsTr("A backup holds rooms, device names, favorites, groups, virtual devices, scenes and all settings of this page. Restoring one replaces the current settings and restarts the app.")
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

                // ---------- share with other panels (MQTT) ----------
                Text {
                    objectName: "shareTitle"
                    visible: panel.settings.sharingAvailable
                    Layout.fillWidth: true
                    Layout.topMargin: Theme.s(22)
                    leftPadding: 4
                    text: qsTr("Share with other panels")
                    color: Theme.muted
                    font.pixelSize: Theme.s(15)
                    Accessible.role: Accessible.Heading
                }
                Text {
                    visible: panel.settings.sharingAvailable
                    Layout.fillWidth: true
                    leftPadding: 4
                    text: qsTr("Saves rooms, names, kinds, groups, virtual devices and scenes on the MQTT broker, where other panels can load them. Favorites, display settings and PINs stay on each panel.")
                    color: Theme.muted
                    font.pixelSize: Theme.s(15)
                    wrapMode: Text.WordWrap
                }
                Flow {
                    visible: panel.settings.sharingAvailable
                    Layout.fillWidth: true
                    spacing: Theme.s(10)
                    PillButton {
                        objectName: "shareSave"
                        iconName: "up"
                        text: qsTr("Save to MQTT")
                        onClicked: root.saveShared()
                    }
                    PillButton {
                        objectName: "shareLoad"
                        iconName: "down"
                        text: qsTr("Load from MQTT")
                        onClicked: root.loadShared()
                    }
                }
            }
        }
    }

    ConfirmDialog {
        id: confirm
        objectName: "backupConfirm"
        onConfirmed: key => {
            const name = key.substring(key.indexOf(":") + 1);
            if (key === "shareSave:")
                root.saveSharedNow();
            else if (key === "shareLoad:")
                Busy.run(qsTr("Loading …"), () => {
                    root.message = panel.settings.loadShared();
                    root.messageError = root.message !== "";
                });
            else if (key.startsWith("restore:"))
                Busy.run(qsTr("Restoring …"), () => {
                    root.message = panel.settings.restoreBackup(name);
                    root.messageError = root.message !== "";
                });
            else
                panel.settings.deleteBackup(name);
        }
    }
}
