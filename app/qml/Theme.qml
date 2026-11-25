pragma Singleton
import QtQuick

QtObject {
    // "light", "dark", "blue" (dark blue with a light blue accent) or "purple" (dark violet with a
    // purple accent); set from the controller in Main.qml
    property string name: "light"
    readonly property bool dark: name !== "light"
    readonly property bool blue: name === "blue"

    function pick(light, dark, blue, purple) {
        return name === "purple" ? purple : name === "blue" ? blue : name === "dark" ? dark : light;
    }

    // UI scale for fonts, spacing and touch targets; set from the window size in Main.qml
    property real scale: 1.0

    function s(v) {
        return Math.round(v * scale);
    }

    readonly property color page: pick("#E6E7EA", "#1C1D1F", "#111B2C", "#1A1625")
    readonly property color tile: pick("#F6F6F7", "#26272A", "#1A273B", "#2A1F3D")
    readonly property color tilePress: pick("#EBECEE", "#303135", "#22334C", "#35284C")
    readonly property color ink: pick("#3A3B3E", "#E8E4DC", "#E4EBF5", "#F1ECF7")
    readonly property color muted: pick("#85878C", "#8A8C91", "#8796AE", "#9A8DB3")
    readonly property color line: pick("#D3D5D9", "#36373B", "#2A3A53", "#3D2F55")
    readonly property color gold: pick("#B4945F", "#C9A86E", "#7DB7F2", "#A866C2")
    readonly property color goldInk: pick("#2A251D", "#1F1B15", "#0D1828", "#1A1027")
    readonly property color goldSoft: pick(Qt.rgba(0.71, 0.58, 0.37, 0.16), Qt.rgba(0.79, 0.66, 0.43, 0.16), Qt.rgba(0.49, 0.72, 0.95, 0.16), Qt.rgba(0.66, 0.40, 0.76, 0.18))
    readonly property color heat1: pick("#F7CDB4", "#E9B79B", "#E9B79B", "#E9B79B")
    readonly property color heat2: pick("#EE8250", "#E7774A", "#E7774A", "#E7774A")
    readonly property color heat3: pick("#D8392B", "#D2402F", "#D2402F", "#D2402F")
    readonly property color knob: pick("#FFFFFF", "#F2EFE9", "#F0F5FB", "#F4EFFA")
    readonly property color ok: pick("#5E9C7B", "#6FB08C", "#6FB08C", "#26C6DA")
    readonly property color err: pick("#C4584B", "#D86A5C", "#D86A5C", "#F35C8C")
    // security alarm tile (leak, glass break, smoke, CO) with white text
    readonly property color alarm: pick("#B4473B", "#A9443A", "#A9443A", "#C2185B")
    // big clock and texts of the screen saver
    readonly property color idleInk: pick(ink, "#BEB9B0", "#B3C0D3", "#C4B8D6")
    readonly property color alarmInk: "#FFFFFF"

    readonly property string fontFamily: "Jost"

    // number and date formats of the panel language; set from the controller in Main.qml
    property string localeName: "en_GB"
    property string dateFormat: "dddd, d MMMM"
    readonly property var locale: Qt.locale(localeName)

    function num(v, decimals) {
        return Number(v).toLocaleString(locale, "f", decimals);
    }
    function fmt(v) {
        return (v === undefined || v === null) ? "–" : num(v, 1);
    }
    function date(d) {
        return d.toLocaleDateString(locale, dateFormat);
    }
}
