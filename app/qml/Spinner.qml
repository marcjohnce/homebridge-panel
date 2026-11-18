import QtQuick
import QtQuick.Shapes

// Turning arc. RotationAnimator runs on the render thread, so the spinner keeps turning while
// the app is busy building a page or saving (Busy.run).
Item {
    id: root

    property color color: Theme.gold
    property real lineWidth: Math.max(2.5, width / 12)
    property bool running: visible

    implicitWidth: Theme.s(40)
    implicitHeight: implicitWidth
    Accessible.role: Accessible.Animation
    Accessible.name: qsTr("Busy")

    Shape {
        anchors.fill: parent
        ShapePath {
            strokeColor: root.color
            strokeWidth: root.lineWidth
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: root.width / 2
                centerY: root.height / 2
                radiusX: (root.width - root.lineWidth) / 2
                radiusY: (root.height - root.lineWidth) / 2
                startAngle: -90
                sweepAngle: 270
            }
        }
    }

    RotationAnimator on rotation {
        from: 0
        to: 360
        duration: 900
        loops: Animation.Infinite
        running: root.running
    }
}
