import QtQuick

// Masked PIN entry with digit keys (alarm system, garage door); Enter on a keyboard submits
Column {
    id: root

    property string entry: ""
    property string error: ""
    signal submitted

    function press(k) {
        error = "";
        if (k === "⌫")
            entry = entry.slice(0, -1);
        else if (k !== "" && entry.length < 8)
            entry += k;
    }

    spacing: 14
    focus: true
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Backspace)
            root.press("⌫");
        else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
            root.submitted();
        else if (/^[0-9]$/.test(event.text))
            root.press(event.text);
        else
            return;
        event.accepted = true;
    }

    Rectangle {
        objectName: "pinDisplay"
        width: parent.width
        height: Theme.s(58)
        radius: 10
        color: Theme.page
        border.color: root.error !== "" ? Theme.err : Theme.line
        Text {
            anchors.centerIn: parent
            text: "•".repeat(root.entry.length)
            color: Theme.ink
            font.pixelSize: Theme.s(30)
            font.letterSpacing: 6
        }
    }
    Text {
        width: parent.width
        visible: root.error !== ""
        text: root.error
        color: Theme.err
        font.pixelSize: Theme.s(14)
    }
    Grid {
        columns: 3
        spacing: 8
        Repeater {
            model: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"]
            Rectangle {
                required property string modelData
                width: (root.width - 16) / 3
                height: Theme.s(56)
                radius: 12
                color: keyMouse.pressed ? Theme.tilePress : Theme.page
                // an empty key keeps its place in the grid
                opacity: modelData !== "" ? 1 : 0
                enabled: modelData !== ""
                Accessible.role: Accessible.Button
                Accessible.name: modelData === "⌫" ? qsTr("Delete") : modelData
                Text {
                    anchors.centerIn: parent
                    visible: parent.modelData !== "⌫"
                    text: parent.modelData
                    color: Theme.ink
                    font.pixelSize: Theme.s(24)
                    font.weight: Font.Light
                }
                LineIcon {
                    anchors.centerIn: parent
                    visible: parent.modelData === "⌫"
                    width: 26
                    height: 26
                    name: "backspace"
                    color: Theme.ink
                }
                MouseArea {
                    id: keyMouse
                    anchors.fill: parent
                    onClicked: root.press(parent.modelData)
                }
            }
        }
    }
}
