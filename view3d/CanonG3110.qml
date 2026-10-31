// Canon PIXMA G series MegaTank (style "canon_g3110": G2110, G3110, G3160, G3410...): matte
// black, the tanks in two pods at the front corners (black on the left, cyan, magenta and
// yellow on the right), the output slot between them. The waste ink drains from the
// service station (right, where the carriage parks) into felt pads in the base; a
// see-through pane in the right side shows them.
// Meshes: meshes/canon_g3110/. `app` is the Printer3D root; scene units are 1 mm.
import QtQuick
import QtQuick3D

Node {
    id: style
    required property Item app

    readonly property string defaultTitle: "Canon PIXMA G3110"
    readonly property var presets: ({
        "front":  [26, 16, 1020, Qt.vector3d(0, 68, 20)],
        "tanks":  [0, 10, 760, Qt.vector3d(0, 52, 160)],
        "pads":   [70, 25, 560, Qt.vector3d(222, 32, 0)],
        "panel":  [-14, 50, 520, Qt.vector3d(178, 147, 125)],
    })
    readonly property var callouts: ({
        "pads":  { anchor: Qt.vector3d(223, 36, 0), normal: Qt.vector3d(1, 0, 0), dx: 90, dy: -80 },
        "tanks": { anchor: Qt.vector3d(-192.5, 53, 165), normal: Qt.vector3d(0, 0, 1), dx: -90, dy: -110 },
        "panel": { anchor: Qt.vector3d(165, 148, 110), normal: Qt.vector3d(0, 1, 0.35).normalized(),
                   dx: 80, dy: -70 },
    })

    // tank windows, left to right, as in make_model (canon_g3110.py TANKS / TANK_W)
    readonly property var tankOrder: ["K", "C", "M", "Y"]
    readonly property var tankX: [-1.925, 1.755, 1.925, 2.095]
    readonly property var tankWide: [2.44, 1, 1, 1]      // the black window is wider

    Node {
        id: printer
        scale: Qt.vector3d(100, 100, 100)

        ShellMaterial { id: mShell; baseColor: "#232529"; roughness: 0.62; specularAmount: 0.6; xray: app.xray }
        ShellMaterial { id: mLidShell; baseColor: "#1d1f22"; roughness: 0.7; specularAmount: 0.55; xray: app.xray }
        ShellMaterial { id: mGloss; baseColor: "#17181b"; roughness: 0.22; specularAmount: 0.95
                        clearcoatAmount: 0.4; clearcoatRoughnessAmount: 0.2; xray: app.xray }
        ShellMaterial { id: mCap; baseColor: "#2b2e33"; roughness: 0.5; specularAmount: 0.6; xray: app.xray }
        ShellMaterial { id: mHoleShell; baseColor: "#040405"; roughness: 1.0; specularAmount: 0.05; xray: app.xray }
        ShellMaterial { id: mInner; baseColor: "#1d2024"; roughness: 0.7; specularAmount: 0.3
                        seeThrough: 0.6; xray: app.xray }
        PrincipledMaterial { id: mHole; baseColor: "#040405"; roughness: 1.0; specularAmount: 0.05 }
        PrincipledMaterial { id: mPanel; baseColor: "#121315"; roughness: 0.3; specularAmount: 0.8 }
        PrincipledMaterial { id: mTray; baseColor: "#2a2d32"; roughness: 0.55; specularAmount: 0.6 }
        PrincipledMaterial { id: mButton; baseColor: "#2d3036"; roughness: 0.35 }
        PrincipledMaterial { id: mRubber; baseColor: "#121314"; roughness: 0.95 }
        PrincipledMaterial { id: mTrim; baseColor: "#24272b"; roughness: 0.25; specularAmount: 0.8 }
        PrincipledMaterial {
            id: mLcd
            baseColor: "#07090b"
            roughness: 0.08
            specularAmount: 1.0
            emissiveFactor: app.connected ? Qt.vector3d(0.10, 0.24, 0.30) : Qt.vector3d(0, 0, 0)
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
        PrincipledMaterial {
            id: mLeds
            baseColor: "#101010"
            lighting: PrincipledMaterial.NoLighting
            emissiveFactor: app.connected ? Qt.vector3d(0.25, 0.75, 2.4) : Qt.vector3d(0.03, 0.03, 0.03)
        }
        PrincipledMaterial {
            id: mWindow
            baseColor: "#aeb8c2"
            opacity: 0.12
            alphaMode: PrincipledMaterial.Blend
            roughness: 0.25
            specularAmount: 1.0
            emissiveFactor: app.hover === "tanks" ? Qt.vector3d(0.04, 0.16, 0.15) : Qt.vector3d(0, 0, 0)
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

        Model { source: "meshes/canon_g3110/body_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true
                pickable: true; property string part: "front" }
        Model { source: "meshes/canon_g3110/front_panel_mesh.mesh"; materials: mGloss; receivesShadows: true
                pickable: true; property string part: "front" }
        Model { source: "meshes/canon_g3110/scanner_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/canon_g3110/lid_mesh.mesh"; materials: mLidShell; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/canon_g3110/tank_cap_mesh.mesh"; materials: mCap; receivesShadows: true
                pickable: true; property string part: "tanks" }
        Model { source: "meshes/canon_g3110/slot_inner_mesh.mesh"; materials: mHoleShell }
        Model { source: "meshes/canon_g3110/tray_mesh.mesh"; materials: mTray; castsShadows: true; receivesShadows: true }
        Model { source: "meshes/canon_g3110/paper_support_mesh.mesh"; materials: mTray; castsShadows: true; receivesShadows: true }
        Model { source: "meshes/canon_g3110/feet_mesh.mesh"; materials: mRubber }
        Model { source: "meshes/canon_g3110/panel_mesh.mesh"; materials: mPanel; receivesShadows: true
                pickable: true; property string part: "panel" }
        Model { source: "meshes/canon_g3110/lcd_mesh.mesh"; materials: mLcd }
        Model { source: "meshes/canon_g3110/buttons_mesh.mesh"; materials: mButton; pickable: true; property string part: "panel" }
        Model { source: "meshes/canon_g3110/power_ring_mesh.mesh"; materials: mRing }
        Model { source: "meshes/canon_g3110/leds_mesh.mesh"; materials: mLeds }

        Model { source: "meshes/canon_g3110/tank_cavity_mesh.mesh"; materials: mHole }
        Model { source: "meshes/canon_g3110/tank_windows_mesh.mesh"; materials: mWindow
                pickable: true; property string part: "tanks" }
        Repeater3D {
            model: style.tankOrder
            Model {
                readonly property int ink: app.inkAt(modelData)
                source: "meshes/canon_g3110/liquid_mesh.mesh"
                position: Qt.vector3d(style.tankX[index], 0.286, 1.42)
                scale: Qt.vector3d(style.tankWide[index], 0.488, 1)
                materials: InkLiquid {
                    inkColor: app.inkColor(ink)
                    time: app.time + index * 1.7
                    glow: app.hover === "tanks" ? 1.6 : 1.0
                    shownLevel: app.inkLevel(ink)
                }
            }
        }

        // waste ink: service station, the felt pads under it, the side window
        Model { source: "meshes/canon_g3110/pad_cavity_mesh.mesh"; materials: mInner; receivesShadows: true }
        Model {
            source: "meshes/canon_g3110/pad_box_mesh.mesh"
            receivesShadows: true
            materials: PrincipledMaterial { baseColor: "#3b4148"; roughness: 0.55; specularAmount: 0.5 }
        }
        Model {
            source: "meshes/canon_g3110/pads_mesh.mesh"
            receivesShadows: true
            materials: PadFelt {
                reach: 0.85
                source: Qt.vector3d(1.70, 0.24, 0.08)
                highlight: app.hover === "pads" ? 1.0
                           : app.activity === "cleaning" ? 0.45 + 0.4 * Math.sin(app.time * 4) : 0.0
                shownFill: app.padFill
            }
        }
        Model { source: "meshes/canon_g3110/service_station_mesh.mesh"; receivesShadows: true
                materials: PrincipledMaterial { baseColor: "#272a2f"; roughness: 0.5; specularAmount: 0.4 } }
        Model { source: "meshes/canon_g3110/station_caps_mesh.mesh"; materials: mRubber }
        Model { source: "meshes/canon_g3110/pad_trim_mesh.mesh"; materials: mTrim }
        Model { source: "meshes/canon_g3110/pad_window_mesh.mesh"; materials: mPane
                pickable: true; property string part: "pads" }
    }

    // the inside, drawn while the shell is see-through (scene units, 1 mm)
    Mechanism {
        app: style.app
        xMin: -110; xMax: 90; parkX: 177
        railY: 82; headZ: 8
        carriageSize: Qt.vector3d(60, 38, 46)
        paperX: 0; paperY: 30; paperW: 210; paperL: 280; rearZ: -150
        // service station caps, then the drain down into the felt in the base
        drain: [Qt.vector3d(177, 58, 8), Qt.vector3d(177, 26, 8)]
    }

    // printed lettering (1 unit = 1 mm)
    BrandLogo { brand: "canon"; position: Qt.vector3d(0, 93, 161.2); size: 15; color: "#e8eaed" }
    Label3D { text: app.d.model || "G3110"; position: Qt.vector3d(150, 134, 160.3); size: 6
              family: app.colors.family; color: "#8f969e" }
    Repeater3D {
        model: style.tankOrder
        Label3D { text: modelData; position: Qt.vector3d(style.tankX[index] * 100, 87, 165.2)
                  size: 5; weight: Font.Bold; family: app.colors.family; color: "#8a9198" }
    }
}
