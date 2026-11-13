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
        const errs = panel.settings.save(change);
        errors = Object.assign({}, errors, errs);
    }
    function apply() {
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
            objectName: "settingsFlick"
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: content.implicitHeight + 20
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            ColumnLayout {
                id: content
                width: Math.min(parent.width, 760)
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
                        onEditRequested: (field, value) => keypad.edit(field, value, v => root.setDraft(field.key, v))
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
            Layout.preferredHeight: 72
            spacing: 12

            Text {
                Layout.fillWidth: true
                text: root.testing ? qsTr("Testing connection …")
                    : root.message !== "" ? root.message
                    : root.dirty ? qsTr("Changes to the Homebridge connection are not applied yet.")
                    : qsTr("Display settings are saved immediately.")
                color: root.testing || (root.message === "" && !root.dirty) ? Theme.muted
                     : root.message === "" ? Theme.ink : (root.messageOk ? Theme.ok : Theme.err)
                font.pixelSize: 14
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
            PillButton {
                objectName: "testButton"
                text: qsTr("Test connection")
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

    Keypad {
        id: keypad
        objectName: "keypad"
    }
}
