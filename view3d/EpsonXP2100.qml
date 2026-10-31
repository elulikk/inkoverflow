// Epson XP-2100 family (style "epson_xp2100": XP-2100, XP-2101, XP-2105): a compact
// all-black multifunction with cartridges, not tanks. The four Epson 206 cartridges
// (K, C, M, Y) ride in the print carriage under the scanner unit; the scene lifts the
// scanner unit to show them (camera "tanks"), and the carriage then moves to the middle,
// where the cartridges are changed, as the real printer does. The waste ink drains from
// the service station (right, where the carriage parks) into felt pads in the base,
// shown through a see-through pane in the right side.
// Meshes: meshes/epson_xp2100/. `app` is the Printer3D root; scene units are 1 mm.
import QtQuick
import QtQuick3D

Node {
    id: style
    required property Item app

    readonly property string defaultTitle: "Epson XP-2100"
    // the ink lives in cartridges: Printer3D words its labels and notes for them
    readonly property bool cartridges: true
    readonly property string inkPart: "Cartuchos"
    readonly property string cartridgeCode: "206"

    // 0 closed - 1 open: the scanner unit lifts while the camera looks at the cartridges
    property real lidOpen: app.shot === "tanks" && app.activity === "" ? 1 : 0
    Behavior on lidOpen { NumberAnimation { duration: 1100; easing.type: Easing.InOutCubic } }

    readonly property var presets: ({
        "front":  [28, 16, 900, Qt.vector3d(0, 70, 20)],
        "tanks":  [12, 48, 580, Qt.vector3d(-20, 80, 10)],
        "pads":   [72, 22, 520, Qt.vector3d(165, 28, 5)],
        "panel":  [-12, 10, 470, Qt.vector3d(-70, 70, 150)],
    })
    readonly property var callouts: ({
        "pads":  { anchor: Qt.vector3d(187, 27, -12), normal: Qt.vector3d(1, 0, 0), dx: 90, dy: -80 },
        // on the lid while closed, on the cartridges once it is up
        "tanks": style.lidOpen > 0.5
                 ? { anchor: Qt.vector3d(mech.cx, 92, 5), normal: Qt.vector3d(0, 1, 0.4).normalized(),
                     dx: -110, dy: -90 }
                 : { anchor: Qt.vector3d(-40, 145.5, 20), normal: Qt.vector3d(0, 1, 0.3).normalized(),
                     dx: -100, dy: -90 },
        "panel": { anchor: Qt.vector3d(-145, 69, 152), normal: Qt.vector3d(0, 0, 1), dx: -80, dy: -70 },
    })

    // scanner unit hinge (dm): the back edge of its top, from make_model.py X_REAR / X_SCAN
    readonly property vector3d hinge: Qt.vector3d(0, 1.36, -1.16)

    Node {
        id: printer
        scale: Qt.vector3d(100, 100, 100)

        PrincipledMaterial { id: mHole; baseColor: "#040405"; roughness: 1.0; specularAmount: 0.05 }
        ShellMaterial { id: mShell; baseColor: "#25282d"; roughness: 0.6; specularAmount: 0.8; xray: app.xray }
        ShellMaterial { id: mLidShell; baseColor: "#202327"; roughness: 0.78; specularAmount: 0.6; xray: app.xray }
        ShellMaterial { id: mGloss; baseColor: "#1c1e22"; roughness: 0.28; specularAmount: 0.95
                        clearcoatAmount: 0.35; clearcoatRoughnessAmount: 0.25; xray: app.xray }
        ShellMaterial { id: mHoleShell; baseColor: "#040405"; roughness: 1.0; specularAmount: 0.05; xray: app.xray }
        ShellMaterial { id: mInner; baseColor: "#1d2024"; roughness: 0.7; specularAmount: 0.3
                        seeThrough: 0.6; xray: app.xray }
        PrincipledMaterial { id: mTray; baseColor: "#2b2f34"; roughness: 0.55; specularAmount: 0.6 }
        PrincipledMaterial { id: mButton; baseColor: "#24272c"; roughness: 0.3; specularAmount: 0.7 }
        PrincipledMaterial { id: mRubber; baseColor: "#161718"; roughness: 0.95 }
        PrincipledMaterial { id: mTrim; baseColor: "#24272b"; roughness: 0.25; specularAmount: 0.8 }
        PrincipledMaterial {
            id: mRing
            baseColor: "#101010"
            lighting: PrincipledMaterial.NoLighting
            readonly property real pulse: app.d.busy ? 0.55 + 0.45 * Math.sin(app.time * 5) : 1
            emissiveFactor: app.connected
                            ? (app.d.busy ? Qt.vector3d(2.6 * pulse, 1.6 * pulse, 0.2)
                                          : Qt.vector3d(0.6, 2.6, 0.5))
                            : Qt.vector3d(0.06, 0.07, 0.07)
        }
        PrincipledMaterial {   // Wi-Fi and status lights
            id: mLeds
            baseColor: "#101010"
            lighting: PrincipledMaterial.NoLighting
            emissiveFactor: app.connected ? Qt.vector3d(0.3, 2.2, 0.6) : Qt.vector3d(0.03, 0.03, 0.03)
        }
        PrincipledMaterial {   // the ink light: blinks orange while a cartridge runs low
            id: mInkLed
            baseColor: "#101010"
            lighting: PrincipledMaterial.NoLighting
            readonly property real blink: 0.5 + 0.5 * Math.sin(app.time * 4)
            emissiveFactor: app.connected && style.lowInk >= 0
                            ? Qt.vector3d(2.8 * blink, 1.3 * blink, 0.1) : Qt.vector3d(0.03, 0.03, 0.03)
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

        Model { source: "meshes/epson_xp2100/body_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true
                pickable: true; property string part: "front" }
        Model { source: "meshes/epson_xp2100/front_panel_mesh.mesh"; materials: mGloss; receivesShadows: true
                pickable: true; property string part: "panel" }
        Model { source: "meshes/epson_xp2100/rear_cover_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/epson_xp2100/paper_support_mesh.mesh"; materials: mTray; castsShadows: true; receivesShadows: true }
        Model { source: "meshes/epson_xp2100/paper_guide_mesh.mesh"; materials: mTray }
        Model { source: "meshes/epson_xp2100/slot_inner_mesh.mesh"; materials: mHoleShell }
        Model { source: "meshes/epson_xp2100/bay_mesh.mesh"; materials: mInner; receivesShadows: true }
        Model { source: "meshes/epson_xp2100/tray_mesh.mesh"; materials: mTray; castsShadows: true; receivesShadows: true }
        Model { source: "meshes/epson_xp2100/feet_mesh.mesh"; materials: mRubber }
        Model { source: "meshes/epson_xp2100/buttons_mesh.mesh"; materials: mButton
                pickable: true; property string part: "panel" }
        Model { source: "meshes/epson_xp2100/power_ring_mesh.mesh"; materials: mRing }
        Model { source: "meshes/epson_xp2100/leds_mesh.mesh"; materials: mLeds }
        Model { source: "meshes/epson_xp2100/ink_led_mesh.mesh"; materials: mInkLed }

        // scanner unit and its lid, hinged at the back: they lift to show the cartridges
        Node {
            position: style.hinge
            eulerRotation: Qt.vector3d(-38 * style.lidOpen, 0, 0)
            Node {
                position: style.hinge.times(-1)
                Model { source: "meshes/epson_xp2100/scanner_mesh.mesh"; materials: mShell
                        castsShadows: app.xray < 0.5; receivesShadows: true
                        pickable: true; property string part: "tanks" }
                Model { source: "meshes/epson_xp2100/lid_mesh.mesh"; materials: mLidShell
                        castsShadows: app.xray < 0.5; receivesShadows: true
                        pickable: true; property string part: "tanks" }
                Model { source: "meshes/epson_xp2100/grip_mesh.mesh"; materials: mHoleShell }
            }
        }

        // waste ink: service station, the felt pads under it, the side window
        Model { source: "meshes/epson_xp2100/pad_cavity_mesh.mesh"; materials: mInner; receivesShadows: true }
        Model {
            source: "meshes/epson_xp2100/pad_box_mesh.mesh"
            receivesShadows: true
            materials: PrincipledMaterial { baseColor: "#3b4148"; roughness: 0.55; specularAmount: 0.5 }
        }
        Model {
            source: "meshes/epson_xp2100/pads_mesh.mesh"
            receivesShadows: true
            materials: PadFelt {
                reach: 0.8
                source: Qt.vector3d(1.37, 0.20, 0.08)
                highlight: app.hover === "pads" ? 1.0
                           : app.activity === "cleaning" ? 0.45 + 0.4 * Math.sin(app.time * 4) : 0.0
                shownFill: app.padFill
            }
        }
        Model { source: "meshes/epson_xp2100/service_station_mesh.mesh"; receivesShadows: true
                materials: PrincipledMaterial { baseColor: "#272a2f"; roughness: 0.5; specularAmount: 0.4 } }
        Model { source: "meshes/epson_xp2100/station_caps_mesh.mesh"; materials: mRubber }
        Model { source: "meshes/epson_xp2100/pad_trim_mesh.mesh"; materials: mTrim }
        Model { source: "meshes/epson_xp2100/pad_window_mesh.mesh"; materials: mPane
                pickable: true; property string part: "pads" }
    }

    // the first cartridge running low (level 0-15 %), or -1
    readonly property int lowInk: {
        var inks = app.inks
        for (var i = 0; i < inks.length; i++)
            if (inks[i].level >= 0 && inks[i].level <= 15) return i
        return -1
    }

    // the inside: carriage, sheet and drain; shown while see-through or while the scanner
    // unit is up (scene units, 1 mm)
    Mechanism {
        id: mech
        app: style.app
        shown: Math.max(style.app.xray, style.lidOpen)
        showFeeds: false
        xMin: -120; xMax: 80; parkX: 137
        restX: style.lidOpen > 0.5 ? -20 : 137
        railY: 50; headZ: 5
        carriageSize: Qt.vector3d(64, 24, 50)
        paperX: -20; paperY: 34; paperW: 200; paperL: 250; rearZ: -110
        // under the parked heads: the caps, then down the drain into the felt in the base
        drain: [Qt.vector3d(137, 26, 5), Qt.vector3d(137, 19, 5)]
    }

    // the four Epson 206 cartridges in the carriage, K C M Y; they ride with it
    Node {
        visible: mech.visible
        opacity: mech.opacity
        position: Qt.vector3d(mech.cx, mech.cy + 2, mech.headZ)
        Repeater3D {
            model: 4
            Node {
                id: cart
                required property int index
                readonly property var ink: style.app.inks[index]
                readonly property bool low: !!ink && ink.level >= 0 && ink.level <= 15
                readonly property color tint: style.app.inkColor(index)
                x: (index - 1.5) * 13.5
                Node {
                    scale: Qt.vector3d(100, 100, 100)
                    Model {
                        source: "meshes/epson_xp2100/cart_shell_mesh.mesh"
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
                        source: "meshes/epson_xp2100/cart_ink_mesh.mesh"
                        position: Qt.vector3d(0, 0.015, 0)
                        scale: Qt.vector3d(1, 0.36, 1)
                        materials: InkLiquid {
                            inkColor: cart.tint
                            time: style.app.time + cart.index * 1.7
                            slosh: mech.mode === "printing" ? 2.2 : 0.5
                            glow: style.app.hover === "tanks" ? 1.6 : 1.0
                            shownLevel: style.app.inkLevel(cart.index)
                        }
                    }
                    Model {
                        source: "meshes/epson_xp2100/cart_label_mesh.mesh"
                        materials: PrincipledMaterial {
                            baseColor: cart.tint
                            roughness: 0.35
                            readonly property real blink: cart.low ? 0.5 + 0.5 * Math.sin(style.app.time * 5) : 0
                            emissiveFactor: Qt.vector3d(cart.tint.r * blink, cart.tint.g * blink,
                                                        cart.tint.b * blink)
                        }
                    }
                    Model {
                        source: "meshes/epson_xp2100/cart_tab_mesh.mesh"
                        materials: PrincipledMaterial { baseColor: "#1a1c20"; roughness: 0.4 }
                    }
                }
                Node {   // "206" printed on the label
                    position: Qt.vector3d(0, 40.9, -10)
                    eulerRotation: Qt.vector3d(-90, 0, 0)
                    scale: Qt.vector3d(0.06, 0.06, 0.06)
                    Text {
                        // not `style.`: inside a Text, `style` is the Text's own style property
                        text: cartridgeCode
                        color: cart.index === 3 ? "#1b1f24" : "#f4f6f8"
                        font.family: app.colors.family; font.pixelSize: 70; font.weight: Font.Bold
                        x: -width / 2; y: -height / 2
                    }
                }
            }
        }
    }

    // printed lettering (2D text placed in the scene, 1 unit = 1 mm)
    BrandLogo { brand: "epson"; position: Qt.vector3d(95, 72, 151.8); size: 12.5; color: "#d3d7dc" }
    Label3D { text: "Wi-Fi"; position: Qt.vector3d(140, 58, 151.8); size: 4.8
              family: app.colors.family; color: "#8f969e" }
}
