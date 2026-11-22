import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Settings → Weather: the places of the weather view, found by name or given as coordinates.
// The default place is the one shown on the screen saver; the others follow as tabs.
Rectangle {
    id: root
    objectName: "weatherPage"

    signal closed
    property string message
    property var found: []
    property bool searching: false
    readonly property var places: panel.weather.placeList

    color: Theme.page
    focus: true
    Keys.onEscapePressed: root.closed()

    function addPlace() {
        message = "";
        keyboard.edit(qsTr("Place name or coordinates"), "", text => {
            const t = text.trim();
            if (t === "")
                return qsTr("Please enter a name.");
            if (panel.weather.isCoordinates(t))
                return panel.weather.addCoordinates(t);
            root.searching = true;
            root.found = [];
            results.open();
            panel.weather.search(t);
            return "";
        }, { maxLength: 40, hint: qsTr("e.g. Hamburg, or 53.55, 9.99") });
    }
    function rename(p) {
        keyboard.edit(qsTr("Name of the place"), p.name, text => panel.weather.renamePlace(p.id, text));
    }

    Connections {
        target: panel.weather
        function onSearchDone(found, error) {
            root.searching = false;
            root.found = found;
            root.message = error;
        }
    }

    MouseArea {
        anchors.fill: parent
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 28
        anchors.rightMargin: 28
        anchors.topMargin: 18
        spacing: 4

        BackHeader {
            Layout.fillWidth: true
            backText: qsTr("Settings")
            title: qsTr("Weather")
            onBack: root.closed()
        }

        Flickable {
            objectName: "weatherFlick"
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: content.implicitHeight + Theme.s(24)
            boundsBehavior: Flickable.StopAtBounds
            clip: true

            ColumnLayout {
                id: content
                width: Math.min(parent.width, Theme.s(760))
                x: (parent.width - width) / 2
                spacing: Theme.s(10)

                Text {
                    Layout.fillWidth: true
                    Layout.topMargin: Theme.s(10)
                    leftPadding: 4
                    text: qsTr("Each place gets a tab under Weather. The default place opens first and is shown on the screen saver. Weather data comes from Open-Meteo.com over the internet.")
                    color: Theme.muted
                    font.pixelSize: Theme.s(15)
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    visible: root.places.length > 0
                    Layout.fillWidth: true
                    Layout.preferredHeight: list.implicitHeight
                    radius: 14
                    color: Theme.tile

                    Column {
                        id: list
                        width: parent.width
                        Repeater {
                            model: root.places
                            Item {
                                id: row
                                required property var modelData
                                required property int index
                                objectName: "place:" + modelData.name
                                width: list.width
                                height: Theme.s(64)

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    spacing: 4
                                    IconButton {
                                        objectName: "default:" + row.modelData.name
                                        iconName: row.modelData["default"] ? "radioOn" : "radioOff"
                                        label: qsTr("Make %1 the default place").arg(row.modelData.name)
                                        onClicked: panel.weather.setDefault(row.modelData.id)
                                    }
                                    Column {
                                        Layout.fillWidth: true
                                        Text {
                                            width: parent.width
                                            text: row.modelData.name
                                            color: Theme.ink
                                            font.pixelSize: Theme.s(18)
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            width: parent.width
                                            text: row.modelData["default"] ? qsTr("%1 – default place").arg(row.modelData.coords)
                                                                           : row.modelData.coords
                                            color: Theme.muted
                                            font.pixelSize: Theme.s(13)
                                            elide: Text.ElideRight
                                        }
                                    }
                                    IconButton {
                                        iconName: "up"
                                        label: qsTr("Move %1 up").arg(row.modelData.name)
                                        enabled: row.index > 0
                                        onClicked: panel.weather.movePlace(row.modelData.id, -1)
                                    }
                                    IconButton {
                                        iconName: "down"
                                        label: qsTr("Move %1 down").arg(row.modelData.name)
                                        enabled: row.index < root.places.length - 1
                                        onClicked: panel.weather.movePlace(row.modelData.id, 1)
                                    }
                                    IconButton {
                                        objectName: "renamePlace:" + row.modelData.name
                                        iconName: "pencil"
                                        label: qsTr("Rename %1").arg(row.modelData.name)
                                        onClicked: root.rename(row.modelData)
                                    }
                                    IconButton {
                                        objectName: "deletePlace:" + row.modelData.name
                                        iconName: "trash"
                                        label: qsTr("Delete %1").arg(row.modelData.name)
                                        onClicked: confirm.ask({
                                            key: row.modelData.id,
                                            label: qsTr("Delete place"),
                                            button: qsTr("Delete"),
                                            confirm: qsTr("Delete the place “%1”?").arg(row.modelData.name)
                                        })
                                    }
                                }
                                Rectangle {
                                    visible: row.index > 0
                                    anchors.top: parent.top
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.leftMargin: 14
                                    anchors.rightMargin: 14
                                    height: 1
                                    color: Theme.line
                                }
                            }
                        }
                    }
                }

                PillButton {
                    objectName: "addPlace"
                    Layout.topMargin: Theme.s(6)
                    iconName: "plus"
                    text: qsTr("Add place")
                    onClicked: root.addPlace()
                }
                Text {
                    Layout.fillWidth: true
                    visible: root.message !== "" && !results.opened
                    text: root.message
                    color: Theme.err
                    font.pixelSize: Theme.s(14)
                    wrapMode: Text.WordWrap
                }
            }
        }
    }

    // places found for the name typed in
    Popup {
        id: results
        objectName: "placeResults"
        anchors.centerIn: Overlay.overlay
        width: Math.min(Theme.s(560), root.width - 40)
        height: Math.min(implicitHeight, root.height - 40)
        padding: Theme.s(20)
        modal: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        Overlay.modal: Rectangle {
            color: Qt.rgba(0, 0, 0, 0.35)
        }
        background: Rectangle {
            radius: 18
            color: Theme.tile
        }
        contentItem: ColumnLayout {
            spacing: Theme.s(10)
            Text {
                text: root.searching ? qsTr("Searching …") : qsTr("Choose the place")
                color: Theme.ink
                font.pixelSize: Theme.s(19)
                font.weight: Font.Medium
            }
            Spinner {
                visible: root.searching
                Layout.alignment: Qt.AlignHCenter
            }
            Text {
                Layout.fillWidth: true
                visible: !root.searching && root.message !== ""
                text: root.message
                color: Theme.err
                font.pixelSize: Theme.s(15)
                wrapMode: Text.WordWrap
            }
            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                implicitHeight: resultColumn.implicitHeight
                contentHeight: resultColumn.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                clip: true
                Column {
                    id: resultColumn
                    width: parent.width
                    Repeater {
                        model: root.found
                        Rectangle {
                            id: hit
                            required property var modelData
                            required property int index
                            objectName: "result:" + index
                            width: resultColumn.width
                            height: Theme.s(58)
                            radius: 10
                            color: hitMouse.pressed ? Theme.tilePress : "transparent"
                            Column {
                                anchors.verticalCenter: parent.verticalCenter
                                x: 10
                                width: parent.width - 20
                                Text {
                                    width: parent.width
                                    text: hit.modelData.name
                                    color: Theme.ink
                                    font.pixelSize: Theme.s(17)
                                    elide: Text.ElideRight
                                }
                                Text {
                                    width: parent.width
                                    text: hit.modelData.region
                                    color: Theme.muted
                                    font.pixelSize: Theme.s(13)
                                    elide: Text.ElideRight
                                }
                            }
                            MouseArea {
                                id: hitMouse
                                anchors.fill: parent
                                onClicked: {
                                    const err = panel.weather.addPlace(hit.modelData.name, hit.modelData.lat, hit.modelData.lon);
                                    root.message = err;
                                    if (err === "")
                                        results.close();
                                }
                            }
                        }
                    }
                }
            }
            PillButton {
                Layout.alignment: Qt.AlignRight
                text: qsTr("Cancel")
                onClicked: results.close()
            }
        }
    }

    TextKeyboard {
        id: keyboard
        objectName: "weatherKeyboard"
    }

    ConfirmDialog {
        id: confirm
        onConfirmed: key => panel.weather.deletePlace(key)
    }

    EdgeBack {
        onBack: root.closed()
    }
}
