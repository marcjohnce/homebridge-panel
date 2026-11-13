pragma Singleton
import QtQuick

QtObject {
    property bool dark: false

    readonly property color page: dark ? "#1C1D1F" : "#E6E7EA"
    readonly property color tile: dark ? "#26272A" : "#F6F6F7"
    readonly property color tilePress: dark ? "#303135" : "#EBECEE"
    readonly property color ink: dark ? "#E8E4DC" : "#3A3B3E"
    readonly property color muted: dark ? "#8A8C91" : "#85878C"
    readonly property color line: dark ? "#36373B" : "#D3D5D9"
    readonly property color gold: dark ? "#C9A86E" : "#B4945F"
    readonly property color goldInk: dark ? "#1F1B15" : "#2A251D"
    readonly property color goldSoft: dark ? Qt.rgba(0.79, 0.66, 0.43, 0.16) : Qt.rgba(0.71, 0.58, 0.37, 0.16)
    readonly property color heat1: dark ? "#E9B79B" : "#F7CDB4"
    readonly property color heat2: dark ? "#E7774A" : "#EE8250"
    readonly property color heat3: dark ? "#D2402F" : "#D8392B"
    readonly property color knob: dark ? "#F2EFE9" : "#FFFFFF"
    readonly property color ok: dark ? "#6FB08C" : "#5E9C7B"
    readonly property color err: dark ? "#D86A5C" : "#C4584B"

    readonly property string fontFamily: "Jost"

    function fmt(v) {
        return (v === undefined || v === null) ? "–" : Number(v).toFixed(1);
    }
}
