// A mono laser printer (the styles of view3d/printers/laser.py), dressed by its family file
// (HpLaserJet.qml, BrotherLaser.qml, PantumLaser.qml, SamsungLaser.qml): colours, logo,
// toner code and the size of each model. One toner cartridge with its drum under the
// cover at the top front (printers) or under the scanner (multifunction), which the scene
// opens to show it (camera "tanks"). No ink and no waste pads: the HUD shows the toner and
// hides the pads (`laser`). While it prints, the drum turns, the fuser glows and the sheet
// comes out on top with its text.
// Meshes: meshes/<style>/. `app` is the Printer3D root; scene units are 1 mm.
import QtQuick
import QtQuick3D

Node {
    id: style
    required property Item app

    // ---- what the family file sets -----------------------------------------------------
    property string defaultTitle: ""
    property string brand: "hp"
    property string tonerCode: ""
    property bool mfp: false
    property real w: 3.4                   // width, depth, height in dm (laser.py SPECS)
    property real d: 2.2
    property real h: 1.8
    property color bodyColor: "#eceef0"
    property color coverColor: "#e2e4e7"   // toner cover, scanner lid
    property color scannerColor: bodyColor
    property color floorColor: "#b8bcc1"   // where the sheets land
    property color doorColor: bodyColor    // the paper tray door
    property color panelColor: "#2f3237"
    property color logoColor: "#9aa0a6"
    property real gloss: 0.4               // 0 matte - 1 glossy plastic

    // ---- what Printer3D asks a style ---------------------------------------------------
    readonly property bool laser: true
    readonly property bool cartridges: true
    readonly property string inkPart: "Tóner"
    readonly property string cartridgeCode: tonerCode
    readonly property string cartridgeSpot: mfp ? "el escáner (tóner)" : "la tapa (tóner)"
    readonly property string openText: mfp ? "Levantar el escáner y ver el tóner"
                                           : "Abrir la tapa y ver el tóner"
    readonly property string closeText: mfp ? "Cerrar el escáner" : "Cerrar la tapa"

    // ---- the layout, as laser.py layout() (dm) -----------------------------------------
    readonly property real x1: w / 2
    readonly property real y0: -d / 2
    readonly property real y1: d / 2
    readonly property real top: mfp ? h - 0.75 : h
    readonly property real tonerW: Math.min(w - 0.55, 3.0)
    readonly property real tonerY: y0 + 0.55            // centre of the cartridge
    readonly property real tonerZ: top - (mfp ? 0.96 : 0.90)     // its base
    readonly property real coverY: y0 + 1.20             // back edge of a printer's top cover
    readonly property real outY0: mfp ? y0 + 0.02 : y0 + 0.14    // the sheets' landing
    readonly property real outY1: mfp ? y1 - 0.62 : coverY - 0.10
    readonly property real outZ: mfp ? top - 0.28 : top - 0.08
    // what lifts to reach the toner: the scanner (hinged at its back top edge) or the top
    // cover (hinged at its back edge), and how far (degrees)
    readonly property vector3d hinge: mfp ? Qt.vector3d(0, h - 0.16, -y1) : Qt.vector3d(0, top, -coverY)
    readonly property real lift: mfp ? 38 : 62
    // the panel's middle (scene mm)
    readonly property vector3d panelAt: mfp ? Qt.vector3d((x1 - 0.78) * 100, (h - 0.15) * 100, -(y0 + 0.20) * 100)
                                            : Qt.vector3d((x1 - 0.485) * 100, (top + 0.01) * 100, -(y0 + 0.45) * 100)
    readonly property real big: Math.max(w, d, h) * 100

    // 0 closed - 1 open: the cover (or the scanner) lifts while the camera looks at the toner
    property real open: app.shot === "tanks" && app.activity === "" ? 1 : 0
    Behavior on open { NumberAnimation { duration: 1100; easing.type: Easing.InOutCubic } }

    readonly property var presets: ({
        "front":  [26, 16, big * 2.6, Qt.vector3d(0, h * 45, 20)],
        "tanks":  [14, 42, big * 1.9, Qt.vector3d(0, top * 80, -tonerY * 100)],
        "pads":   [26, 16, big * 2.6, Qt.vector3d(0, h * 45, 20)],
        "panel":  [-14, 50, big * 1.5, panelAt],
    })
    readonly property var callouts: ({
        "tanks": open > 0.5
                 ? { anchor: Qt.vector3d(0, (tonerZ + 0.62) * 100, -tonerY * 100),
                     normal: Qt.vector3d(0, 1, 0.4).normalized(), dx: -110, dy: -90 }
                 : mfp ? { anchor: Qt.vector3d(-x1 * 40, h * 100, 0), normal: Qt.vector3d(0, 1, 0.3).normalized(),
                           dx: -100, dy: -90 }
                       : { anchor: Qt.vector3d(-x1 * 40, top * 100, -(y0 + 0.60) * 100),
                           normal: Qt.vector3d(0, 1, 0.5).normalized(), dx: -100, dy: -90 },
        // the panel lifts with the cover (or scanner): no label while it is up
        "panel": open > 0.5 ? undefined
                            : { anchor: panelAt, normal: Qt.vector3d(0, 1, 0.35).normalized(), dx: 80, dy: -70 },
    })

    readonly property string meshes: "meshes/" + app.style + "/"
    // the toner running low (0-15 %)
    readonly property bool low: { var k = app.inks[0]; return !!k && k.level >= 0 && k.level <= 15 }

    Node {
        id: printer
        scale: Qt.vector3d(100, 100, 100)

        ShellMaterial { id: mBody; baseColor: style.bodyColor; roughness: 0.6 - 0.35 * style.gloss
                        specularAmount: 0.4 + 0.5 * style.gloss; xray: app.xray }
        ShellMaterial { id: mCover; baseColor: style.coverColor; roughness: 0.55 - 0.35 * style.gloss
                        specularAmount: 0.45 + 0.5 * style.gloss; xray: app.xray }
        ShellMaterial { id: mScanner; baseColor: style.scannerColor; roughness: 0.6 - 0.35 * style.gloss
                        specularAmount: 0.4 + 0.5 * style.gloss; xray: app.xray }
        ShellMaterial { id: mDoor; baseColor: style.doorColor; roughness: 0.5; specularAmount: 0.5; xray: app.xray }
        ShellMaterial { id: mHoleShell; baseColor: "#0c0d0f"; roughness: 1.0; specularAmount: 0.05; xray: app.xray }
        PrincipledMaterial { id: mFloor; baseColor: style.floorColor; roughness: 0.5; specularAmount: 0.5 }
        PrincipledMaterial { id: mPanel; baseColor: style.panelColor; roughness: 0.32; specularAmount: 0.7 }
        PrincipledMaterial { id: mButton; baseColor: Qt.lighter(style.panelColor, 1.3); roughness: 0.35 }
        PrincipledMaterial { id: mRubber; baseColor: "#0a0a0a"; roughness: 0.95 }
        PrincipledMaterial {
            id: mLcd
            baseColor: "#07090b"
            roughness: 0.08
            specularAmount: 1.0
            emissiveFactor: app.connected ? Qt.vector3d(0.10, 0.28, 0.34) : Qt.vector3d(0, 0, 0)
        }
        PrincipledMaterial {
            id: mRing
            baseColor: "#101010"
            lighting: PrincipledMaterial.NoLighting
            readonly property real pulse: app.d.busy ? 0.55 + 0.45 * Math.sin(app.time * 5) : 1
            emissiveFactor: app.connected
                            ? (app.d.busy ? Qt.vector3d(2.6 * pulse, 1.6 * pulse, 0.2)
                                          : Qt.vector3d(0.4, 2.6, 0.6))
                            : Qt.vector3d(0.06, 0.07, 0.07)
        }
        PrincipledMaterial {   // status and toner lights: the toner one blinks while it runs low
            id: mLeds
            baseColor: "#101010"
            lighting: PrincipledMaterial.NoLighting
            readonly property real blink: 0.5 + 0.5 * Math.sin(app.time * 4)
            emissiveFactor: app.connected && style.low ? Qt.vector3d(2.8 * blink, 1.3 * blink, 0.1)
                            : app.connected ? Qt.vector3d(0.3, 2.2, 0.6) : Qt.vector3d(0.03, 0.03, 0.03)
        }

        Model { source: style.meshes + "body_mesh.mesh"; materials: mBody; castsShadows: app.xray < 0.5; receivesShadows: true
                pickable: true; property string part: "front" }
        Model { source: style.meshes + "tray_door_mesh.mesh"; materials: mDoor; receivesShadows: true
                pickable: true; property string part: "front" }
        Model { source: style.meshes + "slot_inner_mesh.mesh"; materials: mHoleShell }
        Model { source: style.meshes + "feet_mesh.mesh"; materials: mRubber }
        // a multifunction's sheets land in the pocket under the scanner; it steps aside
        // while the scanner is up, to show the toner under it
        Node {
            visible: style.mfp && style.open < 0.4
            Model { source: style.mfp ? style.meshes + "out_floor_mesh.mesh" : ""; materials: mFloor; receivesShadows: true }
            Model { source: style.mfp ? style.meshes + "out_stop_mesh.mesh" : ""; materials: mFloor; receivesShadows: true }
        }

        // what lifts to reach the toner, with the panel on it: the scanner and its lid
        // (multifunction), or the top cover with the sheets' recess (printer)
        Node {
            position: style.hinge
            eulerRotation: Qt.vector3d(-style.lift * style.open, 0, 0)
            Node {
                position: style.hinge.times(-1)
                Model { source: style.mfp ? style.meshes + "scanner_mesh.mesh" : ""; materials: mScanner
                        castsShadows: app.xray < 0.5; receivesShadows: true
                        pickable: true; property string part: "tanks" }
                Model { source: style.mfp ? style.meshes + "lid_mesh.mesh" : ""; materials: mCover
                        castsShadows: app.xray < 0.5; receivesShadows: true
                        pickable: true; property string part: "tanks" }
                Model { source: style.mfp ? "" : style.meshes + "top_cover_mesh.mesh"; materials: mCover
                        castsShadows: app.xray < 0.5; receivesShadows: true
                        pickable: true; property string part: "tanks" }
                Model { source: style.mfp ? "" : style.meshes + "out_floor_mesh.mesh"; materials: mFloor; receivesShadows: true }
                Model { source: style.mfp ? "" : style.meshes + "out_stop_mesh.mesh"; materials: mFloor; receivesShadows: true }
                Model { source: style.meshes + "panel_mesh.mesh"; materials: mPanel; receivesShadows: true
                        pickable: true; property string part: "panel" }
                Model { source: style.mfp && style.hasLcd ? style.meshes + "lcd_mesh.mesh" : ""; materials: mLcd }
                Model { source: style.meshes + "buttons_mesh.mesh"; materials: mButton
                        pickable: true; property string part: "panel" }
                Model { source: style.meshes + "power_ring_mesh.mesh"; materials: mRing }
                Model { source: style.meshes + "leds_mesh.mesh"; materials: mLeds }
            }
        }
    }
    property bool hasLcd: false

    // ---- the inside: the toner cartridge and its drum, the fuser, the sheet ------------
    readonly property real shown: Math.max(app.xray, open)
    property real printT: 0
    property real rollA: 0
    readonly property bool moving: app.activity === "printing" || app.activity === "feeding"
    FrameAnimation {
        running: style.app.active && (style.moving || style.printT !== 0)
        onTriggered: {
            var dt = Math.min(frameTime, 0.05)
            if (style.moving) {
                style.printT += dt * (style.app.activity === "feeding" ? 1.6 : 1)
                style.rollA = (style.rollA + dt * 200) % 360
            } else {
                style.printT = 0
            }
        }
    }

    // the cartridge is always there (seen through the open cover or the see-through shell)
    Node {
        position: Qt.vector3d(0, style.tonerZ * 100, -style.tonerY * 100)
        Node {
            scale: Qt.vector3d(100, 100, 100)
            Model { source: style.meshes + "toner_body_mesh.mesh"
                    pickable: true; property string part: "tanks"
                    materials: PrincipledMaterial {
                        baseColor: "#2b2e33"; roughness: 0.45; specularAmount: 0.5
                        emissiveFactor: style.app.hover === "tanks" ? Qt.vector3d(0.04, 0.16, 0.15)
                                                                     : Qt.vector3d(0, 0, 0)
                    } }
            Model { source: style.meshes + "toner_grip_mesh.mesh"
                    materials: PrincipledMaterial {
                        baseColor: style.low ? "#e08a1e" : "#454a51"; roughness: 0.4
                        readonly property real blink: style.low ? 0.5 + 0.5 * Math.sin(style.app.time * 5) : 0
                        emissiveFactor: Qt.vector3d(0.9 * blink, 0.45 * blink, 0.05 * blink)
                    } }
            // the drum, under the front edge: green, it turns while printing
            Model { source: style.meshes + "toner_drum_mesh.mesh"
                    position: Qt.vector3d(0, 0.12, 0.33)
                    eulerRotation: Qt.vector3d(style.rollA, 0, 0)
                    materials: PrincipledMaterial { baseColor: "#2f6e46"; metalness: 0.3; roughness: 0.25 } }
        }
        Label3D { text: style.tonerCode; position: Qt.vector3d(30, 62.6, 10)
                  eulerRotation: Qt.vector3d(-90, 0, 0); size: 5; weight: Font.Bold
                  family: style.app.colors.family; color: "#d6dade" }
    }

    // the fuser, behind the cartridge: two rollers, glowing while they fuse the toner
    Node {
        visible: style.shown > 0.02
        opacity: Math.min(1, style.shown * 1.4)
        position: Qt.vector3d(0, (style.tonerZ + 0.25) * 100, -(style.tonerY + 0.62) * 100)
        Repeater3D {
            model: [0, 15]
            Model {
                source: "#Cylinder"
                y: modelData
                eulerRotation: Qt.vector3d(0, 0, 90)
                scale: Qt.vector3d(0.12, style.tonerW * 0.95, 0.12)
                materials: PrincipledMaterial {
                    baseColor: index ? "#3a3f46" : "#7a2f1c"
                    roughness: 0.4
                    readonly property real heat: style.moving && index === 0 ? 0.7 + 0.3 * Math.sin(style.app.time * 6) : 0
                    emissiveFactor: Qt.vector3d(2.4 * heat, 0.9 * heat, 0.1 * heat)
                }
            }
        }
    }

    // the sheet coming out onto the top (or under the scanner), printed with text
    Node {
        visible: style.moving
        position: Qt.vector3d(-105, style.outZ * 100 + 3, -style.outY1 * 100)
        eulerRotation: Qt.vector3d(-90, 0, 0)     // flat: the 2D item's y is the scene's z
        Item {
            id: sheet
            readonly property real period: 9
            readonly property real u: (style.printT % period) / period
            readonly property real len: 297 * Math.min(1, u / 0.8)
            width: 210
            height: len
            opacity: u > 0.9 ? (1 - u) * 10 : 1
            Rectangle { anchors.fill: parent; color: "#f4f4ef" }
            Column {
                visible: style.app.activity === "printing"
                anchors.bottom: parent.bottom       // the leading edge is the first printed
                anchors.bottomMargin: 18
                x: 18
                spacing: 6
                Repeater {
                    model: Math.max(0, Math.floor((sheet.len - 36) / 10))
                    Rectangle { width: 174 - (index * 37) % 70; height: 4; color: "#1d1d1f"; opacity: 0.85 }
                }
            }
        }
    }

    // printed lettering (1 unit = 1 mm)
    BrandLogo { brand: style.brand; color: style.logoColor; size: 12
                position: Qt.vector3d(0, (Math.min(0.70, style.top * 0.45) + style.top) * 50,
                                      -style.y0 * 100 + 0.3) }
}
