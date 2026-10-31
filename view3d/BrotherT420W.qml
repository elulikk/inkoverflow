// Brother InkBenefit Tank (style "brother_t420w": DCP-T220, T420W, T520W, T720DW): a flat
// dark grey box, the control panel at the front left of the top, the four tanks at the
// front right under a flip cover, the paper cassette at the bottom of the front. The
// waste ink drains from the service station (right, where the carriage parks) into felt
// pads in the base; a see-through pane in the right side shows them.
// Meshes: meshes/brother_t420w/. `app` is the Printer3D root; scene units are 1 mm.
import QtQuick
import QtQuick3D

Node {
    id: style
    required property Item app

    readonly property string defaultTitle: "Brother DCP-T420W"
    readonly property var presets: ({
        "front":  [26, 16, 1000, Qt.vector3d(0, 66, 20)],
        "tanks":  [-10, 8, 520, Qt.vector3d(158, 50, 170)],
        "pads":   [70, 25, 580, Qt.vector3d(218, 33, -35)],
        "panel":  [-14, 50, 520, Qt.vector3d(-148, 146, 150)],
    })
    readonly property var callouts: ({
        "pads":  { anchor: Qt.vector3d(218, 35, -35), normal: Qt.vector3d(1, 0, 0), dx: 90, dy: -80 },
        "tanks": { anchor: Qt.vector3d(157.5, 41, 180), normal: Qt.vector3d(0, 0, 1), dx: 90, dy: -110 },
        "panel": { anchor: Qt.vector3d(-150, 147, 156), normal: Qt.vector3d(0, 1, 0.35).normalized(),
                   dx: -80, dy: -70 },
    })

    // tank windows, left to right (brother_t420w.py TANKS)
    readonly property var tankOrder: ["K", "C", "M", "Y"]
    readonly property var tankX: [1.275, 1.475, 1.675, 1.875]

    Node {
        id: printer
        scale: Qt.vector3d(100, 100, 100)

        ShellMaterial { id: mShell; baseColor: "#2b2d31"; roughness: 0.6; specularAmount: 0.55; xray: app.xray }
        ShellMaterial { id: mLidShell; baseColor: "#25272b"; roughness: 0.68; specularAmount: 0.5; xray: app.xray }
        ShellMaterial { id: mCassette; baseColor: "#3a3d42"; roughness: 0.55; specularAmount: 0.5; xray: app.xray }
        ShellMaterial { id: mGloss; baseColor: "#1b1d20"; roughness: 0.22; specularAmount: 0.95
                        clearcoatAmount: 0.4; clearcoatRoughnessAmount: 0.2; xray: app.xray }
        ShellMaterial { id: mHoleShell; baseColor: "#040405"; roughness: 1.0; specularAmount: 0.05; xray: app.xray }
        ShellMaterial { id: mInner; baseColor: "#1d2024"; roughness: 0.7; specularAmount: 0.3
                        seeThrough: 0.6; xray: app.xray }
        PrincipledMaterial { id: mHole; baseColor: "#040405"; roughness: 1.0; specularAmount: 0.05 }
        PrincipledMaterial { id: mPanel; baseColor: "#17181b"; roughness: 0.3; specularAmount: 0.8 }
        PrincipledMaterial { id: mTray; baseColor: "#34373c"; roughness: 0.55; specularAmount: 0.6 }
        PrincipledMaterial { id: mButton; baseColor: "#3a3e44"; roughness: 0.35 }
        PrincipledMaterial { id: mRubber; baseColor: "#121314"; roughness: 0.95 }
        PrincipledMaterial { id: mTrim; baseColor: "#24272b"; roughness: 0.25; specularAmount: 0.8 }
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
            emissiveFactor: app.connected ? Qt.vector3d(0.4, 2.2, 0.6) : Qt.vector3d(0.03, 0.03, 0.03)
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

        Model { source: "meshes/brother_t420w/body_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true
                pickable: true; property string part: "front" }
        Model { source: "meshes/brother_t420w/cassette_mesh.mesh"; materials: mCassette; receivesShadows: true
                pickable: true; property string part: "front" }
        Model { source: "meshes/brother_t420w/tank_cover_mesh.mesh"; materials: mGloss; receivesShadows: true
                pickable: true; property string part: "tanks" }
        Model { source: "meshes/brother_t420w/scanner_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/brother_t420w/lid_mesh.mesh"; materials: mLidShell; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/brother_t420w/slot_inner_mesh.mesh"; materials: mHoleShell }
        Model { source: "meshes/brother_t420w/tray_mesh.mesh"; materials: mTray; castsShadows: true; receivesShadows: true }
        Model { source: "meshes/brother_t420w/feet_mesh.mesh"; materials: mRubber }
        Model { source: "meshes/brother_t420w/panel_mesh.mesh"; materials: mPanel; receivesShadows: true
                pickable: true; property string part: "panel" }
        Model { source: "meshes/brother_t420w/buttons_mesh.mesh"; materials: mButton; pickable: true; property string part: "panel" }
        Model { source: "meshes/brother_t420w/power_ring_mesh.mesh"; materials: mRing }
        Model { source: "meshes/brother_t420w/leds_mesh.mesh"; materials: mLeds }

        Model { source: "meshes/brother_t420w/tank_cavity_mesh.mesh"; materials: mHole }
        Model { source: "meshes/brother_t420w/tank_windows_mesh.mesh"; materials: mWindow
                pickable: true; property string part: "tanks" }
        Repeater3D {
            model: style.tankOrder
            Model {
                readonly property int ink: app.inkAt(modelData)
                source: "meshes/brother_t420w/liquid_mesh.mesh"
                position: Qt.vector3d(style.tankX[index], 0.206, 1.565)
                scale: Qt.vector3d(1, 0.408, 1)
                materials: InkLiquid {
                    inkColor: app.inkColor(ink)
                    time: app.time + index * 1.7
                    glow: app.hover === "tanks" ? 1.6 : 1.0
                    shownLevel: app.inkLevel(ink)
                }
            }
        }

        // waste ink: service station, the felt pads under it, the side window
        Model { source: "meshes/brother_t420w/pad_cavity_mesh.mesh"; materials: mInner; receivesShadows: true }
        Model {
            source: "meshes/brother_t420w/pad_box_mesh.mesh"
            receivesShadows: true
            materials: PrincipledMaterial { baseColor: "#3b4148"; roughness: 0.55; specularAmount: 0.5 }
        }
        Model {
            source: "meshes/brother_t420w/pads_mesh.mesh"
            receivesShadows: true
            materials: PadFelt {
                reach: 0.85
                source: Qt.vector3d(1.70, 0.24, -0.27)
                highlight: app.hover === "pads" ? 1.0
                           : app.activity === "cleaning" ? 0.45 + 0.4 * Math.sin(app.time * 4) : 0.0
                shownFill: app.padFill
            }
        }
        Model { source: "meshes/brother_t420w/service_station_mesh.mesh"; receivesShadows: true
                materials: PrincipledMaterial { baseColor: "#272a2f"; roughness: 0.5; specularAmount: 0.4 } }
        Model { source: "meshes/brother_t420w/station_caps_mesh.mesh"; materials: mRubber }
        Model { source: "meshes/brother_t420w/pad_trim_mesh.mesh"; materials: mTrim }
        Model { source: "meshes/brother_t420w/pad_window_mesh.mesh"; materials: mPane
                pickable: true; property string part: "pads" }
    }

    // the inside, drawn while the shell is see-through (scene units, 1 mm)
    Mechanism {
        app: style.app
        xMin: -125; xMax: 60; parkX: 175
        railY: 100; headZ: -27
        carriageSize: Qt.vector3d(60, 38, 46)
        paperX: -35; paperY: 56; paperW: 210; paperL: 280; rearZ: -165
        // service station caps, then the drain down into the felt in the base
        drain: [Qt.vector3d(175, 58, -27), Qt.vector3d(175, 26, -27)]
    }

    // printed lettering (1 unit = 1 mm)
    BrandLogo { brand: "brother"; position: Qt.vector3d(158, 104, 182.8); size: 11; color: "#f2f4f6" }
    Label3D { text: app.d.model || "DCP-T420W"; position: Qt.vector3d(-20, 135, 180.3); size: 6
              family: app.colors.family; color: "#9aa1a8" }
    Repeater3D {
        model: style.tankOrder
        Label3D { text: modelData; position: Qt.vector3d(style.tankX[index] * 100, 14, 179.8)
                  size: 5; weight: Font.Bold; family: app.colors.family; color: "#8a9198" }
    }
}
