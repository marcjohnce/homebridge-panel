import QtQuick

Rectangle {
    id: root

    property bool shown: false

    function show(message) {
        label.text = message;
        shown = true;
        hideTimer.restart();
    }

    width: Math.min(label.implicitWidth + 40, parent.width * 0.88)
    height: label.implicitHeight + 24
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
    }
    Text {
        id: label
        anchors.centerIn: parent
        width: Math.min(implicitWidth, root.parent.width * 0.88 - 40)
        wrapMode: Text.WordWrap
        color: Theme.page
        font.pixelSize: Theme.s(16)
    }
    Timer {
        id: hideTimer
        interval: 4000
        onTriggered: root.shown = false
    }
}
