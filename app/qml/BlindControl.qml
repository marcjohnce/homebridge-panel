import QtQuick
import QtQuick.Layouts

// Window blind: drag the drawn blind to set the position, Open / Stop / Close, slat angle.
// Position 0 = closed, 100 = fully open.
RowLayout {
    id: root

    required property var dev
    required property Item sheet

    readonly property var st: dev.state || ({})
    readonly property var meta: dev.meta || ({})
    readonly property bool hasTilt: (dev.capabilities || []).indexOf("tilt") >= 0
    readonly property bool moving: st.moving === "opening" || st.moving === "closing"
    // while moving show where the blind is heading, otherwise where it is
    readonly property int serverValue: moving ? (st.target ?? 0) : (st.position ?? 0)
    property bool holding: false
    property int local: 0
    readonly property int shown: holding ? local : serverValue

    readonly property real gap: Math.min(Theme.s(72), Math.round(width * 0.08))
    readonly property real controlsWidth: 3 * Theme.s(64) + 2 * Theme.s(14)
    // as tall as the space allows, but leave room for the controls on the right
    readonly property real visualWidth: Math.max(160, Math.min(Math.round((height - 40) * 0.78), Theme.s(344),
                                                           width - controlsWidth - gap - 16))
    readonly property real visualHeight: Math.round(visualWidth / 0.78)

    spacing: 0

    function setPosition(v) {
        local = Math.round(Math.max(0, Math.min(100, v)));
        holding = true;
        release.stop();
        commit.restart();
    }
    function send(attrs) {
        holding = false;
        commit.stop();
        panel.setAttrs(root.dev.id, attrs);
    }

    Timer {
        id: commit
        interval: 400
        onTriggered: {
            panel.setAttrs(root.dev.id, { position: root.local });
            release.restart();
        }
    }
    Timer {
        id: release
        interval: 2000
        onTriggered: root.holding = false
    }

    Item { Layout.fillWidth: true }

    // The blind: covered part from the top with slats, a rail at its lower edge
    Rectangle {
        id: visual
        objectName: "blindVisual"
        Layout.preferredWidth: root.visualWidth
        Layout.preferredHeight: root.visualHeight
        radius: 14
        color: Theme.tile
        activeFocusOnTab: true
        border.color: activeFocus ? Theme.gold : "transparent"
        border.width: 2
        Accessible.role: Accessible.Slider
        Accessible.name: qsTr("Blind position, %1 percent open").arg(root.shown)
        Keys.onUpPressed: root.setPosition(root.shown + 10)
        Keys.onDownPressed: root.setPosition(root.shown - 10)

        Item {
            id: pane
            anchors.fill: parent
            anchors.margins: Theme.s(12)
            clip: true

            Rectangle {     // window glass
                anchors.fill: parent
                radius: 6
                color: Theme.page
            }
            Rectangle {     // covered part
                id: cover
                width: parent.width
                height: Math.round(parent.height * (100 - root.shown) / 100)
                radius: 6
                color: Theme.line
                Behavior on height {
                    enabled: !root.holding
                    NumberAnimation { duration: 300; easing.type: Easing.OutCubic }
                }

                Repeater {
                    model: Math.floor(cover.height / Theme.s(14))
                    Rectangle {
                        required property int index
                        y: (index + 1) * Theme.s(14) - 1
                        width: cover.width
                        height: 1
                        color: Theme.muted
                        opacity: 0.35
                    }
                }
            }
            Rectangle {     // bottom rail = drag handle
                y: Math.min(pane.height - height, cover.height - height / 2)
                width: parent.width
                height: Theme.s(8)
                radius: height / 2
                color: Theme.gold
            }
        }

        MouseArea {
            anchors.fill: pane
            preventStealing: true
            function apply(my) {
                root.setPosition(100 - my / height * 100);
            }
            onPressed: mouse => {
                root.sheet.interactionStarted();
                apply(mouse.y);
            }
            onPositionChanged: mouse => apply(mouse.y)
            onReleased: root.sheet.interactionEnded()
            onCanceled: root.sheet.interactionEnded()
        }
    }

    Item { Layout.preferredWidth: root.gap }

    ColumnLayout {
        Layout.alignment: Qt.AlignVCenter
        spacing: Theme.s(14)

        Row {
            objectName: "blindPosition"
            Text {
                text: root.shown
                color: Theme.ink
                font.pixelSize: Math.min(Theme.s(84), root.visualHeight * 0.2)
                font.weight: Font.ExtraLight
            }
            Text {
                y: Math.round(parent.height * 0.14)
                leftPadding: 4
                text: "%"
                color: Theme.muted
                font.pixelSize: Theme.s(20)
            }
        }
        Text {
            text: root.st.moving === "opening" ? qsTr("Opening …")
                : root.st.moving === "closing" ? qsTr("Closing …")
                : root.shown >= 100 ? qsTr("Open") : root.shown <= 0 ? qsTr("Closed") : qsTr("open")
            color: root.moving ? Theme.gold : Theme.muted
            font.pixelSize: Theme.s(16)
        }

        Row {
            Layout.topMargin: Theme.s(10)
            spacing: Theme.s(14)
            CircleButton {
                objectName: "openButton"
                iconName: "up"
                label: qsTr("Open")
                onClicked: root.send({ position: 100 })
            }
            CircleButton {
                objectName: "stopButton"
                iconName: "pause"
                label: qsTr("Stop")
                onClicked: root.send({ stop: true })
            }
            CircleButton {
                objectName: "closeButton"
                iconName: "down"
                label: qsTr("Close")
                onClicked: root.send({ position: 0 })
            }
        }

        TiltSlider {
            objectName: "tiltSlider"
            visible: root.hasTilt
            Layout.topMargin: Theme.s(14)
            Layout.preferredWidth: root.controlsWidth
            serverValue: root.st.tilt ?? 0
            minAngle: root.meta.min_tilt ?? -90
            maxAngle: root.meta.max_tilt ?? 90
            onInteracting: active => active ? root.sheet.interactionStarted() : root.sheet.interactionEnded()
            onCommitted: angle => panel.setAttrs(root.dev.id, { tilt: angle })
        }
    }

    Item { Layout.fillWidth: true }
}
