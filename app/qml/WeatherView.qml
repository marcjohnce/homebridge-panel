import QtQuick
import QtQuick.Layouts

// Menu "Weather": one large tile with the weather now and the next 7 days for the place chosen
// in the tabs (places are set in Settings → Weather). Data: Open-Meteo.
Rectangle {
    id: root
    objectName: "weatherView"

    readonly property var w: panel.weather.current
    readonly property bool ok: w.state === "ok"
    readonly property bool narrow: width < Theme.s(640)

    function iconFor(kind, night) {
        return kind === "clear" ? (night ? "moon" : "sun") : kind === "partly" ? "weather" : kind;
    }

    radius: 14
    color: Theme.tile

    // loading, or no weather yet
    Column {
        anchors.centerIn: parent
        width: parent.width * 0.8
        spacing: 14
        visible: !root.ok
        Spinner {
            anchors.horizontalCenter: parent.horizontalCenter
            visible: root.w.state === "loading"
        }
        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: root.w.state === "loading" ? qsTr("Loading the weather …")
                : qsTr("No weather for %1: %2").arg(root.w.name || "").arg(root.w.error || "")
            color: Theme.muted
            font.pixelSize: Theme.s(18)
        }
    }

    ColumnLayout {
        visible: root.ok
        anchors.fill: parent
        anchors.margins: root.narrow ? Theme.s(20) : Theme.s(28)
        spacing: Theme.s(16)

        // now
        RowLayout {
            objectName: "weatherNow"
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.s(24)

            LineIcon {
                Layout.preferredWidth: root.narrow ? Theme.s(84) : Theme.s(116)
                Layout.preferredHeight: Layout.preferredWidth
                Layout.alignment: Qt.AlignVCenter
                lineWidth: 1.1
                name: root.ok ? root.iconFor(root.w.now.kind, root.w.now.night) : "cloud"
                color: Theme.gold
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                spacing: 2
                Text {
                    objectName: "weatherTemp"
                    text: root.ok ? qsTr("%1 °C").arg(root.w.now.temp) : ""
                    color: Theme.ink
                    font.pixelSize: root.narrow ? Theme.s(64) : Theme.s(84)
                    font.weight: Font.ExtraLight
                }
                Text {
                    Layout.fillWidth: true
                    text: root.ok ? root.w.now.text : ""
                    color: Theme.ink
                    font.pixelSize: Theme.s(22)
                    elide: Text.ElideRight
                }
                Text {
                    Layout.fillWidth: true
                    text: root.ok && root.w.days.length ? qsTr("Today %1° / %2°").arg(root.w.days[0].max).arg(root.w.days[0].min) : ""
                    color: Theme.muted
                    font.pixelSize: Theme.s(17)
                }
            }
            GridLayout {
                Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
                columns: 2
                rowSpacing: Theme.s(10)
                columnSpacing: Theme.s(18)
                Repeater {
                    model: root.ok ? [
                        { label: qsTr("Feels like"), value: qsTr("%1 °C").arg(root.w.now.feels) },
                        { label: qsTr("Humidity"), value: qsTr("%1 %").arg(root.w.now.humidity) },
                        { label: qsTr("Wind"), value: qsTr("%1 km/h").arg(root.w.now.wind) }
                    ] : []
                    delegate: Item {
                        required property var modelData
                        required property int index
                        Layout.columnSpan: 2
                        Layout.fillWidth: true
                        implicitWidth: label.implicitWidth + value.implicitWidth + Theme.s(18)
                        implicitHeight: Math.max(label.implicitHeight, value.implicitHeight)
                        Text {
                            id: label
                            anchors.left: parent.left
                            anchors.baseline: value.baseline
                            text: modelData.label
                            color: Theme.muted
                            font.pixelSize: Theme.s(16)
                        }
                        Text {
                            id: value
                            anchors.right: parent.right
                            text: modelData.value
                            color: Theme.ink
                            font.pixelSize: Theme.s(20)
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.line
        }

        // the next 7 days, in equal columns
        Row {
            id: daysRow
            objectName: "weatherDays"
            Layout.fillWidth: true
            Layout.preferredHeight: childrenRect.height
            Repeater {
                model: root.ok ? root.w.days : []
                delegate: Item {
                    id: day
                    required property var modelData
                    required property int index
                    width: daysRow.width / Math.max(1, root.w.days.length)
                    height: dayColumn.implicitHeight
                    Accessible.role: Accessible.StaticText
                    Accessible.name: qsTr("%1: %2, %3° to %4°").arg(modelData.day).arg(modelData.text).arg(modelData.min).arg(modelData.max)
                    Column {
                        id: dayColumn
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: Theme.s(6)
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: day.modelData.day
                            color: day.index === 0 ? Theme.ink : Theme.muted
                            font.pixelSize: Theme.s(16)
                            font.weight: day.index === 0 ? Font.Medium : Font.Normal
                        }
                        LineIcon {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: Theme.s(40)
                            height: Theme.s(40)
                            name: root.iconFor(day.modelData.kind, false)
                            color: Theme.ink
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: day.modelData.max + "°"
                            color: Theme.ink
                            font.pixelSize: Theme.s(20)
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: day.modelData.min + "°"
                            color: Theme.muted
                            font.pixelSize: Theme.s(17)
                        }
                        Row {
                            anchors.horizontalCenter: parent.horizontalCenter
                            spacing: 3
                            opacity: day.modelData.rain !== "" ? 1 : 0
                            LineIcon {
                                anchors.verticalCenter: parent.verticalCenter
                                width: Theme.s(14)
                                height: width
                                name: "drop"
                                color: Theme.muted
                            }
                            Text {
                                text: day.modelData.rain || "0 %"
                                color: Theme.muted
                                font.pixelSize: Theme.s(13)
                            }
                        }
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignRight
            text: root.ok && root.w.error !== ""
                  ? qsTr("Not updated: %1. Weather data: Open-Meteo.com, from %2").arg(root.w.error).arg(root.w.updated)
                  : qsTr("Weather data: Open-Meteo.com, updated %1").arg(root.ok ? root.w.updated : "")
            color: root.ok && root.w.error !== "" ? Theme.err : Theme.muted
            font.pixelSize: Theme.s(12)
            elide: Text.ElideLeft
        }
    }
}
