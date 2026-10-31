// HP DeskJet 2700 family (style "hp_deskjet_2775": DeskJet 2710, 2720, 2755, Ink Advantage
// 2775, 2776...): white, with cartridges, not tanks. The two HP 667 cartridges (black and
// tri-colour) ride in the carriage behind the front door; the scene folds the door down to
// show them (camera "tanks") and the carriage comes to the middle, where they are changed,
// as the real printer does. The waste ink drains from the service station (right, where
// the carriage parks) into a felt pad in the base, seen through a pane in the right side.
// Meshes: meshes/hp_deskjet_2775/. `app` is the Printer3D root; scene units are 1 mm.
import QtQuick
import QtQuick3D

Node {
    id: style
    required property Item app

    readonly property string defaultTitle: "HP DeskJet Ink Advantage 2775"
    // the ink lives in cartridges: Printer3D words its labels and notes for them
    readonly property bool cartridges: true
    readonly property string inkPart: "Cartuchos"
    readonly property string cartridgeCode: "667"
    readonly property string cartridgeSpot: "la tapa frontal (cartuchos)"
    readonly property string openText: "Bajar la tapa y ver los cartuchos"
    readonly property string closeText: "Cerrar la tapa"

    // 0 closed - 1 open: the front door folds down while the camera looks at the cartridges
    property real doorOpen: app.shot === "tanks" && app.activity === "" ? 1 : 0
    Behavior on doorOpen { NumberAnimation { duration: 1100; easing.type: Easing.InOutCubic } }

    readonly property var presets: ({
        "front":  [26, 16, 950, Qt.vector3d(0, 62, 20)],
        "tanks":  [0, 16, 560, Qt.vector3d(0, 70, 150)],
        "pads":   [70, 25, 520, Qt.vector3d(212, 29, -10)],
        "panel":  [-14, 50, 480, Qt.vector3d(-160, 137, 110)],
    })
    readonly property var callouts: ({
        "pads":  { anchor: Qt.vector3d(213, 29, -10), normal: Qt.vector3d(1, 0, 0), dx: 90, dy: -80 },
        // on the door while closed, on the cartridges once it is down
        "tanks": style.doorOpen > 0.5
                 ? { anchor: Qt.vector3d(mech.cx, 96, 105), normal: Qt.vector3d(0, 0.3, 1).normalized(),
                     dx: -110, dy: -90 }
                 : { anchor: Qt.vector3d(0, 74, 153), normal: Qt.vector3d(0, 0, 1), dx: -100, dy: -90 },
        "panel": { anchor: Qt.vector3d(-160, 138, 110), normal: Qt.vector3d(0, 1, 0.35).normalized(),
                   dx: -80, dy: -70 },
    })

    // the door's hinge (dm): its bottom front edge, from hp_deskjet.py DOOR / Y0
    readonly property vector3d hinge: Qt.vector3d(0, 0.506, 1.524)

    Node {
        id: printer
        scale: Qt.vector3d(100, 100, 100)

        ShellMaterial { id: mShell; baseColor: "#eceef0"; roughness: 0.42; specularAmount: 0.45; xray: app.xray }
        ShellMaterial { id: mLidShell; baseColor: "#f4f5f6"; roughness: 0.38; specularAmount: 0.5; xray: app.xray }
        ShellMaterial { id: mGrey; baseColor: "#a9aeb4"; roughness: 0.5; specularAmount: 0.45; xray: app.xray }
        ShellMaterial { id: mHoleShell; baseColor: "#0c0d0f"; roughness: 1.0; specularAmount: 0.05; xray: app.xray }
        ShellMaterial { id: mInner; baseColor: "#646a71"; roughness: 0.6; specularAmount: 0.35
                        seeThrough: 0.6; xray: app.xray }
        PrincipledMaterial { id: mPanel; baseColor: "#2f3237"; roughness: 0.35; specularAmount: 0.7 }
        PrincipledMaterial { id: mTray; baseColor: "#c4c8cc"; roughness: 0.4; specularAmount: 0.5 }
        PrincipledMaterial { id: mButton; baseColor: "#41464c"; roughness: 0.35 }
        PrincipledMaterial { id: mRubber; baseColor: "#0a0a0a"; roughness: 0.95 }
        PrincipledMaterial { id: mTrim; baseColor: "#9aa0a6"; roughness: 0.3; specularAmount: 0.7 }
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
                                          : Qt.vector3d(2.4, 2.4, 2.6))
                            : Qt.vector3d(0.06, 0.07, 0.07)
        }
        PrincipledMaterial {   // the ink light: blinks orange while a cartridge runs low
            id: mLeds
            baseColor: "#101010"
            lighting: PrincipledMaterial.NoLighting
            readonly property real blink: 0.5 + 0.5 * Math.sin(app.time * 4)
            emissiveFactor: app.connected && style.lowInk >= 0
                            ? Qt.vector3d(2.8 * blink, 1.3 * blink, 0.1)
                            : app.connected ? Qt.vector3d(0.25, 0.75, 2.4) : Qt.vector3d(0.03, 0.03, 0.03)
        }
        PrincipledMaterial {
            id: mPane
            baseColor: "#5a6b7a"
            opacity: 0.22
            alphaMode: PrincipledMaterial.Blend
            roughness: 0.1
            specularAmount: 1.0
            emissiveFactor: app.hover === "pads" ? Qt.vector3d(0.04, 0.18, 0.17) : Qt.vector3d(0, 0, 0)
        }

        Model { source: "meshes/hp_deskjet_2775/body_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true
                pickable: true; property string part: "front" }
        Model { source: "meshes/hp_deskjet_2775/bay_mesh.mesh"; materials: mInner; receivesShadows: true }
        Model { source: "meshes/hp_deskjet_2775/scanner_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/hp_deskjet_2775/lid_mesh.mesh"; materials: mLidShell; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/hp_deskjet_2775/rear_cover_mesh.mesh"; materials: mGrey; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/hp_deskjet_2775/paper_support_mesh.mesh"; materials: mTray; castsShadows: true; receivesShadows: true }
        Model { source: "meshes/hp_deskjet_2775/slot_inner_mesh.mesh"; materials: mHoleShell }
        Model { source: "meshes/hp_deskjet_2775/tray_mesh.mesh"; materials: mTray; castsShadows: true; receivesShadows: true }
        Model { source: "meshes/hp_deskjet_2775/feet_mesh.mesh"; materials: mRubber }
        Model { source: "meshes/hp_deskjet_2775/panel_mesh.mesh"; materials: mPanel; receivesShadows: true
                pickable: true; property string part: "panel" }
        Model { source: "meshes/hp_deskjet_2775/lcd_mesh.mesh"; materials: mLcd }
        Model { source: "meshes/hp_deskjet_2775/buttons_mesh.mesh"; materials: mButton; pickable: true; property string part: "panel" }
        Model { source: "meshes/hp_deskjet_2775/power_ring_mesh.mesh"; materials: mRing }
        Model { source: "meshes/hp_deskjet_2775/leds_mesh.mesh"; materials: mLeds }

        // the cartridge door, hinged at its bottom edge: it folds down to show the cartridges
        Node {
            position: style.hinge
            eulerRotation: Qt.vector3d(82 * style.doorOpen, 0, 0)
            Node {
                position: style.hinge.times(-1)
                Model { source: "meshes/hp_deskjet_2775/door_mesh.mesh"; materials: mShell
                        castsShadows: app.xray < 0.5; receivesShadows: true
                        pickable: true; property string part: "tanks" }
                BrandLogo { brand: "hp"; position: Qt.vector3d(0, 0.74, 1.526)
                            scale: Qt.vector3d(0.001, 0.001, 0.001); size: 13; color: "#9aa0a6" }
            }
        }

        // waste ink: service station, the felt pad under it, the side window
        Model { source: "meshes/hp_deskjet_2775/pad_cavity_mesh.mesh"; materials: mInner; receivesShadows: true }
        Model {
            source: "meshes/hp_deskjet_2775/pad_box_mesh.mesh"
            receivesShadows: true
            materials: PrincipledMaterial { baseColor: "#3b4148"; roughness: 0.55; specularAmount: 0.5 }
        }
        Model {
            source: "meshes/hp_deskjet_2775/pads_mesh.mesh"
            receivesShadows: true
            materials: PadFelt {
                reach: 0.8
                source: Qt.vector3d(1.65, 0.22, -0.10)
                highlight: app.hover === "pads" ? 1.0
                           : app.activity === "cleaning" ? 0.45 + 0.4 * Math.sin(app.time * 4) : 0.0
                shownFill: app.padFill
            }
        }
        Model { source: "meshes/hp_deskjet_2775/service_station_mesh.mesh"; receivesShadows: true
                materials: PrincipledMaterial { baseColor: "#272a2f"; roughness: 0.5; specularAmount: 0.4 } }
        Model { source: "meshes/hp_deskjet_2775/station_caps_mesh.mesh"; materials: mRubber }
        Model { source: "meshes/hp_deskjet_2775/pad_trim_mesh.mesh"; materials: mTrim }
        Model { source: "meshes/hp_deskjet_2775/pad_window_mesh.mesh"; materials: mPane
                pickable: true; property string part: "pads" }
    }

    // the first cartridge running low (level 0-15 %), or -1
    readonly property int lowInk: {
        var inks = app.inks
        for (var i = 0; i < Math.min(2, inks.length); i++)
            if (inks[i].level >= 0 && inks[i].level <= 15) return i
        return -1
    }

    // the inside: carriage, sheet and drain; shown while see-through or while the door is
    // down (scene units, 1 mm)
    Mechanism {
        id: mech
        app: style.app
        shown: Math.max(style.app.xray, style.doorOpen)
        showFeeds: false
        xMin: -100; xMax: 100; parkX: 165
        restX: style.doorOpen > 0.5 ? 0 : 165
        railY: 64; headZ: 105
        carriageSize: Qt.vector3d(70, 20, 40)
        paperX: 0; paperY: 30; paperW: 210; paperL: 280; rearZ: -130
        // the caps under the parked heads, then the drain back to the felt
        drain: [Qt.vector3d(165, 46, 105), Qt.vector3d(165, 30, 105), Qt.vector3d(165, 30, -10),
                Qt.vector3d(165, 22, -10)]
    }

    // the two HP 667 cartridges in the carriage, black and tri-colour; they ride with it
    Node {
        visible: mech.visible
        opacity: mech.opacity
        position: Qt.vector3d(mech.cx, mech.cy + 10, mech.headZ)
        Repeater3D {
            model: [{ mesh: "cart_k", x: -18 }, { mesh: "cart_c", x: 10 }]
            Node {
                id: cart
                required property int index
                required property var modelData
                readonly property var ink: style.app.inks[index]
                readonly property bool low: !!ink && ink.level >= 0 && ink.level <= 15
                readonly property color tint: style.app.inkColor(index)
                x: modelData.x
                Node {
                    scale: Qt.vector3d(100, 100, 100)
                    Model {
                        source: "meshes/hp_deskjet_2775/" + cart.modelData.mesh + "_shell_mesh.mesh"
                        pickable: true; property string part: "tanks"
                        materials: PrincipledMaterial {
                            baseColor: "#4a525c"; opacity: 0.26
                            alphaMode: PrincipledMaterial.Blend
                            roughness: 0.18; specularAmount: 1.0
                            emissiveFactor: style.app.hover === "tanks" ? Qt.vector3d(0.04, 0.16, 0.15)
                                                                         : Qt.vector3d(0, 0, 0)
                        }
                    }
                    Model {
                        source: "meshes/hp_deskjet_2775/" + cart.modelData.mesh + "_ink_mesh.mesh"
                        position: Qt.vector3d(0, 0.015, 0)
                        scale: Qt.vector3d(1, 0.26, 1)
                        materials: InkLiquid {
                            inkColor: cart.tint
                            time: style.app.time + cart.index * 1.7
                            slosh: mech.mode === "printing" ? 2.2 : 0.5
                            glow: style.app.hover === "tanks" ? 1.6 : 1.0
                            shownLevel: style.app.inkLevel(cart.index)
                        }
                    }
                    Model {
                        source: "meshes/hp_deskjet_2775/" + cart.modelData.mesh + "_label_mesh.mesh"
                        materials: PrincipledMaterial {
                            baseColor: cart.tint
                            roughness: 0.35
                            readonly property real blink: cart.low ? 0.5 + 0.5 * Math.sin(style.app.time * 5) : 0
                            emissiveFactor: Qt.vector3d(cart.tint.r * blink, cart.tint.g * blink,
                                                        cart.tint.b * blink)
                        }
                    }
                    Model {
                        source: "meshes/hp_deskjet_2775/" + cart.modelData.mesh + "_tab_mesh.mesh"
                        materials: PrincipledMaterial { baseColor: "#1a1c20"; roughness: 0.4 }
                    }
                }
                // "667" printed on the label
                Label3D { text: cartridgeCode; position: Qt.vector3d(0, 30.9, -8)
                          eulerRotation: Qt.vector3d(-90, 0, 0); scale: Qt.vector3d(0.06, 0.06, 0.06)
                          size: 7; weight: Font.Bold; family: app.colors.family; color: "#f4f6f8" }
            }
        }
    }

    // printed lettering (1 unit = 1 mm)
    Label3D { text: "DeskJet"; position: Qt.vector3d(130, 119, 152.6); size: 5.5
              family: app.colors.family; color: "#7d848b" }
}
