import QtQuick
import QtQuick.Shapes
import "Geometry.js" as Geo

// 270° arc with a cold → warm gradient, optional drag knob, scale and labels.
Item {
    id: root

    property real from: 10
    property real to: 30
    property real value: 20
    property bool active: true
    property real lineWidth: 6
    property bool knob: false
    property int ticks: 0
    property bool labels: false
    property real knobSize: 28

    readonly property real frac: Math.max(0, Math.min(1, (value - from) / (to - from)))
    readonly property real margin: (knob ? knobSize / 2 + 2 : lineWidth / 2) + (labels ? 30 : 0) + 1
    readonly property real radius: Math.min(width, height) / 2 - margin
    readonly property real cx: width / 2
    readonly property real cy: height / 2
    readonly property real endAngle: Geo.ARC_START + Geo.ARC_SWEEP * frac

    Accessible.ignored: true

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: "transparent"
            fillColor: Theme.line
            PathSvg { path: Geo.band(root.cx, root.cy, root.radius, root.lineWidth, Geo.ARC_START, Geo.ARC_START + Geo.ARC_SWEEP) }
        }
        ShapePath {
            strokeColor: "transparent"
            fillColor: Qt.rgba(Theme.muted.r, Theme.muted.g, Theme.muted.b, 0.55)
            fillGradient: root.active ? heat : null
            PathSvg { path: Geo.band(root.cx, root.cy, root.radius, root.lineWidth, Geo.ARC_START, root.endAngle) }
        }
    }

    // Conical gradient: pale at the start (bottom left), red at the end (bottom right)
    ConicalGradient {
        id: heat
        centerX: root.cx
        centerY: root.cy
        angle: 315
        GradientStop { position: 0.0; color: Theme.heat3 }
        GradientStop { position: 0.375; color: Theme.heat2 }
        GradientStop { position: 0.75; color: Theme.heat1 }
        GradientStop { position: 1.0; color: Theme.heat3 }
    }

    Repeater {
        model: root.ticks > 0 ? root.ticks + 1 : 0
        Rectangle {
            required property int index
            readonly property bool major: index % 5 === 0
            readonly property var p: Geo.polar(root.cx, root.cy, root.radius + (root.knob ? root.knobSize / 2 + 4 : 8),
                                              Geo.ARC_START + Geo.ARC_SWEEP * index / root.ticks)
            width: major ? 3.2 : 1.8
            height: width
            radius: width / 2
            x: p.x - width / 2
            y: p.y - height / 2
            color: Theme.muted
            opacity: 0.6
        }
    }

    Repeater {
        model: root.labels ? [0, 0.5, 1] : []
        Text {
            required property real modelData
            readonly property var p: Geo.polar(root.cx, root.cy, root.radius + (root.knob ? root.knobSize / 2 + 20 : 34), Geo.ARC_START + Geo.ARC_SWEEP * modelData)
            x: p.x - width / 2
            y: p.y - height / 2
            text: Math.round(root.from + (root.to - root.from) * modelData)
            color: Theme.muted
            font.pixelSize: Theme.s(13)
            font.weight: Font.Light
        }
    }

    Rectangle {
        readonly property var p: Geo.polar(root.cx, root.cy, root.radius, root.endAngle)
        visible: root.knob
        width: root.knobSize
        height: root.knobSize
        radius: root.knobSize / 2
        x: p.x - root.knobSize / 2
        y: p.y - root.knobSize / 2
        color: Theme.knob
        border.color: Theme.line
        border.width: 1
    }
}
