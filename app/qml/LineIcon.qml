import QtQuick
import QtQuick.Shapes
import "Icons.js" as Icons

Item {
    id: root

    property string name: "light"
    property color color: Theme.ink
    property real lineWidth: 1.3

    implicitWidth: 24
    implicitHeight: 24
    Accessible.ignored: true

    Shape {
        anchors.centerIn: parent
        width: 24
        height: 24
        scale: Math.min(root.width, root.height) / 24
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: root.color
            strokeWidth: root.lineWidth
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: Icons.path(root.name) }
        }
    }
}
