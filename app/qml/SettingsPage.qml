import QtQuick
import QtQuick.Layouts

// Settings. Sections marked "instant" save immediately; the others (Homebridge)
// collect changes that are tested and applied from the fixed bar at the bottom.
Rectangle {
    id: root

    property var draft: ({})
    property var errors: ({})
    property string message
    property bool messageOk: false
    property bool testing: false
    property string subPage: ""
    signal closed

    readonly property var sections: panel.settings.sections
    readonly property var changes: {
        const out = {};
        for (const sec of sections) {
            if (sec.instant)
                continue;
            for (const f of sec.fields) {
                if (draft.hasOwnProperty(f.key) && String(draft[f.key]) !== String(f.value))
                    out[f.key] = draft[f.key];
            }
        }
        return out;
    }
    readonly property bool dirty: Object.keys(changes).length > 0

    color: Theme.page
    focus: true
    Keys.onEscapePressed: root.closed()

    function current(key) {
        if (draft.hasOwnProperty(key))
            return draft[key];
        for (const sec of sections)
            for (const f of sec.fields)
                if (f.key === key)
                    return f.value;
        return undefined;
    }
    function setDraft(key, value) {
        const d = Object.assign({}, draft);
        d[key] = value;
        draft = d;
        const e = Object.assign({}, errors);
        delete e[key];
        errors = e;
        message = "";
    }
    function saveInstant(key, value) {
        const change = {};
        change[key] = value;
        Busy.run(qsTr("Saving …"), () => {
            const errs = panel.settings.save(change);
            root.errors = Object.assign({}, root.errors, errs);
        });
    }
    function apply() {
        Busy.run(qsTr("Saving …"), applyNow);
    }
    function applyNow() {
        const errs = panel.settings.save(changes);
        errors = errs;
        if (Object.keys(errs).length > 0) {
            messageOk = false;
            message = qsTr("Check the highlighted entries.");
            return;
        }
        draft = {};
        messageOk = true;
        message = qsTr("Applied. Reconnecting …");
    }
    // software update: install the release found (after a confirmation) or look again
    function update(field) {
        if (panel.updateInfo.install)
            confirm.ask({ key: "update", label: field.label, button: qsTr("Install"),
                          confirm: qsTr("Install version %1 now? The app restarts afterwards.").arg(panel.updateInfo.latest) });
        else
            panel.checkUpdate();
    }
    function testMqtt() {
        testing = true;
        message = "";
        panel.settings.testMqtt(current("mqtt_host"), current("mqtt_port"), current("mqtt_protocol"),
                                current("mqtt_user"), current("mqtt_password"));
    }
    // text and passwords with the on-screen keyboard, numbers and addresses with the keypad
    // instant: the section saves at once (e.g. Wi-Fi for guests), otherwise the entry waits for "Apply"
    function editValue(field, value, instant) {
        const take = v => instant ? root.saveInstant(field.key, v) : root.setDraft(field.key, v);
        if (field.kind === "text" || field.kind === "password") {
            textKeyboard.edit(field.label, String(value), text => {
                const err = panel.settings.validate(field.key, text);
                if (err === "")
                    take(text);
                return err;
            }, { hint: field.help, maxLength: 200, autoCapitalize: false, secret: field.kind === "password" });
        } else if (field.kind === "code") {
            // secret digits (alarm PIN): start empty, saved at once; empty = no PIN
            keypad.edit(field, "", v => root.saveInstant(field.key, v));
        } else {
            keypad.edit(field, value, take);
        }
    }
    function testConnection() {
        testing = true;
        message = "";
        panel.settings.testConnection(current("hap_host"), current("hap_port"), current("hap_pin"));
    }

    Connections {
        target: panel.settings
        function onTestFinished(ok, text) {
            root.testing = false;
            root.messageOk = ok;
            root.message = text;
        }
    }

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
            backText: qsTr("Overview")
            title: qsTr("Settings")
            onBack: root.closed()
        }

        Flickable {
            id: settingsFlickable
            objectName: "settingsFlick"
            layer.enabled: GraphicsInfo.api === GraphicsInfo.Software   // see TileGrid.qml

            // opaque background for the layer above (transparent layers render black in software mode)
            Rectangle {
                parent: settingsFlickable
                anchors.fill: parent
                z: -1
                visible: settingsFlickable.layer.enabled
                color: Theme.page
            }

            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: content.implicitHeight + 20
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            ColumnLayout {
                id: content
                width: Math.min(parent.width, Theme.s(760))
                x: (parent.width - width) / 2
                spacing: 8

                Repeater {
                    model: root.sections
                    SettingsSection {
                        required property var modelData
                        Layout.fillWidth: true
                        section: modelData
                        draft: root.draft
                        errors: root.errors
                        onEdit: (key, value) => section.instant ? root.saveInstant(key, value) : root.setDraft(key, value)
                        onEditRequested: (field, value) => root.editValue(field, value, section.instant)
                        onActionRequested: field => field.kind === "page" ? Busy.run(qsTr("Loading …"), () => root.subPage = field.key)
                                                 : field.kind === "update" ? root.update(field)
                                                 : field.key === "mqtt_test" ? root.testMqtt()
                                                 : field.confirm ? confirm.ask(field) : panel.settings.runAction(field.key)
                    }
                }

                InfoSection {
                    objectName: "infoSection"
                    Layout.fillWidth: true
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.line
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: Theme.s(72)
            spacing: 12

            Text {
                Layout.fillWidth: true
                text: root.testing ? qsTr("Testing connection …")
                    : root.message !== "" ? root.message
                    : root.dirty ? qsTr("Changes to the connections are not applied yet.")
                    : qsTr("Display settings are saved immediately.")
                color: root.testing || (root.message === "" && !root.dirty) ? Theme.muted
                     : root.message === "" ? Theme.ink : (root.messageOk ? Theme.ok : Theme.err)
                font.pixelSize: Theme.s(14)
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
            PillButton {
                objectName: "testButton"
                text: qsTr("Test Homebridge")
                enabled: !root.testing
                onClicked: root.testConnection()
            }
            PillButton {
                objectName: "applyButton"
                primary: true
                text: qsTr("Apply")
                enabled: root.dirty
                onClicked: root.apply()
            }
        }
    }

    Loader {
        anchors.fill: parent
        active: root.subPage === "rooms_page"
        sourceComponent: RoomsPage {
            objectName: "roomsPage"
            onClosed: {
                root.subPage = "";
                root.forceActiveFocus();
            }
        }
    }

    Loader {
        anchors.fill: parent
        active: root.subPage === "batteries_page"
        sourceComponent: BatteriesPage {
            objectName: "batteriesPage"
            onClosed: {
                root.subPage = "";
                root.forceActiveFocus();
            }
        }
    }

    Loader {
        anchors.fill: parent
        active: root.subPage === "backups_page"
        sourceComponent: BackupsPage {
            objectName: "backupsPage"
            onClosed: {
                root.subPage = "";
                root.forceActiveFocus();
            }
        }
    }

    Keypad {
        id: keypad
        objectName: "keypad"
    }

    TextKeyboard {
        id: textKeyboard
        objectName: "settingsKeyboard"
    }

    ConfirmDialog {
        id: confirm
        objectName: "confirmDialog"
        onConfirmed: key => key === "update" ? panel.installUpdate() : panel.settings.runAction(key)
    }
}
