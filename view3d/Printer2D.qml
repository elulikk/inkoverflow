// Vista 2D: the printer drawn flat and front on, as 2D sprites (one item per part: body,
// scanner, tanks or cartridges, pads, panel, tray, the inside). Printer3D.qml shows it in
// place of the 3D scene when bridge.mode2d is on and keeps its HUD, callouts and cards: this
// file answers the same questions as a 3D style file (presets, callouts, cartridges...) in
// 2D terms. Far lighter than the 3D scene, for computers where that one runs slowly.
// Sprite units: each printer is drawn on a sheet of SW x SH; a preset is [zoom, x, y], the
// sprite point put in the middle of the view; a callout spot is {x, y, dx, dy}.
import QtQuick

Item {
    id: stage
    required property Item app
    anchors.fill: parent

    readonly property real sw: 680
    readonly property real sh: 400
    // pixels per sprite unit: to fit at zoom 1, and now
    readonly property real fit: Math.min(width / 860, height / 560)
    readonly property real k: fit * app.zoom

    // the same names a 3D style file has
    readonly property var art: artLoader.item
    readonly property string defaultTitle: art ? art.defaultTitle : ""
    readonly property bool cartridges: !!(art && art.cartridges)
    readonly property string inkPart: cartridges ? "Cartuchos" : "Tanques"
    readonly property string cartridgeCode: art && art.cartridgeCode ? art.cartridgeCode : ""
    readonly property var presets: art ? art.presets : ({})
    readonly property var callouts: art ? art.callouts : ({})

    // sprite point -> view pixels
    function toScreen(x, y) { return Qt.point(sheet.x + x * k, sheet.y + y * k) }
    // the part under view pixel (px, py): "tanks", "pads", "panel", "front" or ""
    function partAt(px, py) {
        if (!art) return ""
        var x = (px - sheet.x) / k, y = (py - sheet.y) / k
        var order = ["tanks", "pads", "panel", "front"]
        for (var i = 0; i < order.length; i++) {
            var r = art.hits[order[i]]
            if (r && x >= r[0] && x <= r[0] + r[2] && y >= r[1] && y <= r[1] + r[3]) return order[i]
        }
        return ""
    }

    Item {
        id: sheet
        width: stage.sw
        height: stage.sh
        transformOrigin: Item.TopLeft
        scale: stage.k
        x: stage.width / 2 - app.center.x * stage.k
        y: stage.height * 0.5 - app.center.y * stage.k
        Loader {
            id: artLoader
            anchors.fill: parent
            sourceComponent: (app.style === "hp_smart_tank_580" || app.style === "hp_smart_tank_210") ? hpArt
                             : app.style === "epson_xp2100" ? xpArt : l3150Art
            // the root puts the camera on the new printer once it is drawn
            onLoaded: Qt.callLater(app.styleReady)
        }
    }

    Component { id: l3150Art; L3150Art {} }
    Component { id: hpArt; HpArt {} }
    Component { id: xpArt; XpArt {} }

    // ---- sprites shared by every printer ------------------------------------------------
    // a piece of the shell: see-through while the printer works (app.xray)
    component Shell: Rectangle {
        property color tone: "#1a1c20"
        readonly property bool light: tone.hslLightness > 0.5
        radius: 8
        opacity: 1 - 0.72 * app.xray
        border.color: light ? Qt.rgba(0, 0, 0, 0.13) : Qt.rgba(1, 1, 1, 0.07)
        border.width: 1
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.lighter(tone, light ? 1.04 : 1.5) }
            GradientStop { position: 1.0; color: light ? Qt.darker(tone, 1.06) : tone }
        }
    }

    // a tank window (or a cartridge): the ink inside at its level, its surface rippling
    component InkWindow: Rectangle {
        id: iw
        property int ink: 0
        readonly property var info: app.inks[ink]
        readonly property bool known: !!info && info.level >= 0
        readonly property bool lit: app.hover === "tanks"
        color: "#3a4048"        // light enough for the black ink to show against it
        radius: 3
        clip: true
        border.color: lit ? app.colors.accent : Qt.rgba(1, 1, 1, 0.14)
        border.width: lit ? 1.4 : 0.8
        Rectangle {
            x: 2
            width: parent.width - 4
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 2
            height: (parent.height - 4) * app.inkLevel(iw.ink)
            radius: 2
            color: app.inkColor(iw.ink)
            opacity: iw.known ? 0.95 : 0.45
            Behavior on height { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } }
            Rectangle {   // the surface
                width: parent.width
                height: 1.6
                y: 0.7 * Math.sin(app.time * 2.2 + iw.ink * 1.7)
                color: Qt.lighter(app.inkColor(iw.ink), 1.7)
                opacity: 0.8
            }
        }
        Rectangle { x: 2.5; y: 2; width: 2.2; height: parent.height - 4; radius: 1
                    color: "white"; opacity: 0.13 }   // glass shine
    }

    // the waste-ink pads behind their see-through door: the felt, stained as far as it is full
    component PadWindow: Rectangle {
        readonly property real glow: app.hover === "pads" ? 1
                                     : app.activity === "cleaning" ? 0.45 + 0.4 * Math.sin(app.time * 4) : 0
        radius: 4
        color: "#3b4148"
        clip: true
        border.color: glow > 0 ? Qt.rgba(app.colors.accent.r, app.colors.accent.g, app.colors.accent.b,
                                         0.35 + 0.65 * glow)
                               : Qt.rgba(1, 1, 1, 0.16)
        border.width: glow > 0 ? 1.4 : 1
        Rectangle {
            anchors.fill: parent
            anchors.margins: 3
            radius: 2
            color: "#e6e0d2"
            Rectangle {   // the stain
                anchors.bottom: parent.bottom
                width: parent.width
                height: parent.height * Math.min(1, app.padFill)
                color: app.padFill >= 0.9 ? "#3a1f2e" : "#2d2a3a"
                opacity: 0.85
                Behavior on height { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } }
            }
            Repeater {    // felt layers
                model: 3
                Rectangle { x: (index + 1) * parent.width / 4; width: 0.8; height: parent.height
                            color: "black"; opacity: 0.14 }
            }
        }
        Rectangle { anchors.fill: parent; radius: 4; color: "#7d8fa0"; opacity: 0.2 }   // the door
    }

    // power ring or status led: green connected, amber pulsing while busy, dark when off
    component Light: Rectangle {
        property bool ring: false
        readonly property color lit: app.connected ? (app.d.busy ? app.colors.warn : app.colors.ok)
                                                   : "#2a2d31"
        width: 8
        height: width
        radius: width / 2
        color: ring ? "transparent" : lit
        border.color: lit
        border.width: ring ? 1.8 : 0
        opacity: app.connected && app.d.busy ? 0.55 + 0.45 * Math.sin(app.time * 5) : 1
    }

    // the sheet coming out of the slot while printing (the item's top is the slot)
    component Sheet: Item {
        id: sh
        property real maxLen: 44
        readonly property bool feeding: app.activity === "feeding"
        readonly property real out: app.activity !== "printing" && !feeding ? 0
                                    : feeding ? (app.time * 0.25) % 1
                                    : app.progress >= 0 ? app.progress : (app.time * 0.08) % 1
        height: maxLen
        clip: true
        visible: out > 0
        Rectangle {
            width: parent.width
            height: sh.maxLen * Math.max(0.06, sh.out)
            color: "#f6f6f2"
            radius: 1
            Repeater {   // what is printed on it so far
                model: 6
                Rectangle {
                    x: 14 + (index % 2) * 30
                    y: parent.height - 8 - index * 7
                    width: parent.width - 40 - (index % 3) * 40
                    height: 3
                    visible: y > 2 && !sh.feeding
                    color: app.inkColor(index % 4)
                    opacity: 0.75
                }
            }
        }
    }

    // the floor the printer stands on, with its shadow
    component Platform: Item {
        property real shadowX: 60
        property real shadowW: 560
        anchors.fill: parent
        Rectangle {
            x: 14; y: 316; width: 652; height: 46; radius: 23
            color: app.colors.floor
            border.color: Qt.rgba(app.colors.accent.r, app.colors.accent.g, app.colors.accent.b, 0.75)
            border.width: 1.5
        }
        Rectangle { x: parent.shadowX; y: 322; width: parent.shadowW; height: 18; radius: 9
                    color: "black"; opacity: 0.35 }
    }

    // a rubber foot
    component Foot: Rectangle { y: 328; width: 34; height: 6; radius: 2; color: "#0a0a0a" }

    // the inside, shown while the shell is see-through: the carriage on its rail, the heads
    // working while printing, and the ink a cleaning flushes down the tube into the pads
    component Interior: Item {
        id: inn
        property real railY: 200
        property real xMin: 120
        property real xMax: 400
        property real parkX: 450
        property real restX: parkX          // where it waits when not printing
        property point padAt: Qt.point(470, 310)
        property bool cartridges: false     // it carries the four cartridges
        property real shown: app.xray
        property real cw: 58
        property real ch: 34
        anchors.fill: parent
        visible: shown > 0.02
        opacity: Math.min(1, shown * 1.4)

        readonly property string mode: app.activity
        readonly property real goalX: mode === "printing"
                                      ? xMin + (xMax - xMin) * (0.5 + 0.5 * Math.sin(app.time * 2.4))
                                      : mode === "cleaning" ? parkX : restX
        property real cx: parkX
        readonly property real cy: railY + (mode === "cleaning" ? Math.sin(app.time * 9) * 1.2 : 0)
        Connections {
            target: app
            function onTickChanged() { inn.cx += (inn.goalX - inn.cx) * (inn.mode === "printing" ? 0.45 : 0.08) }
        }
        function frac(v) { return v - Math.floor(v) }

        // the tube from the service station (under the parked heads) to the pads
        Rectangle { x: inn.parkX - 2; y: inn.railY + inn.ch / 2; width: 4
                    height: inn.padAt.y - y; color: "#59616a"; opacity: 0.6 }
        Rectangle { x: Math.min(inn.parkX, inn.padAt.x) - 2; y: inn.padAt.y - 2
                    width: Math.abs(inn.padAt.x - inn.parkX) + 4; height: 4; color: "#59616a"; opacity: 0.6 }
        Repeater {    // drops on their way to the pads
            model: 8
            Rectangle {
                readonly property real f: inn.frac(app.time * 0.6 + index / 8)
                readonly property real l1: inn.padAt.y - (inn.railY + inn.ch / 2)
                readonly property real l2: Math.abs(inn.padAt.x - inn.parkX)
                readonly property real s: f * (l1 + l2)
                visible: inn.mode === "cleaning"
                width: 5; height: 5; radius: 2.5
                color: app.inkColor(index % 4)
                x: (s < l1 ? inn.parkX : inn.parkX + Math.sign(inn.padAt.x - inn.parkX) * (s - l1)) - 2.5
                y: (s < l1 ? inn.railY + inn.ch / 2 + s : inn.padAt.y) - 2.5
            }
        }
        // the rail
        Rectangle { x: inn.xMin - inn.cw / 2 - 12; y: inn.railY - 2
                    width: inn.parkX - inn.xMin + inn.cw + 24; height: 4; radius: 2; color: "#6b737c" }
        // the carriage
        Rectangle {
            x: inn.cx - inn.cw / 2
            y: inn.cy - inn.ch / 2
            width: inn.cw
            height: inn.ch
            radius: 4
            color: "#2c3036"
            border.color: "#56606a"
            Row {    // the four ink feeds, or the four cartridges
                anchors.horizontalCenter: parent.horizontalCenter
                y: inn.cartridges ? 4 : -5
                spacing: inn.cartridges ? 3 : 6
                Repeater {
                    model: 4
                    Rectangle {
                        width: inn.cartridges ? (inn.cw - 17) / 4 : 6
                        height: inn.cartridges ? inn.ch - 12 : 8
                        radius: 2
                        color: inn.cartridges ? "#3a4048" : app.inkColor(index)
                        border.color: inn.cartridges ? Qt.rgba(1, 1, 1, 0.15) : "transparent"
                        clip: true
                        Rectangle {
                            visible: inn.cartridges
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 1.5
                            x: 1.5
                            width: parent.width - 3
                            height: (parent.height - 3) * app.inkLevel(index)
                            color: app.inkColor(index)
                            radius: 1
                        }
                    }
                }
            }
            Rectangle {   // the heads; they flash while printing
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                width: parent.width - 10
                height: 4
                color: inn.mode === "printing" && Math.sin(app.time * 30) > 0 ? app.colors.accent : "#111316"
            }
        }
    }

    // ---- Epson L3150 / L3250: black, tank unit on the right ---------------------------------
    component L3150Art: Item {
        readonly property string defaultTitle: "Impresora Epson"
        readonly property var presets: ({
            "front": [1, 330, 210], "tanks": [1.8, 552, 245],
            "pads": [2.0, 470, 300], "panel": [2.0, 130, 172] })
        readonly property var callouts: ({
            "pads":  { x: 470, y: 313, dx: 110, dy: 60 },
            "tanks": { x: 552, y: 270, dx: 90, dy: -95 },
            "panel": { x: 80, y: 167, dx: -80, dy: -70 } })
        readonly property var hits: ({
            "front": [56, 94, 448, 240], "panel": [62, 152, 142, 30],
            "tanks": [500, 150, 104, 180], "pads": [442, 296, 56, 34] })
        readonly property bool panelLit: app.group(app.hover) === "panel"

        Platform { shadowX: 56; shadowW: 560 }
        Rectangle { x: 210; y: 94; width: 220; height: 22; radius: 4; color: "#24272c"
                    opacity: 1 - 0.72 * app.xray }                  // paper support
        Shell { x: 56; y: 112; width: 448; height: 42; radius: 9; tone: "#16181b" }   // scanner
        Rectangle { x: 66; y: 124; width: 428; height: 1.5; color: "#2b2e34"; opacity: 1 - 0.72 * app.xray }
        Shell { x: 60; y: 150; width: 440; height: 180; radius: 10; tone: "#1a1c20" }  // body
        Rectangle { x: 140; y: 176; width: 300; height: 104; radius: 6; color: "#121418"
                    border.color: Qt.rgba(1, 1, 1, 0.05); opacity: 1 - 0.72 * app.xray }
        Text { x: 290 - width / 2; y: 194; text: "EPSON"; color: "#9fa5ad"; opacity: 1 - 0.72 * app.xray
               font.family: "Arial"; font.pixelSize: 22; font.weight: Font.Bold; font.letterSpacing: 4 }
        // control panel
        Rectangle {
            x: 66; y: 156; width: 134; height: 22; radius: 5; color: "#0d0e10"
            border.color: parent.panelLit ? app.colors.accent : Qt.rgba(1, 1, 1, 0.06)
            border.width: parent.panelLit ? 1.4 : 1
            Light { ring: true; x: 8; y: 5; width: 12 }
            Repeater { model: 3; Rectangle { x: 30 + index * 18; y: 7; width: 12; height: 8; radius: 2; color: "#2c2f35" } }
            Light { x: 90; y: 8; width: 5 }
            Light { x: 102; y: 8; width: 5 }
        }
        Rectangle { x: 150; y: 280; width: 280; height: 14; radius: 3; color: "#040405" }   // slot
        Rectangle { x: 140; y: 294; width: 300; height: 16; radius: 4; color: "#24272c" }   // tray
        Rectangle { x: 150; y: 306; width: 280; height: 5; radius: 2; color: "#2c3036" }
        Sheet { x: 165; y: 288; width: 250; maxLen: 40 }
        // tank unit
        Shell { x: 500; y: 150; width: 104; height: 180; radius: 10; tone: "#1a1c20" }
        Rectangle { x: 504; y: 154; width: 96; height: 22; radius: 6; color: "#0f1012"; opacity: 1 - 0.72 * app.xray }
        Text { x: 552 - width / 2; y: 192; text: app.d.model || "L3150"; color: "#8f969e"
               font.family: app.colors.family; font.pixelSize: 13; font.weight: Font.DemiBold }
        Repeater {    // seen from the front, left to right: K Y M C, as in EpsonL3150.qml
            model: ["K", "Y", "M", "C"]
            InkWindow { x: 512 + index * 21; y: 232; width: 15; height: 76; ink: app.inkAt(modelData) }
        }
        Repeater {
            model: ["K", "Y", "M", "C"]
            Text { x: 519.5 + index * 21 - width / 2; y: 311; text: modelData; color: "#7d858e"
                   font.family: app.colors.family; font.pixelSize: 9; font.weight: Font.Bold }
        }
        Foot { x: 80 }
        Foot { x: 440 }
        Foot { x: 560 }
        Interior { railY: 214; xMin: 130; xMax: 390; parkX: 440; padAt: Qt.point(470, 313) }
        PadWindow { x: 446; y: 300; width: 48; height: 26 }
    }

    // ---- HP Smart Tank 580: white, tanks behind windows at the front left -----------------
    component HpArt: Item {
        // the 210 is the 580 without the scanner and without the screen
        readonly property bool noScanner: app.style === "hp_smart_tank_210"
        readonly property string defaultTitle: noScanner ? "HP Smart Tank 210" : "HP Smart Tank 580"
        readonly property var presets: ({
            "front": [1, 320, 215], "tanks": [1.9, 141, 262],
            "pads": [2.0, 540, 300], "panel": [2.0, 110, 145] })
        readonly property var callouts: ({
            "pads":  { x: 563, y: 312, dx: 90, dy: -80 },
            "tanks": { x: 141, y: 275, dx: -90, dy: -110 },
            "panel": { x: 88, y: 133, dx: -80, dy: -70 } })
        readonly property var hits: ({
            "front": [46, 110, 548, 222], "panel": [52, 114, 98, 48],
            "tanks": [76, 232, 130, 78], "pads": [540, 294, 46, 36] })
        readonly property bool panelLit: app.group(app.hover) === "panel"

        Platform { shadowX: 44; shadowW: 560 }
        Shell { x: 46; y: 120; width: 548; height: 44; radius: 9; tone: "#33373c" }    // top
        Rectangle { x: 152; y: 112; width: 438; height: 36; radius: 7; color: "#4f545a"
                    visible: !noScanner; opacity: 1 - 0.72 * app.xray }               // scanner lid
        Rectangle { x: 152; y: 144; width: 438; height: 3; color: "#5c6268"
                    visible: !noScanner; opacity: 1 - 0.72 * app.xray }
        Shell { x: 50; y: 158; width: 540; height: 172; radius: 10; tone: "#e9ecef" }  // body
        // control panel with its small screen
        Rectangle {
            x: 56; y: 118; width: 90; height: 40; radius: 7; color: "#26292d"
            border.color: parent.panelLit ? app.colors.accent : Qt.rgba(1, 1, 1, 0.08)
            border.width: parent.panelLit ? 1.4 : 1
            Rectangle {
                visible: !noScanner
                x: 10; y: 8; width: 44; height: 15; radius: 2
                color: app.connected ? "#7fd3c0" : "#1d2a28"
                Text { anchors.centerIn: parent; visible: app.connected
                       text: app.d.busy ? "..." : "Listo"; color: "#0c2b25"
                       font.family: app.colors.family; font.pixelSize: 7; font.weight: Font.DemiBold }
            }
            Repeater { model: noScanner ? 2 : 3
                       Rectangle { x: 10 + index * 16; y: noScanner ? 17 : 28; width: 11; height: 6; radius: 2; color: "#3a3e44" } }
            Light { ring: true; x: 66; y: 10; width: 12 }
        }
        // logo
        Rectangle {
            x: 310; y: 180; width: 40; height: 40; radius: 20
            color: "transparent"; border.color: "#8a9097"; border.width: 2
            opacity: 1 - 0.72 * app.xray
            Text { anchors.centerIn: parent; text: "hp"; color: "#8a9097"; font.italic: true
                   font.family: "Arial"; font.pixelSize: 20; font.weight: Font.Bold }
        }
        // tanks
        Rectangle { x: 80; y: 236; width: 122; height: 70; radius: 6; color: "#dfe3e7"
                    border.color: "#c7ccd1"; opacity: 1 - 0.6 * app.xray }
        Repeater {
            model: ["K", "C", "M", "Y"]
            Text { x: 101 + index * 27 - width / 2; y: 239; text: modelData; color: "#7d858e"
                   font.family: app.colors.family; font.pixelSize: 8; font.weight: Font.Bold }
        }
        Repeater {
            model: 4
            InkWindow { x: 92 + index * 27; y: 252; width: 18; height: 46; ink: index }
        }
        // output slot and tray
        Rectangle {
            x: 232; y: 236; width: 344; height: 56; radius: 5; color: "#17191c"
            Repeater { model: 9; Rectangle { x: 16 + index * 36; y: 10; width: 14; height: 4; radius: 1; color: "#2b2f34" } }
        }
        Rectangle { x: 240; y: 286; width: 328; height: 10; radius: 3; color: "#c4c9ce" }
        Sheet { x: 260; y: 282; width: 290; maxLen: 44 }
        Rectangle {
            x: 430; y: 304; width: 104; height: 16; radius: 3
            color: "#f7f8f9"; border.color: "#c8cdd2"; opacity: 1 - 0.72 * app.xray
            Text { anchors.centerIn: parent; text: defaultTitle; color: "#4a5056"
                   font.family: app.colors.family; font.pixelSize: 8 }
        }
        Foot { x: 70 }
        Foot { x: 300 }
        Foot { x: 540 }
        Interior { railY: 200; xMin: 250; xMax: 500; parkX: 548; padAt: Qt.point(563, 312); cw: 56; ch: 32 }
        PadWindow { x: 544; y: 298; width: 38; height: 28 }
    }

    // ---- Epson XP-2100: compact black, four cartridges in the carriage under the scanner ------
    component XpArt: Item {
        id: xp
        readonly property string defaultTitle: "Epson XP-2100"
        readonly property bool cartridges: true
        readonly property string cartridgeCode: "206"
        // the scanner unit lifts while the camera looks at the cartridges
        property real lidOpen: app.shot === "tanks" && app.activity === "" ? 1 : 0
        Behavior on lidOpen { NumberAnimation { duration: 1100; easing.type: Easing.InOutCubic } }

        readonly property var presets: ({
            "front": [1, 320, 190], "tanks": [1.35, 320, 160],
            "pads": [2.0, 510, 295], "panel": [1.8, 220, 234] })
        readonly property var callouts: ({
            "pads":  { x: 531, y: 303, dx: 90, dy: -80 },
            "tanks": lidOpen > 0.5 ? { x: 320, y: 180, dx: -110, dy: -90 }
                                   : { x: 300, y: 140, dx: -100, dy: -90 },
            "panel": { x: 116, y: 235, dx: -80, dy: -70 } })
        readonly property var hits: ({
            "front": [76, 36, 488, 294], "panel": [96, 218, 258, 34],
            "tanks": lidOpen > 0.5 ? [270, 168, 100, 50] : [80, 116, 480, 56],
            "pads": [508, 284, 46, 38] })
        readonly property bool panelLit: app.group(app.hover) === "panel"

        Platform { shadowX: 76; shadowW: 488 }
        Rectangle { x: 214; y: 64; width: 212; height: 64; radius: 4; color: "#1e2024"
                    opacity: 1 - 0.72 * app.xray }                                  // paper support
        Rectangle { x: 232; y: 36; width: 176; height: 80; radius: 1; color: "#f2f2ee" }   // the paper in it
        Shell { x: 80; y: 166; width: 480; height: 164; radius: 10; tone: "#1a1c20" }   // body
        Rectangle { x: 96; y: 166; width: 448; height: 46; color: "#060607"
                    opacity: 0.9 * xp.lidOpen }                                       // the open bay
        Rectangle { x: 548; y: 118 - 70 * xp.lidOpen; width: 6; height: 50 + 70 * xp.lidOpen
                    color: "#2a2d31"; visible: xp.lidOpen > 0.02 }                    // hinge arm
        Shell { x: 80; y: 118 - 70 * xp.lidOpen; width: 480; height: 52; radius: 9; tone: "#16181b" }  // scanner
        Rectangle { x: 92; y: 132 - 70 * xp.lidOpen; width: 456; height: 1.5; color: "#2b2e34"
                    opacity: 1 - 0.72 * app.xray }
        // control panel
        Rectangle {
            x: 100; y: 222; width: 250; height: 26; radius: 5; color: "#0d0e10"
            border.color: xp.panelLit ? app.colors.accent : Qt.rgba(1, 1, 1, 0.06)
            border.width: xp.panelLit ? 1.4 : 1
            Light { ring: true; x: 10; y: 7; width: 12 }
            Repeater { model: 3; Light { x: 32 + index * 10; y: 10.5; width: 5 } }
            Repeater { model: 4; Rectangle { x: 75 + index * 22; y: 7; width: 12; height: 12; radius: 6; color: "#2c2f35" } }
        }
        Text { x: 372; y: 224; text: "EPSON"; color: "#9fa5ad"; opacity: 1 - 0.72 * app.xray
               font.family: "Arial"; font.pixelSize: 16; font.weight: Font.Bold; font.letterSpacing: 3 }
        Rectangle { x: 150; y: 264; width: 340; height: 14; radius: 3; color: "#040405" }   // slot
        Rectangle { x: 130; y: 278; width: 380; height: 18; radius: 4; color: "#24272c" }   // tray
        Rectangle { x: 110; y: 292; width: 420; height: 6; radius: 3; color: "#2c3036" }
        Sheet { x: 170; y: 272; width: 300; maxLen: 46 }
        Foot { x: 96 }
        Foot { x: 300 }
        Foot { x: 516 }
        Interior {
            railY: 194; xMin: 150; xMax: 460; parkX: 490
            restX: xp.lidOpen > 0.5 ? 320 : 490   // where the cartridges are changed
            padAt: Qt.point(531, 303)
            cartridges: true; cw: 84; ch: 40
            shown: Math.max(app.xray, xp.lidOpen)
        }
        PadWindow { x: 512; y: 288; width: 38; height: 30 }
    }
}
