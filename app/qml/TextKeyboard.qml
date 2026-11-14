import QtQuick
import QtQuick.Controls.Basic

// On-screen keyboard for names (rooms). The letter layout follows the panel language;
// "?123" switches to digits, punctuation and accented letters. A connected keyboard works as well.
Popup {
    id: root

    property string title
    property string hint
    property string error
    property bool shift: false
    property bool symbols: false
    property int maxLength: 24
    property bool autoCapitalize: true   // off for topics, user names and passwords
    property bool secret: false          // passwords: dots instead of the letters
    // called with the text; returns an error message, or "" to close
    property var acceptFn: null

    readonly property var letterRows: {
        switch (panel.language) {
        case "de": return ["qwertzuiopü", "asdfghjklöä", "yxcvbnmß"];
        case "fr": return ["azertyuiop", "qsdfghjklm", "wxcvbné"];
        case "es": return ["qwertyuiop", "asdfghjklñ", "zxcvbnm"];
        default: return ["qwertyuiop", "asdfghjkl", "zxcvbnm"];
        }
    }
    // digits and the characters MQTT topics, host names, user names and passwords need, then accents
    readonly property var symbolRows: ["1234567890", "-/_#+.:@&*", "()',!?$%=~", "éèêàçùòìíóá"]
    readonly property var rows: symbols ? symbolRows : letterRows
    readonly property real unit: (availableWidth - 10 * keySpacing) / 11
    readonly property int keySpacing: 6

    // opts: { hint, maxLength (24), autoCapitalize (true), secret (false) }
    function edit(heading, text, accept, opts) {
        const o = opts || {};
        hint = o.hint || "";
        maxLength = o.maxLength || 24;
        autoCapitalize = o.autoCapitalize !== false;
        secret = !!o.secret;
        title = heading;
        error = "";
        symbols = false;
        acceptFn = accept;
        input.text = text;
        shift = autoCapitalize && text === "";
        open();
        input.forceActiveFocus();
        input.selectAll();
    }
    function type(ch) {
        error = "";
        if (input.selectedText !== "")
            input.remove(input.selectionStart, input.selectionEnd);
        if (input.length >= maxLength)
            return;
        input.insert(input.cursorPosition, shift ? ch.toUpperCase() : ch);
        shift = false;
    }
    function backspace() {
        error = "";
        if (input.selectedText !== "")
            input.remove(input.selectionStart, input.selectionEnd);
        else if (input.cursorPosition > 0)
            input.remove(input.cursorPosition - 1, input.cursorPosition);
        shift = autoCapitalize && input.text === "";
    }
    function done() {
        const err = acceptFn ? acceptFn(input.text) : "";
        if (err !== "")
            error = err;
        else
            close();
    }

    anchors.centerIn: Overlay.overlay
    width: Math.min(parent ? parent.width - 32 : Theme.s(820), Theme.s(820))
    padding: 22
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    Overlay.modal: Rectangle {
        color: Qt.rgba(0, 0, 0, 0.35)
    }

    background: Rectangle {
        radius: 18
        color: Theme.tile
    }

    contentItem: Column {
        spacing: 12

        Text {
            width: parent.width
            text: root.title
            color: Theme.ink
            font.pixelSize: Theme.s(19)
            font.weight: Font.Medium
            elide: Text.ElideRight
        }

        Rectangle {
            width: parent.width
            height: Theme.s(56)
            radius: 10
            color: Theme.page
            border.color: root.error !== "" ? Theme.err : Theme.line

            TextInput {
                id: input
                objectName: "keyboardInput"
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                verticalAlignment: TextInput.AlignVCenter
                maximumLength: root.maxLength
                echoMode: root.secret ? TextInput.PasswordEchoOnEdit : TextInput.Normal
                inputMethodHints: Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase
                color: Theme.ink
                selectionColor: Theme.goldSoft
                selectedTextColor: Theme.ink
                font.pixelSize: Theme.s(24)
                font.weight: Font.Light
                clip: true
                Accessible.role: Accessible.EditableText
                Accessible.name: root.title
                onTextEdited: root.error = ""
                Keys.onReturnPressed: root.done()
                Keys.onEnterPressed: root.done()
            }
        }

        Text {
            objectName: "keyboardHint"
            width: parent.width
            text: root.error !== "" ? root.error : root.hint
            visible: text !== ""
            color: root.error !== "" ? Theme.err : Theme.muted
            font.pixelSize: Theme.s(13)
            wrapMode: Text.WordWrap
        }

        Column {
            objectName: "keyboardKeys"
            width: parent.width
            spacing: root.keySpacing

            Repeater {
                model: root.rows
                Row {
                    id: keyRow
                    required property string modelData
                    required property int index
                    readonly property bool last: index === root.rows.length - 1
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: root.keySpacing

                    KeyCap {
                        visible: keyRow.last
                        widthUnits: 1.5
                        iconName: "shift"
                        label: qsTr("Shift")
                        active: root.shift
                        onPressed: root.shift = !root.shift
                    }
                    Repeater {
                        model: keyRow.modelData.split("")
                        KeyCap {
                            required property string modelData
                            objectName: "key:" + modelData
                            text: root.shift ? modelData.toUpperCase() : modelData
                            onPressed: root.type(modelData)
                        }
                    }
                    KeyCap {
                        visible: keyRow.last
                        widthUnits: 1.5
                        iconName: "backspace"
                        label: qsTr("Delete")
                        holdable: true
                        onPressed: root.backspace()
                        onHeld: {
                            input.text = "";
                            root.shift = root.autoCapitalize;
                        }
                    }
                }
            }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: root.keySpacing
                KeyCap {
                    objectName: "key:symbols"
                    widthUnits: 2
                    text: root.symbols ? qsTr("ABC") : "?123"
                    label: root.symbols ? qsTr("Letters") : qsTr("Digits and symbols")
                    onPressed: root.symbols = !root.symbols
                }
                KeyCap {
                    objectName: "key:space"
                    widthUnits: 7
                    label: qsTr("Space")
                    onPressed: root.type(" ")
                }
            }
        }

        Row {
            anchors.right: parent.right
            spacing: 10
            PillButton {
                text: qsTr("Cancel")
                onClicked: root.close()
            }
            PillButton {
                objectName: "keyboardDone"
                primary: true
                text: qsTr("Done")
                onClicked: root.done()
            }
        }
    }

    component KeyCap: Rectangle {
        id: key
        property string text
        property string iconName
        property string label: text
        property real widthUnits: 1
        property bool active: false
        property bool holdable: false   // long press runs "held" instead of "pressed"
        signal pressed
        signal held

        objectName: "key:" + iconName
        width: root.unit * widthUnits + root.keySpacing * (widthUnits - 1)
        height: Theme.s(52)
        radius: 10
        color: active ? Theme.goldSoft : (keyMouse.pressed ? Theme.tilePress : Theme.page)
        Accessible.role: Accessible.Button
        Accessible.name: label

        Text {
            anchors.centerIn: parent
            visible: key.iconName === ""
            text: key.text
            color: Theme.ink
            font.pixelSize: Theme.s(key.text.length > 1 ? 16 : 22)
            font.weight: Font.Light
        }
        LineIcon {
            anchors.centerIn: parent
            visible: key.iconName !== ""
            width: Theme.s(24)
            height: Theme.s(24)
            name: key.iconName
            color: Theme.ink
        }
        MouseArea {
            id: keyMouse
            anchors.fill: parent
            onClicked: key.pressed()
            onPressAndHold: key.holdable ? key.held() : key.pressed()
        }
    }
}
