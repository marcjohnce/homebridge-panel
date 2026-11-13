import QtQuick
import QtQuick.Layouts

// Readings of a sensor as large cards: temperature, humidity, air pressure, light level
Item {
    id: root

    required property var dev

    readonly property var st: dev.state || ({})
    readonly property var readings: {
        const out = [];
        if (st.current_temp !== undefined && st.current_temp !== null)
            out.push({ key: "temp", icon: "thermostat", label: qsTr("Temperature"), value: Theme.fmt(st.current_temp), unit: "°C" });
        if (st.humidity !== undefined && st.humidity !== null)
            out.push({ key: "humidity", icon: "drop", label: qsTr("Humidity"), value: Math.round(st.humidity), unit: "%" });
        if (st.pressure !== undefined && st.pressure !== null)
            out.push({ key: "pressure", icon: "gauge", label: qsTr("Air pressure"), value: Math.round(st.pressure), unit: "hPa" });
        if (st.lux !== undefined && st.lux !== null)
            out.push({ key: "lux", icon: "sun", label: qsTr("Light level"),
                       value: st.lux < 10 ? Number(st.lux).toFixed(1) : Math.round(st.lux).toLocaleString(Qt.locale("en_GB"), "f", 0),
                       unit: "lx" });
        return out;
    }
    // All cards in one row if they stay at least 180 px wide, otherwise two columns
    readonly property int columns: (width - (readings.length - 1) * gap) / Math.max(1, readings.length) >= Theme.s(180)
                                   ? Math.max(1, readings.length) : 2
    readonly property int rows: Math.ceil(readings.length / Math.max(1, columns))
    readonly property real gap: Theme.s(16)
    readonly property real cardWidth: Math.min(Theme.s(300), (width - (columns - 1) * gap) / Math.max(1, columns))
    readonly property real cardHeight: Math.min(cardWidth * 0.8, (height - Theme.s(24) - (rows - 1) * gap) / Math.max(1, rows))

    Text {
        anchors.centerIn: parent
        visible: root.readings.length === 0
        text: qsTr("This sensor has not reported a reading yet.")
        color: Theme.muted
        font.pixelSize: Theme.s(18)
    }

    GridLayout {
        objectName: "sensorReadings"
        anchors.centerIn: parent
        columns: root.columns
        columnSpacing: root.gap
        rowSpacing: root.gap

        Repeater {
            model: root.readings
            Rectangle {
                id: card
                required property var modelData
                objectName: "reading:" + modelData.key
                Layout.preferredWidth: root.cardWidth
                Layout.preferredHeight: root.cardHeight
                radius: 14
                color: Theme.tile
                Accessible.role: Accessible.StaticText
                Accessible.name: qsTr("%1: %2 %3").arg(modelData.label).arg(modelData.value).arg(modelData.unit)

                LineIcon {
                    x: Theme.s(18)
                    y: Theme.s(18)
                    width: Theme.s(30)
                    height: Theme.s(30)
                    name: card.modelData.icon
                    color: Theme.gold
                }
                Row {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: Theme.s(4)
                    Text {
                        text: card.modelData.value
                        color: Theme.ink
                        font.pixelSize: Math.min(root.cardHeight * 0.36, root.cardWidth * 0.26)
                        font.weight: Font.ExtraLight
                    }
                    Text {
                        y: Math.round(parent.height * 0.12)
                        leftPadding: 4
                        text: card.modelData.unit
                        color: Theme.muted
                        font.pixelSize: Theme.s(18)
                    }
                }
                Text {
                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    anchors.margins: Theme.s(18)
                    text: card.modelData.label
                    color: Theme.muted
                    font.pixelSize: Theme.s(15)
                }
            }
        }
    }
}
