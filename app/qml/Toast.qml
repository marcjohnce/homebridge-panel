import QtQuick

// Short message at the bottom; optionally with an action such as "Undo".
Rectangle {
    id: root

    property bool shown: false
    property string actionText
    property var actionFn: null

    function show(message, action, fn) {
        label.text = message;
        actionText = action || "";
        actionFn = fn || null;
        shown = true;
        hideTimer.interval = actionText !== "" ? 6000 : 4000;
        hideTimer.restart();
    }

    width: Math.min(row.implicitWidth + 40, parent.width * 0.88)
    height: Math.max(label.implicitHeight + 24, actionText !== "" ? Theme.s(52) : 0)
    radius: 12
    color: Theme.ink
    anchors.horizontalCenter: parent.horizontalCenter
    y: shown ? parent.height - height - 24 : parent.height + 20
    visible: y < parent.height
    Accessible.role: Accessible.AlertMessage
    Accessible.name: label.text

    Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

    Rectangle {
        width: 4
        height: parent.height
        radius: 2
        color: Theme.err
        visible: root.actionText === ""
    }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: Theme.s(20)
        Text {
            id: label
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(implicitWidth, root.parent.width * 0.88 - 40 - (action.visible ? action.width + row.spacing : 0))
            wrapMode: Text.WordWrap
            color: Theme.page
            font.pixelSize: Theme.s(16)
        }
        Text {
            id: action
            objectName: "toastAction"
            anchors.verticalCenter: parent.verticalCenter
            visible: root.actionText !== ""
            text: root.actionText
            color: Theme.gold
            font.pixelSize: Theme.s(16)
            font.weight: Font.Medium
            Accessible.role: Accessible.Button
            Accessible.name: text
            MouseArea {
                anchors.fill: parent
                anchors.margins: -12
                onClicked: {
                    const fn = root.actionFn;
                    root.shown = false;
                    if (fn)
                        fn();
                }
            }
        }
    }
    Timer {
        id: hideTimer
        interval: 4000
        onTriggered: root.shown = false
    }
}
