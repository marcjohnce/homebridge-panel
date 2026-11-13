import QtQuick
import QtQuick.Shapes
import "Geometry.js" as Geo

// Color wheel: angle = hue, distance from the center = saturation
Item {
    id: root

    property real hue: 0
    property real saturation: 0
    property bool lit: false
    signal committed(int hue, int saturation)
    signal interacting(bool active)

    property bool holding: false
    property real localHue: 0
    property real localSat: 0
    readonly property real h: holding ? localHue : hue
    readonly property real s: holding ? localSat : saturation
    readonly property real r: width / 2

    activeFocusOnTab: true
    Accessible.role: Accessible.Slider
    Accessible.name: qsTr("Hue %1 degrees, saturation %2 percent").arg(Math.round(h)).arg(Math.round(s))
    Keys.onRightPressed: setColor((h + 10) % 360, Math.max(s, 60))
    Keys.onLeftPressed: setColor((h + 350) % 360, Math.max(s, 60))

    function setColor(hh, ss) {
        localHue = hh;
        localSat = ss;
        holding = true;
        release.stop();
        commit.restart();
    }

    Timer {
        id: commit
        interval: 300
        onTriggered: {
            root.committed(Math.round(root.localHue), Math.round(root.localSat));
            release.restart();
        }
    }
    Timer {
        id: release
        interval: 1500
        onTriggered: root.holding = false
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: -10
        radius: width / 2
        color: "transparent"
        border.width: 3
        border.color: root.activeFocus ? Theme.gold
                     : (root.lit || root.holding ? Qt.hsla(root.h / 360, Math.max(root.s, 40) / 100, 0.55, 1) : Theme.line)
    }

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: "transparent"
            fillGradient: ConicalGradient {
                centerX: root.r
                centerY: root.r
                angle: 0
                GradientStop { position: 0.0; color: "#FF0000" }
                GradientStop { position: 0.1667; color: "#FFFF00" }
                GradientStop { position: 0.3333; color: "#00FF00" }
                GradientStop { position: 0.5; color: "#00FFFF" }
                GradientStop { position: 0.6667; color: "#0000FF" }
                GradientStop { position: 0.8333; color: "#FF00FF" }
                GradientStop { position: 1.0; color: "#FF0000" }
            }
            PathSvg { path: Geo.circle(root.r, root.r, root.r) }
        }
        ShapePath {
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: root.r
                centerY: root.r
                centerRadius: root.r
                focalX: root.r
                focalY: root.r
                focalRadius: 0
                GradientStop { position: 0.0; color: "#FFFFFFFF" }
                GradientStop { position: 1.0; color: "#00FFFFFF" }
            }
            PathSvg { path: Geo.circle(root.r, root.r, root.r) }
        }
    }

    Rectangle {
        readonly property real a: root.h * Math.PI / 180
        readonly property real size: Math.max(28, Math.round(root.width / 12))
        width: size
        height: size
        radius: size / 2
        x: root.r + Math.cos(a) * root.s / 100 * root.r - size / 2
        y: root.r - Math.sin(a) * root.s / 100 * root.r - size / 2
        color: Qt.hsla(root.h / 360, root.s / 100, 1 - root.s / 200, 1)
        border.color: "white"
        border.width: 3
    }

    MouseArea {
        anchors.fill: parent
        preventStealing: true
        function apply(mx, my) {
            const dx = mx - root.r, dy = root.r - my;
            const hh = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
            const ss = Math.min(1, Math.sqrt(dx * dx + dy * dy) / root.r) * 100;
            root.setColor(hh, ss);
        }
        onPressed: mouse => {
            root.interacting(true);
            apply(mouse.x, mouse.y);
        }
        onPositionChanged: mouse => apply(mouse.x, mouse.y)
        onReleased: root.interacting(false)
        onCanceled: root.interacting(false)
    }
}
