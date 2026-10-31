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
    readonly property string inkPart: art && art.laser ? "Tóner" : cartridges ? "Cartuchos" : "Tanques"
    readonly property string cartridgeCode: art && art.cartridgeCode ? art.cartridgeCode : ""
    readonly property string cartridgeSpot: art && art.cartridgeSpot ? art.cartridgeSpot : ""
    readonly property bool laser: !!(art && art.laser)
    readonly property string openText: art && art.openText ? art.openText : ""
    readonly property string closeText: art && art.closeText ? art.closeText : ""
    readonly property var presets: art ? art.presets : ({})
    readonly property var callouts: art ? art.callouts : ({})

    // sprite point -> view pixels
    function toScreen(x, y) { return Qt.point(sheet.x + x * k, sheet.y + y * k) }
    // the part under view pixel (px, py): "tanks", "pads", "panel", "front" or "". A part's
    // hit area is one [x, y, w, h] or a list of them.
    function partAt(px, py) {
        if (!art) return ""
        var x = (px - sheet.x) / k, y = (py - sheet.y) / k
        var order = ["tanks", "pads", "panel", "front"]
        for (var i = 0; i < order.length; i++) {
            var r = art.hits[order[i]]
            var rects = r && Array.isArray(r[0]) ? r : [r]
            for (var j = 0; j < rects.length; j++) {
                var q = rects[j]
                if (q && x >= q[0] && x <= q[0] + q[2] && y >= q[1] && y <= q[1] + q[3]) return order[i]
            }
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
            sourceComponent: ({ "hp_smart_tank_580": hpArt, "hp_smart_tank_210": hpArt,
                                "epson_xp2100": xpArt, "canon_g3110": canonArt,
                                "brother_t420w": brotherArt, "hp_ink_tank_415": inkTankArt,
                                "hp_deskjet_2775": deskJetArt })[app.style]
                             || (app.style in laserStyles ? laserArt : l3150Art)
            // the root puts the camera on the new printer once it is drawn
            onLoaded: Qt.callLater(app.styleReady)
        }
    }

    Component { id: l3150Art; L3150Art {} }
    Component { id: hpArt; HpArt {} }
    Component { id: xpArt; XpArt {} }
    Component { id: canonArt; CanonArt {} }
    Component { id: brotherArt; BrotherArt {} }
    Component { id: inkTankArt; InkTankArt {} }
    Component { id: deskJetArt; DeskJetArt {} }
    Component { id: laserArt; LaserArt {} }
    readonly property var laserStyles: ({ "hp_laserjet_m111": 1, "hp_laserjet_m141": 1,
        "brother_hl1212w": 1, "brother_dcp1612w": 1, "pantum_p2500w": 1, "pantum_m6550nw": 1,
        "samsung_m2020w": 1, "samsung_m2070w": 1 })

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
        property bool cartridges: false     // it carries the cartridges
        property int carts: 4               // how many: four (one per colour) or two
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
                    model: inn.cartridges ? inn.carts : 4
                    Rectangle {
                        width: inn.cartridges ? (inn.cw - 5 - 3 * inn.carts) / inn.carts : 6
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

    // ---- Canon G3110: black, tank pods at both front corners --------------------------------
    component CanonArt: Item {
        readonly property string defaultTitle: "Canon PIXMA G3110"
        readonly property var presets: ({
            "front": [1, 320, 215], "tanks": [1.5, 320, 250],
            "pads": [2.0, 559, 300], "panel": [2.0, 530, 145] })
        readonly property var callouts: ({
            "pads":  { x: 559, y: 311, dx: 90, dy: -80 },
            "tanks": { x: 80, y: 252, dx: -90, dy: -100 },
            "panel": { x: 500, y: 142, dx: 80, dy: -70 } })
        readonly property var hits: ({
            "front": [42, 126, 556, 204], "panel": [470, 130, 120, 24],
            "tanks": [[42, 160, 76, 130], [522, 166, 76, 124]], "pads": [530, 294, 58, 32] })
        readonly property bool panelLit: app.group(app.hover) === "panel"

        Platform { shadowX: 42; shadowW: 556 }
        Rectangle { x: 190; y: 80; width: 260; height: 56; radius: 4; color: "#24272c"
                    opacity: 1 - 0.72 * app.xray }                                  // paper support
        Shell { x: 118; y: 128; width: 480; height: 42; radius: 9; tone: "#1d1f22" }   // scanner
        Rectangle { x: 128; y: 140; width: 340; height: 1.5; color: "#2b2e34"; opacity: 1 - 0.72 * app.xray }
        Shell { x: 42; y: 166; width: 76; height: 164; radius: 9; tone: "#25272b" }   // black tank pod
        Rectangle { x: 48; y: 160; width: 64; height: 10; radius: 4; color: "#2b2e33"; opacity: 1 - 0.72 * app.xray }
        Shell { x: 522; y: 166; width: 76; height: 164; radius: 9; tone: "#25272b" }  // colour tank pod
        Shell { x: 118; y: 170; width: 404; height: 160; radius: 6; tone: "#1f2125" }  // front between them
        Rectangle { x: 128; y: 178; width: 384; height: 56; radius: 4; color: "#16171a"
                    opacity: 1 - 0.72 * app.xray }
        Text { x: 320 - width / 2; y: 190; text: "Canon"; color: "#e8eaed"; opacity: 1 - 0.72 * app.xray
               font.family: "Georgia"; font.pixelSize: 24; font.weight: Font.Bold }
        // control panel on the scanner, over the colour tanks
        Rectangle {
            x: 470; y: 132; width: 120; height: 22; radius: 5; color: "#121315"
            border.color: parent.panelLit ? app.colors.accent : Qt.rgba(1, 1, 1, 0.06)
            border.width: parent.panelLit ? 1.4 : 1
            Rectangle { x: 10; y: 5; width: 34; height: 12; radius: 2
                        color: app.connected ? "#7fd3c0" : "#1d2a28" }
            Repeater { model: 3; Rectangle { x: 52 + index * 14; y: 8; width: 10; height: 6; radius: 2; color: "#2d3036" } }
            Light { ring: true; x: 98; y: 5; width: 12 }
        }
        Rectangle { x: 165; y: 250; width: 310; height: 34; radius: 3; color: "#040405" }   // slot
        Rectangle { x: 180; y: 282; width: 280; height: 12; radius: 3; color: "#2a2d32" }   // tray
        Sheet { x: 190; y: 262; width: 260; maxLen: 40 }
        InkWindow { x: 62; y: 214; width: 36; height: 70; ink: app.inkAt("K") }
        Text { x: 80 - width / 2; y: 200; text: "K"; color: "#8a9198"
               font.family: app.colors.family; font.pixelSize: 9; font.weight: Font.Bold }
        Repeater {
            model: ["C", "M", "Y"]
            InkWindow { x: 530 + index * 21; y: 214; width: 15; height: 70; ink: app.inkAt(modelData) }
        }
        Repeater {
            model: ["C", "M", "Y"]
            Text { x: 537.5 + index * 21 - width / 2; y: 200; text: modelData; color: "#8a9198"
                   font.family: app.colors.family; font.pixelSize: 9; font.weight: Font.Bold }
        }
        Foot { x: 60 }
        Foot { x: 300 }
        Foot { x: 548 }
        Interior { railY: 214; xMin: 180; xMax: 440; parkX: 500; padAt: Qt.point(559, 311) }
        PadWindow { x: 532; y: 298; width: 54; height: 26 }
    }

    // ---- Brother DCP-T420W: flat dark box, tanks at the front right, paper cassette ---------
    component BrotherArt: Item {
        readonly property string defaultTitle: "Brother DCP-T420W"
        readonly property var presets: ({
            "front": [1, 320, 215], "tanks": [1.8, 484, 240],
            "pads": [2.0, 569, 300], "panel": [2.0, 131, 150] })
        readonly property var callouts: ({
            "pads":  { x: 569, y: 310, dx: 90, dy: -80 },
            "tanks": { x: 484, y: 250, dx: 90, dy: -100 },
            "panel": { x: 80, y: 146, dx: -80, dy: -70 } })
        readonly property var hits: ({
            "front": [48, 131, 544, 199], "panel": [56, 134, 150, 24],
            "tanks": [420, 168, 128, 140], "pads": [552, 294, 34, 32] })
        readonly property bool panelLit: app.group(app.hover) === "panel"

        Platform { shadowX: 48; shadowW: 544 }
        Shell { x: 48; y: 131; width: 544; height: 32; radius: 8; tone: "#26282c" }    // scanner
        Rectangle { x: 210; y: 137; width: 372; height: 1.5; color: "#34373c"; opacity: 1 - 0.72 * app.xray }
        Shell { x: 48; y: 160; width: 544; height: 170; radius: 8; tone: "#2b2d31" }   // body
        // control panel, front left of the top
        Rectangle {
            x: 56; y: 136; width: 150; height: 22; radius: 5; color: "#17181b"
            border.color: parent.panelLit ? app.colors.accent : Qt.rgba(1, 1, 1, 0.06)
            border.width: parent.panelLit ? 1.4 : 1
            Light { ring: true; x: 8; y: 5; width: 12 }
            Repeater { model: 4; Rectangle { x: 32 + index * 22; y: 8; width: 13; height: 7; radius: 2; color: "#3a3e44" } }
            Repeater { model: 3; Light { x: 36 + index * 22; y: 2; width: 4 } }
        }
        Text { x: 300 - width / 2; y: 141; text: app.d.model || "DCP-T420W"; color: "#9aa1a8"
               opacity: 1 - 0.72 * app.xray; font.family: app.colors.family; font.pixelSize: 9 }
        Rectangle { x: 100; y: 205; width: 300; height: 44; radius: 4; color: "#040405" }   // output
        Rectangle { x: 115; y: 245; width: 270; height: 8; radius: 3; color: "#34373c" }    // tray
        Sheet { x: 120; y: 222; width: 260; maxLen: 30 }
        Rectangle {                                                                           // cassette
            x: 110; y: 262; width: 280; height: 54; radius: 4; color: "#3a3d42"
            opacity: 1 - 0.72 * app.xray
            Rectangle { x: 110; y: 4; width: 60; height: 8; radius: 3; color: "#26282c" }
        }
        // tank cover with the logo, the windows under it
        Rectangle { x: 420; y: 168; width: 128; height: 58; radius: 6; color: "#1b1d20"
                    opacity: 1 - 0.72 * app.xray }
        Text { x: 484 - width / 2; y: 186; text: "brother"; color: "#f2f4f6"; opacity: 1 - 0.72 * app.xray
               font.family: "Arial"; font.pixelSize: 17; font.weight: Font.Black }
        Repeater {
            model: ["K", "C", "M", "Y"]
            InkWindow { x: 436 + index * 25; y: 236; width: 17; height: 52; ink: app.inkAt(modelData) }
        }
        Repeater {
            model: ["K", "C", "M", "Y"]
            Text { x: 444.5 + index * 25 - width / 2; y: 291; text: modelData; color: "#8a9198"
                   font.family: app.colors.family; font.pixelSize: 9; font.weight: Font.Bold }
        }
        Foot { x: 66 }
        Foot { x: 300 }
        Foot { x: 540 }
        Interior { railY: 200; xMin: 120; xMax: 380; parkX: 540; padAt: Qt.point(569, 310) }
        PadWindow { x: 552; y: 298; width: 34; height: 26 }
    }

    // ---- HP Ink Tank 415: glossy black body, the tank unit on its right ----------------------
    component InkTankArt: Item {
        readonly property string defaultTitle: "HP Ink Tank 415"
        readonly property var presets: ({
            "front": [1, 320, 215], "tanks": [2.0, 570, 262],
            "pads": [2.0, 493, 300], "panel": [2.0, 90, 170] })
        readonly property var callouts: ({
            "pads":  { x: 493, y: 311, dx: -90, dy: -80 },
            "tanks": { x: 570, y: 265, dx: 90, dy: -100 },
            "panel": { x: 50, y: 168, dx: -80, dy: -70 } })
        readonly property var hits: ({
            "front": [25, 148, 497, 182], "panel": [30, 156, 110, 24],
            "tanks": [524, 200, 91, 130], "pads": [470, 294, 46, 32] })
        readonly property bool panelLit: app.group(app.hover) === "panel"

        Platform { shadowX: 25; shadowW: 590 }
        Rectangle { x: 160; y: 100; width: 240; height: 54; radius: 4; color: "#24272c"
                    opacity: 1 - 0.72 * app.xray }                                  // paper support
        Shell { x: 25; y: 146; width: 497; height: 42; radius: 12; tone: "#1d1e21" }   // scanner
        Rectangle { x: 35; y: 152; width: 477; height: 1.5; color: "#33363b"; opacity: 1 - 0.72 * app.xray }
        Shell { x: 25; y: 186; width: 497; height: 144; radius: 12; tone: "#1b1c1f" }  // body
        // buttons on the front of the scanner
        Rectangle {
            x: 30; y: 158; width: 110; height: 24; radius: 5; color: "transparent"
            border.color: parent.panelLit ? app.colors.accent : "transparent"
            border.width: 1.4
            Light { ring: true; x: 8; y: 6; width: 12 }
            Repeater { model: 3; Rectangle { x: 34 + index * 18; y: 8; width: 10; height: 10; radius: 5; color: "#2d3036" } }
            Repeater { model: 3; Light { x: 36.5 + index * 18; y: 1; width: 4 } }
        }
        Text { x: 270 - width / 2; y: 158; text: "hp"; color: "#c8ccd1"; font.italic: true
               opacity: 1 - 0.72 * app.xray; font.family: "Segoe UI"; font.pixelSize: 16; font.weight: Font.Bold }
        Rectangle { x: 140; y: 230; width: 300; height: 44; radius: 4; color: "#040405" }   // slot
        Rectangle { x: 155; y: 270; width: 270; height: 12; radius: 3; color: "#2a2d32" }   // tray
        Sheet { x: 165; y: 246; width: 250; maxLen: 44 }
        // tank unit
        Shell { x: 524; y: 210; width: 91; height: 120; radius: 10; tone: "#1b1c1f" }
        Rectangle { x: 528; y: 203; width: 83; height: 11; radius: 5; color: "#232529"; opacity: 1 - 0.72 * app.xray }
        Text { x: 569.5 - width / 2; y: 222; text: "Ink Tank"; color: "#8f969e"
               font.family: app.colors.family; font.pixelSize: 8 }
        InkWindow { x: 533; y: 240; width: 22; height: 62; ink: app.inkAt("K") }
        Repeater {
            model: ["C", "M", "Y"]
            InkWindow { x: 559 + index * 17; y: 240; width: 13; height: 62; ink: app.inkAt(modelData) }
        }
        Repeater {
            model: ["K", "C", "M", "Y"]
            Text { x: [544, 565.5, 582.5, 599.5][index] - width / 2; y: 306; text: modelData; color: "#8a9198"
                   font.family: app.colors.family; font.pixelSize: 8; font.weight: Font.Bold }
        }
        Foot { x: 46 }
        Foot { x: 440 }
        Foot { x: 560 }
        Interior { railY: 205; xMin: 150; xMax: 420; parkX: 480; padAt: Qt.point(493, 311) }
        PadWindow { x: 470; y: 298; width: 46; height: 26 }
    }

    // ---- HP DeskJet 2775: white, two cartridges behind the front door -----------------------
    component DeskJetArt: Item {
        id: dj
        readonly property string defaultTitle: "HP DeskJet Ink Advantage 2775"
        readonly property bool cartridges: true
        readonly property string cartridgeCode: "667"
        readonly property string cartridgeSpot: "la tapa frontal (cartuchos)"
        readonly property string openText: "Bajar la tapa y ver los cartuchos"
        readonly property string closeText: "Cerrar la tapa"
        // the door folds down while the camera looks at the cartridges
        property real doorOpen: app.shot === "tanks" && app.activity === "" ? 1 : 0
        Behavior on doorOpen { NumberAnimation { duration: 1100; easing.type: Easing.InOutCubic } }

        readonly property var presets: ({
            "front": [1, 320, 215], "tanks": [1.6, 320, 225],
            "pads": [2.0, 560, 300], "panel": [2.0, 122, 140] })
        readonly property var callouts: ({
            "pads":  { x: 560, y: 311, dx: 90, dy: -80 },
            "tanks": { x: 320, y: 215, dx: -110, dy: -90 },
            "panel": { x: 80, y: 136, dx: -80, dy: -70 } })
        readonly property var hits: ({
            "front": [46, 128, 548, 202], "panel": [52, 126, 140, 20],
            "tanks": [152, 190, 336, 60], "pads": [540, 294, 40, 32] })
        readonly property bool panelLit: app.group(app.hover) === "panel"

        Platform { shadowX: 46; shadowW: 548 }
        Rectangle { x: 180; y: 70; width: 280; height: 70; radius: 4; color: "#c4c8cc"
                    opacity: 1 - 0.72 * app.xray }                                  // paper input
        Rectangle { x: 50; y: 124; width: 540; height: 12; radius: 4; color: "#a9aeb4"
                    opacity: 1 - 0.72 * app.xray }                                  // rear cover
        Shell { x: 46; y: 134; width: 548; height: 44; radius: 9; tone: "#eceef0" }    // scanner
        Rectangle { x: 200; y: 128; width: 390; height: 12; radius: 5; color: "#f4f5f6"
                    border.color: Qt.rgba(0, 0, 0, 0.08); opacity: 1 - 0.72 * app.xray }   // lid
        // control panel with its small screen, left of the lid
        Rectangle {
            x: 52; y: 126; width: 140; height: 20; radius: 5; color: "#2f3237"
            border.color: dj.panelLit ? app.colors.accent : Qt.rgba(1, 1, 1, 0.08)
            border.width: dj.panelLit ? 1.4 : 1
            Rectangle { x: 10; y: 4; width: 40; height: 12; radius: 2
                        color: app.connected ? "#7fd3c0" : "#1d2a28" }
            Repeater { model: 3; Rectangle { x: 60 + index * 16; y: 7; width: 11; height: 6; radius: 2; color: "#41464c" } }
            Light { ring: true; x: 116; y: 4; width: 12 }
        }
        Shell { x: 46; y: 176; width: 548; height: 154; radius: 10; tone: "#e9ecef" }  // body
        Rectangle { x: 160; y: 194; width: 320; height: 54; radius: 4; color: "#3a3f45"
                    opacity: 0.9 * dj.doorOpen }                                     // the open bay
        Rectangle {                                                                   // the door
            x: 152; y: 190 + 58 * dj.doorOpen; width: 336; height: 60 * (1 - 0.8 * dj.doorOpen)
            radius: 4; color: "#eef0f2"; border.color: "#c8cdd2"
            opacity: 1 - 0.72 * app.xray
            Text { anchors.centerIn: parent; visible: dj.doorOpen < 0.5; text: "hp"; color: "#9aa0a6"
                   font.italic: true; font.family: "Segoe UI"; font.pixelSize: 18; font.weight: Font.Bold }
        }
        Rectangle { x: 160; y: 252; width: 320; height: 30; radius: 3; color: "#17191c" }   // slot
        Rectangle { x: 170; y: 280; width: 300; height: 10; radius: 3; color: "#c4c9ce" }   // tray
        Sheet { x: 185; y: 262; width: 270; maxLen: 40 }
        Foot { x: 66 }
        Foot { x: 300 }
        Foot { x: 540 }
        Interior {
            railY: 218; xMin: 200; xMax: 440; parkX: 520
            restX: dj.doorOpen > 0.5 ? 320 : 520     // where the cartridges are changed
            padAt: Qt.point(560, 311)
            cartridges: true; carts: 2; cw: 70; ch: 34
            shown: Math.max(app.xray, dj.doorOpen)
        }
        PadWindow { x: 540; y: 298; width: 40; height: 26 }
    }

    // ---- mono lasers (laser.py): one drawing, sized and coloured per model ------------------
    component LaserArt: Item {
        id: la
        // size in mm (laser.py SPECS) and colours, as the 3D family files
        readonly property var looks: ({
            "hp_laserjet_m111": { title: "HP LaserJet M111w", brand: "hp", toner: "150A", mfp: false,
                                  w: 346, h: 159, body: "#eceef0", cover: "#e4e6e9", panel: "#c9cdd2", logo: "#a0a6ac" },
            "hp_laserjet_m141": { title: "HP LaserJet MFP M141w", brand: "hp", toner: "150A", mfp: true,
                                  w: 360, h: 197, body: "#eceef0", cover: "#e4e6e9", panel: "#c9cdd2", logo: "#a0a6ac" },
            "brother_hl1212w": { title: "Brother HL-1212W", brand: "brother", toner: "TN-1060", mfp: false,
                                 w: 340, h: 189, body: "#25262a", cover: "#2c2e32", panel: "#18191c", logo: "#c9cdd2" },
            "brother_dcp1612w": { title: "Brother DCP-1612W", brand: "brother", toner: "TN-1060", mfp: true,
                                  w: 385, h: 255, body: "#25262a", cover: "#2c2e32", panel: "#18191c", logo: "#c9cdd2" },
            "pantum_p2500w": { title: "Pantum P2500W", brand: "pantum", toner: "PC-210", mfp: false,
                               w: 337, h: 178, body: "#2c2d30", cover: "#1b1c1f", panel: "#151618", logo: "#b9bec4" },
            "pantum_m6550nw": { title: "Pantum M6550NW", brand: "pantum", toner: "PC-210", mfp: true,
                                w: 417, h: 301, body: "#2c2d30", cover: "#1b1c1f", panel: "#151618", logo: "#b9bec4" },
            "samsung_m2020w": { title: "Samsung Xpress M2020W", brand: "samsung", toner: "MLT-D111S", mfp: false,
                                w: 331, h: 178, body: "#eef0f2", cover: "#1f2124", panel: "#1f2124", logo: "#5d646b" },
            "samsung_m2070w": { title: "Samsung Xpress M2070W", brand: "samsung", toner: "MLT-D111S", mfp: true,
                                w: 406, h: 253, body: "#eef0f2", cover: "#1f2124", panel: "#1f2124", logo: "#5d646b" },
        })
        readonly property var look: looks[app.style] || looks["hp_laserjet_m111"]
        readonly property bool mfp: look.mfp

        readonly property string defaultTitle: look.title
        readonly property bool laser: true
        readonly property bool cartridges: true
        readonly property string cartridgeCode: look.toner
        readonly property string cartridgeSpot: mfp ? "el escáner (tóner)" : "la tapa (tóner)"
        readonly property string openText: mfp ? "Levantar el escáner y ver el tóner" : "Abrir la tapa y ver el tóner"
        readonly property string closeText: mfp ? "Cerrar el escáner" : "Cerrar la tapa"
        property real open: app.shot === "tanks" && app.activity === "" ? 1 : 0
        Behavior on open { NumberAnimation { duration: 1100; easing.type: Easing.InOutCubic } }

        // sprite units: 1.3 per mm, standing on the floor (y 330), centred on x 320
        readonly property real bw: look.w * 1.3
        readonly property real bh: look.h * 1.3
        readonly property real bx: 320 - bw / 2
        readonly property real by: 330 - bh
        readonly property real scanH: mfp ? 97 : 0            // scanner unit and lid (75 mm)
        readonly property real bodyY: by + scanH               // top of the printer body
        readonly property real coverH: mfp ? 0 : 20
        readonly property point panelAt: mfp ? Qt.point(bx + bw - 70, by + 20) : Qt.point(bx + bw - 50, by + 8)
        readonly property real shown: Math.max(app.xray, open)

        readonly property var presets: ({
            "front": [1, 320, 215], "tanks": [1.1, 320, bodyY - 10],
            "pads": [1, 320, 215], "panel": [2.0, panelAt.x, panelAt.y + 20] })
        readonly property var callouts: ({
            "tanks": { x: 320 - bw * 0.25, y: open > 0.5 ? bodyY + 34 : by + 8, dx: -100, dy: -90 },
            "panel": open > 0.5 ? undefined : { x: panelAt.x, y: panelAt.y, dx: 80, dy: -70 } })
        readonly property var hits: ({
            "front": [bx, by, bw, bh], "panel": [panelAt.x - 40, panelAt.y - 10, 80, 22],
            "tanks": [bx, by, bw, mfp ? scanH : coverH + 6] })
        readonly property bool panelLit: app.group(app.hover) === "panel"

        Platform { shadowX: la.bx; shadowW: la.bw }
        Shell { x: la.bx; y: la.bodyY; width: la.bw; height: 330 - la.bodyY; radius: 9; tone: la.look.body }  // body
        Text { x: 320 - width / 2; y: la.bodyY + (330 - la.bodyY) * 0.22; text: ({ "hp": "hp", "brother": "brother",
                   "pantum": "PANTUM", "samsung": "SAMSUNG" })[la.look.brand]
               color: la.look.logo; opacity: 1 - 0.72 * app.xray; font.italic: la.look.brand === "hp"
               font.family: la.look.brand === "hp" ? "Segoe UI" : "Arial"; font.pixelSize: 15; font.weight: Font.Bold
               font.letterSpacing: la.look.brand === "pantum" || la.look.brand === "samsung" ? 2 : 0 }
        // the toner cartridge in its well, seen while the cover is up or the shell see-through
        Rectangle {
            x: 320 - la.bw * 0.36; y: la.bodyY + 18; width: la.bw * 0.72; height: 40; radius: 5
            color: "#2b2e33"; border.color: app.hover === "tanks" ? app.colors.accent : Qt.rgba(1, 1, 1, 0.12)
            visible: la.shown > 0.02; opacity: Math.min(1, la.shown * 1.4)
            Rectangle {   // the toner left, as a bar
                x: 10; y: 8; width: (parent.width - 20) * app.inkLevel(0); height: 6; radius: 3
                color: app.inks.length && app.inks[0].level >= 0 && app.inks[0].level <= 15 ? app.colors.warn : "#8a9198"
                Behavior on width { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } }
            }
            Rectangle { x: parent.width / 2 - 30; y: -5; width: 60; height: 9; radius: 4; color: "#454a51" }  // grip
            Text { x: 10; y: 18; text: la.look.toner; color: "#d6dade"
                   font.family: app.colors.family; font.pixelSize: 9; font.weight: Font.Bold }
            Rectangle {   // the drum, green, and the fuser glowing behind it while printing
                x: 6; y: parent.height - 7; width: parent.width - 12; height: 6; radius: 3; color: "#2f6e46"
            }
            Rectangle {
                x: 6; y: parent.height + 4; width: parent.width - 12; height: 4; radius: 2
                color: app.activity === "printing" ? "#ff8a3d" : "#7a2f1c"
                opacity: app.activity === "printing" ? 0.6 + 0.4 * Math.sin(app.time * 6) : 1
            }
        }
        // the paper tray door, low on the front
        Rectangle { x: la.bx + 26; y: 330 - Math.min(70, (330 - la.bodyY) * 0.45) * 1.3 + 4
                    width: la.bw - 52; height: Math.min(70, (330 - la.bodyY) * 0.45) * 1.3 - 16; radius: 4
                    color: Qt.darker(la.look.body, 1.04); border.color: Qt.rgba(0, 0, 0, 0.12)
                    opacity: 1 - 0.72 * app.xray }
        // a multifunction: the pocket the sheets land in, under the scanner
        Rectangle { visible: la.mfp; x: la.bx + 30; y: la.bodyY - 2; width: la.bw - 60; height: 26; radius: 3
                    color: "#0c0d0f"; opacity: 1 - 0.6 * la.open }
        Sheet { x: 320 - 105; y: la.mfp ? la.bodyY + 10 : la.by + 6; width: 210; maxLen: la.mfp ? 14 : 12 }
        // what lifts: the scanner, or the top cover; the panel rides on it
        Item {
            x: 0; y: -(la.mfp ? 70 : 34) * la.open
            width: parent.width; height: parent.height
            Shell { visible: la.mfp; x: la.bx; y: la.by; width: la.bw; height: la.scanH - 4; radius: 9
                    tone: la.look.body }
            Rectangle { visible: la.mfp; x: la.bx + 4; y: la.by - 4; width: la.bw - 8; height: 14; radius: 6
                        color: la.look.cover; opacity: 1 - 0.72 * app.xray }                       // lid
            Rectangle { visible: !la.mfp; x: la.bx; y: la.by; width: la.bw; height: la.coverH; radius: 8
                        color: la.look.cover; border.color: Qt.rgba(0, 0, 0, 0.12)
                        opacity: 1 - 0.72 * app.xray }                                             // top cover
            Rectangle {
                x: la.panelAt.x - 40; y: la.panelAt.y - 8; width: 80; height: 18; radius: 5; color: la.look.panel
                border.color: la.panelLit ? app.colors.accent : Qt.rgba(1, 1, 1, 0.08)
                border.width: la.panelLit ? 1.4 : 1
                Rectangle { visible: la.mfp && la.look.brand !== "hp"; x: 6; y: 4; width: 26; height: 10; radius: 2
                            color: app.connected ? "#7fd3c0" : "#1d2a28" }
                Repeater { model: 2; Light { x: 40 + index * 9; y: 6.5; width: 5 } }
                Light { ring: true; x: 62; y: 3; width: 12 }
            }
        }
        Foot { x: la.bx + 20 }
        Foot { x: la.bx + la.bw - 54 }
    }
}
