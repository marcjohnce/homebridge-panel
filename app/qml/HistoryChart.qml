import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes

// History of a device (Eve history): temperature, humidity, air pressure or the power draw of a
// plug over 24 hours, 7 or 30 days as a line. Touch the chart to read a value.
ColumnLayout {
    id: root

    required property string deviceId
    property int days: 1
    property string kind: "temperature"  // chosen quantity; the first one the device has if it lacks it
    property var result: null            // answer of panel.loadHistory
    readonly property var kinds: result ? result.kinds : []
    readonly property string shown: kinds.indexOf(kind) >= 0 ? kind : kinds.length ? kinds[0] : kind
    readonly property var series: result && result.series[shown] ? result.series[shown] : null
    readonly property var points: series ? series.points : []
    readonly property bool loading: result === null
    // per quantity: unit, decimals, grid step, smallest y range and margin around the values
    readonly property var scale: ({
        temperature: { unit: "°C", decimals: 1, step: 1, span: 2, pad: 0.3 },
        humidity: { unit: "%", decimals: 0, step: 10, span: 20, pad: 1 },
        pressure: { unit: "hPa", decimals: 0, step: 1, span: 6, pad: 0.5 },
        // power from 0 W up to a round value above the highest
        power: { unit: "W", decimals: series && series.max < 10 ? 1 : 0, step: 1, span: 10, pad: 0, zero: true }
    })[shown]
    // a round number at or above v: 1, 2, 2.5 or 5 times a power of ten
    function roundUp(v) {
        const mag = Math.pow(10, Math.floor(Math.log10(Math.max(v, 1e-9))));
        for (const m of [1, 2, 2.5, 5, 10])
            if (m * mag >= v)
                return m * mag;
        return 10 * mag;
    }
    readonly property real lo: !points.length || scale.zero ? 0
        : Math.floor((series.min - scale.pad) / scale.step) * scale.step
    readonly property real hi: !points.length ? 1
        : scale.zero ? roundUp(Math.max(series.max * 1.05, scale.span))
        : Math.max(Math.ceil((series.max + scale.pad) / scale.step) * scale.step, lo + scale.span)
    property int probe: -1               // index of the touched point
    readonly property var probed: probe >= 0 && probe < points.length ? points[probe] : null

    function text(v) {
        return Theme.num(v, scale.decimals) + " " + scale.unit;
    }
    function load() {
        probe = -1;
        result = null;
        panel.loadHistory(deviceId, days);
    }
    function xOf(t) {
        return (t - result.since) / (result.until - result.since) * plot.width;
    }
    function yOf(v) {
        return plot.height - (v - lo) / (hi - lo) * plot.height;
    }
    // labels below the chart: every 6 hours, every day (at noon) or every week (Monday)
    function ticks() {
        if (!result)
            return [];
        const out = [];
        const step = days === 1 ? 6 * 3600000 : days === 7 ? 86400000 : 7 * 86400000;
        const d = new Date(result.since);
        d.setMinutes(0, 0, 0);
        if (days === 1)
            d.setHours(Math.ceil(d.getHours() / 6) * 6);
        else {
            d.setHours(24);
            if (days === 30)        // weeks start on Monday
                d.setDate(d.getDate() + (8 - d.getDay()) % 7);
        }
        // weekdays stand in the middle of their day
        const shift = days === 7 ? 12 * 3600000 : 0;
        if (days === 7)
            d.setDate(d.getDate() - 1);
        for (let t = d.getTime() + shift; t <= result.until; t += step) {
            if (t < result.since)
                continue;
            const at = new Date(t);
            out.push({ t: t, label: days === 1 ? at.toLocaleTimeString(Theme.locale, "HH:mm")
                                   : days === 7 ? at.toLocaleDateString(Theme.locale, "ddd")
                                   : at.toLocaleDateString(Theme.locale, "d MMM") });
        }
        return out;
    }

    spacing: Theme.s(14)
    Component.onCompleted: load()
    onDaysChanged: load()
    onShownChanged: probe = -1

    Connections {
        target: panel
        function onHistoryLoaded(id, days, result) {
            if (id === root.deviceId && days === root.days)
                root.result = result;
        }
    }

    // quantities (only when the device has more than one) and periods side by side; below each
    // other when the names are too long for one line (e.g. "Pression atmosphérique")
    GridLayout {
        id: choices
        readonly property real gap: Theme.s(28)
        readonly property bool oneLine: kindRow.implicitWidth + rangeRow.implicitWidth + 2 * gap + 1 <= root.width
        Layout.fillWidth: true
        columns: oneLine ? 3 : 1
        columnSpacing: gap
        rowSpacing: Theme.s(6)

        Row {
            id: kindRow
            visible: root.kinds.length > 1
            spacing: choices.gap
            Repeater {
                model: root.kinds.length > 1 ? root.kinds : []
                UnderlineButton {
                    required property string modelData
                    objectName: "historyKind:" + modelData
                    text: modelData === "temperature" ? qsTr("Temperature")
                        : modelData === "humidity" ? qsTr("Humidity")
                        : modelData === "power" ? qsTr("Power") : qsTr("Air pressure")
                    selected: root.shown === modelData
                    onClicked: root.kind = modelData
                }
            }
        }
        Rectangle {
            visible: kindRow.visible && choices.oneLine
            Layout.preferredWidth: 1
            Layout.preferredHeight: Theme.s(26)
            color: Theme.line
        }
        Row {
            id: rangeRow
            spacing: choices.gap
            Repeater {
                model: [{ days: 1, label: qsTr("24 hours") }, { days: 7, label: qsTr("7 days") },
                        { days: 30, label: qsTr("30 days") }]
                UnderlineButton {
                    required property var modelData
                    objectName: "historyRange:" + modelData.days
                    text: modelData.label
                    selected: root.days === modelData.days
                    onClicked: root.days = modelData.days
                }
            }
        }
    }

    Text {
        objectName: "historyRange"
        Layout.topMargin: -Theme.s(4)
        visible: root.points.length > 0
        // power: highest draw and the consumption in the period; otherwise lowest and highest
        text: !root.series ? ""
            : root.shown === "power"
              ? qsTr("Highest %1").arg(root.text(root.series.max)) + "    "
                + qsTr("Consumption %1").arg(Theme.num(root.series.energy || 0, (root.series.energy || 0) < 10 ? 2 : 1) + " kWh")
              : qsTr("Lowest %1").arg(root.text(root.series.min)) + "    " + qsTr("Highest %1").arg(root.text(root.series.max))
        color: Theme.muted
        font.pixelSize: Theme.s(16)
    }

    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true

        // y axis: three labels with grid lines
        Repeater {
            model: root.points.length ? 3 : 0
            Item {
                required property int index
                readonly property real value: root.lo + (root.hi - root.lo) * index / 2
                y: plot.y + root.yOf(value)
                width: parent.width
                Rectangle {
                    x: plot.x
                    width: plot.width
                    height: 1
                    color: Theme.line
                }
                Text {
                    anchors.right: parent.left
                    anchors.rightMargin: -plot.x + 10
                    anchors.verticalCenter: parent.top
                    text: Theme.num(parent.value, Number.isInteger(parent.value) ? 0 : 1) + " " + root.scale.unit
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                }
            }
        }

        Item {
            id: plot
            objectName: "historyPlot"
            x: Theme.s(64)
            y: Theme.s(10)
            width: parent.width - x
            height: parent.height - y - Theme.s(34)

            Shape {
                anchors.fill: parent
                visible: root.points.length > 1
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeWidth: 0
                    strokeColor: "transparent"
                    fillColor: Theme.goldSoft
                    PathPolyline {
                        path: root.points.length > 1
                              ? [Qt.point(root.xOf(root.points[0].t), plot.height)]
                                .concat(root.points.map(p => Qt.point(root.xOf(p.t), root.yOf(p.v))))
                                .concat([Qt.point(root.xOf(root.points[root.points.length - 1].t), plot.height)])
                              : []
                    }
                }
                ShapePath {
                    strokeWidth: 2.5
                    strokeColor: Theme.gold
                    fillColor: "transparent"
                    joinStyle: ShapePath.RoundJoin
                    capStyle: ShapePath.RoundCap
                    PathPolyline {
                        path: root.points.map(p => Qt.point(root.xOf(p.t), root.yOf(p.v)))
                    }
                }
            }

            // touched point: vertical line, dot and its time and value
            Rectangle {
                visible: root.probed !== null
                x: root.probed ? root.xOf(root.probed.t) : 0
                width: 1
                height: plot.height
                color: Theme.muted
            }
            Rectangle {
                visible: root.probed !== null
                width: Theme.s(12)
                height: width
                radius: width / 2
                color: Theme.gold
                x: root.probed ? root.xOf(root.probed.t) - width / 2 : 0
                y: root.probed ? root.yOf(root.probed.v) - height / 2 : 0
            }
            Rectangle {
                objectName: "historyProbe"
                visible: root.probed !== null
                readonly property real at: root.probed ? root.xOf(root.probed.t) : 0
                x: Math.max(0, Math.min(plot.width - width, at - width / 2))
                y: -Theme.s(6)
                width: probeText.implicitWidth + Theme.s(20)
                height: probeText.implicitHeight + Theme.s(10)
                radius: height / 2
                color: Theme.tile
                border.color: Theme.line
                Text {
                    id: probeText
                    anchors.centerIn: parent
                    text: !root.probed ? "" : qsTr("%1: %2")
                        .arg(new Date(root.probed.t).toLocaleString(Theme.locale, root.days === 1 ? "HH:mm" : "ddd d MMM, HH:mm"))
                        .arg(root.text(root.probed.v))
                    color: Theme.ink
                    font.pixelSize: Theme.s(15)
                }
            }

            MouseArea {
                anchors.fill: parent
                enabled: root.points.length > 0
                function pick(mx) {
                    let best = 0;
                    for (let i = 1; i < root.points.length; i++)
                        if (Math.abs(root.xOf(root.points[i].t) - mx) < Math.abs(root.xOf(root.points[best].t) - mx))
                            best = i;
                    root.probe = best;
                }
                onPressed: mouse => { hideProbe.stop(); pick(mouse.x); }
                onPositionChanged: mouse => pick(mouse.x)
                onReleased: hideProbe.restart()
            }
            Timer {
                id: hideProbe
                interval: 4000
                onTriggered: root.probe = -1
            }

            // x axis labels
            Repeater {
                model: root.ticks()
                Text {
                    required property var modelData
                    readonly property real at: root.xOf(modelData.t)
                    x: Math.max(0, Math.min(plot.width - width, at - width / 2))
                    y: plot.height + Theme.s(8)
                    text: modelData.label
                    color: Theme.muted
                    font.pixelSize: Theme.s(14)
                }
            }
        }

        Text {
            objectName: "historyMessage"
            anchors.centerIn: parent
            width: parent.width * 0.8
            visible: root.loading || root.points.length === 0
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: root.loading ? qsTr("Reading the history …")
                : root.result.error !== "" ? root.result.error
                : qsTr("No values for this period yet.")
            color: root.result && root.result.error !== "" ? Theme.err : Theme.muted
            font.pixelSize: Theme.s(17)
        }
    }
}
