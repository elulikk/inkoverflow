// HP Ink Tank (style "hp_ink_tank_415": Ink Tank 310, 315, 319, Wireless 410, 415, 419):
// glossy black, a compact DeskJet-like body with the four tanks in a unit bolted on its
// right side (the wide black one first). The waste ink drains from the service station
// (right, where the carriage parks) back into felt pads in the base; a see-through pane
// in the right side of the main body, behind the tank unit, shows them.
// Meshes: meshes/hp_ink_tank_415/. `app` is the Printer3D root; scene units are 1 mm.
import QtQuick
import QtQuick3D

Node {
    id: style
    required property Item app

    readonly property string defaultTitle: "HP Ink Tank 415"
    readonly property var presets: ({
        "front":  [30, 16, 1150, Qt.vector3d(0, 62, 20)],
        "tanks":  [-12, 8, 560, Qt.vector3d(222, 52, 150)],
        "pads":   [100, 22, 600, Qt.vector3d(180, 33, -97)],
        "panel":  [-20, 15, 480, Qt.vector3d(-215, 120, 150)],
    })
    readonly property var callouts: ({
        "pads":  { anchor: Qt.vector3d(181, 35, -97), normal: Qt.vector3d(1, 0, 0), dx: 90, dy: -80 },
        "tanks": { anchor: Qt.vector3d(223, 52, 156), normal: Qt.vector3d(0, 0, 1), dx: 90, dy: -110 },
        "panel": { anchor: Qt.vector3d(-213, 126, 155), normal: Qt.vector3d(0, 0, 1), dx: -80, dy: -70 },
    })

    // tank windows, left to right (hp_ink_tank.py TANKS / TANK_W)
    readonly property var tankOrder: ["K", "C", "M", "Y"]
    readonly property var tankX: [1.98, 2.175, 2.33, 2.485]
    readonly property var tankWide: [1.74, 1, 1, 1]

    Node {
        id: printer
        scale: Qt.vector3d(100, 100, 100)

        ShellMaterial { id: mShell; baseColor: "#1b1c1f"; roughness: 0.34; specularAmount: 0.75
                        clearcoatAmount: 0.15; clearcoatRoughnessAmount: 0.35; xray: app.xray }
        ShellMaterial { id: mLidShell; baseColor: "#1f2124"; roughness: 0.5; specularAmount: 0.6; xray: app.xray }
        ShellMaterial { id: mMatte; baseColor: "#232529"; roughness: 0.65; specularAmount: 0.5; xray: app.xray }
        ShellMaterial { id: mHoleShell; baseColor: "#040405"; roughness: 1.0; specularAmount: 0.05; xray: app.xray }
        ShellMaterial { id: mInner; baseColor: "#1d2024"; roughness: 0.7; specularAmount: 0.3
                        seeThrough: 0.6; xray: app.xray }
        PrincipledMaterial { id: mHole; baseColor: "#040405"; roughness: 1.0; specularAmount: 0.05 }
        PrincipledMaterial { id: mTray; baseColor: "#2a2d32"; roughness: 0.55; specularAmount: 0.6 }
        PrincipledMaterial { id: mButton; baseColor: "#2d3036"; roughness: 0.35 }
        PrincipledMaterial { id: mRubber; baseColor: "#121314"; roughness: 0.95 }
        PrincipledMaterial { id: mTrim; baseColor: "#24272b"; roughness: 0.25; specularAmount: 0.8 }
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
        PrincipledMaterial {   // Wi-Fi and status lights
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

        Model { source: "meshes/hp_ink_tank_415/body_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true
                pickable: true; property string part: "front" }
        Model { source: "meshes/hp_ink_tank_415/scanner_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true
                pickable: true; property string part: "panel" }
        Model { source: "meshes/hp_ink_tank_415/lid_mesh.mesh"; materials: mLidShell; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/hp_ink_tank_415/rear_cover_mesh.mesh"; materials: mMatte; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/hp_ink_tank_415/paper_support_mesh.mesh"; materials: mTray; castsShadows: true; receivesShadows: true }
        Model { source: "meshes/hp_ink_tank_415/slot_inner_mesh.mesh"; materials: mHoleShell }
        Model { source: "meshes/hp_ink_tank_415/tray_mesh.mesh"; materials: mTray; castsShadows: true; receivesShadows: true }
        Model { source: "meshes/hp_ink_tank_415/feet_mesh.mesh"; materials: mRubber }
        Model { source: "meshes/hp_ink_tank_415/buttons_mesh.mesh"; materials: mButton; pickable: true; property string part: "panel" }
        Model { source: "meshes/hp_ink_tank_415/power_ring_mesh.mesh"; materials: mRing }
        Model { source: "meshes/hp_ink_tank_415/leds_mesh.mesh"; materials: mLeds }

        Model { source: "meshes/hp_ink_tank_415/tank_unit_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true
                pickable: true; property string part: "tanks" }
        Model { source: "meshes/hp_ink_tank_415/tank_cap_mesh.mesh"; materials: mMatte; receivesShadows: true
                pickable: true; property string part: "tanks" }
        Model { source: "meshes/hp_ink_tank_415/tank_cavity_mesh.mesh"; materials: mHole }
        Model { source: "meshes/hp_ink_tank_415/tank_windows_mesh.mesh"; materials: mWindow
                pickable: true; property string part: "tanks" }
        Repeater3D {
            model: style.tankOrder
            Model {
                readonly property int ink: app.inkAt(modelData)
                source: "meshes/hp_ink_tank_415/liquid_mesh.mesh"
                position: Qt.vector3d(style.tankX[index], 0.256, 1.32)
                scale: Qt.vector3d(style.tankWide[index], 0.538, 1)
                materials: InkLiquid {
                    inkColor: app.inkColor(ink)
                    time: app.time + index * 1.7
                    glow: app.hover === "tanks" ? 1.6 : 1.0
                    shownLevel: app.inkLevel(ink)
                }
            }
        }

        // waste ink: service station, the felt pads behind it, the side window
        Model { source: "meshes/hp_ink_tank_415/pad_cavity_mesh.mesh"; materials: mInner; receivesShadows: true }
        Model {
            source: "meshes/hp_ink_tank_415/pad_box_mesh.mesh"
            receivesShadows: true
            materials: PrincipledMaterial { baseColor: "#3b4148"; roughness: 0.55; specularAmount: 0.5 }
        }
        Model {
            source: "meshes/hp_ink_tank_415/pads_mesh.mesh"
            receivesShadows: true
            materials: PadFelt {
                reach: 0.85
                source: Qt.vector3d(1.38, 0.24, -0.95)
                highlight: app.hover === "pads" ? 1.0
                           : app.activity === "cleaning" ? 0.45 + 0.4 * Math.sin(app.time * 4) : 0.0
                shownFill: app.padFill
            }
        }
        Model { source: "meshes/hp_ink_tank_415/service_station_mesh.mesh"; receivesShadows: true
                materials: PrincipledMaterial { baseColor: "#272a2f"; roughness: 0.5; specularAmount: 0.4 } }
        Model { source: "meshes/hp_ink_tank_415/station_caps_mesh.mesh"; materials: mRubber }
        Model { source: "meshes/hp_ink_tank_415/pad_trim_mesh.mesh"; materials: mTrim }
        Model { source: "meshes/hp_ink_tank_415/pad_window_mesh.mesh"; materials: mPane
                pickable: true; property string part: "pads" }
    }

    // the inside, drawn while the shell is see-through (scene units, 1 mm)
    Mechanism {
        app: style.app
        xMin: -150; xMax: 80; parkX: 138
        railY: 85; headZ: 2
        carriageSize: Qt.vector3d(62, 38, 46)
        paperX: -30; paperY: 34; paperW: 210; paperL: 280; rearZ: -140
        // the caps under the parked heads, then the drain back to the felt behind them
        drain: [Qt.vector3d(138, 32, 2), Qt.vector3d(138, 32, -95), Qt.vector3d(138, 24, -95)]
    }

    // printed lettering (1 unit = 1 mm)
    BrandLogo { brand: "hp"; position: Qt.vector3d(-30, 126, 153.3); size: 13; color: "#c8ccd1" }
    Label3D { text: "Ink Tank"; position: Qt.vector3d(222, 91, 155.3); size: 5.5
              family: app.colors.family; color: "#8f969e" }
    Repeater3D {
        model: style.tankOrder
        Label3D { text: modelData; position: Qt.vector3d(style.tankX[index] * 100, 17, 155.3)
                  size: 5; weight: Font.Bold; family: app.colors.family; color: "#8a9198" }
    }
}
