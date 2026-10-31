// HP Smart Tank 210 (style "hp_smart_tank_210"): white body with a dark grey top, the four
// tanks behind small windows at the front left, the output slot at the front right. The
// waste ink drains from the service station (right side, where the carriage parks) into
// felt pads in the base; a see-through window on the right side shows them.
// Meshes: meshes/hp_smart_tank_210/. `app` is the Printer3D root; scene units are 1 mm.
import QtQuick
import QtQuick3D

Node {
    id: style
    required property Item app

    readonly property string defaultTitle: "HP Smart Tank 210"
    readonly property var presets: ({
        "front":  [28, 16, 1060, Qt.vector3d(0, 66, 20)],
        "tanks":  [-16, 8, 470, Qt.vector3d(-162, 34, 150)],
        "pads":   [70, 27, 560, Qt.vector3d(190, 28, 10)],
        "panel":  [-16, 50, 600, Qt.vector3d(-175, 130, 105)],
    })
    readonly property var callouts: ({
        "pads":  { anchor: Qt.vector3d(219, 40, 20), normal: Qt.vector3d(1, 0, 0), dx: 90, dy: -80 },
        "tanks": { anchor: Qt.vector3d(-162, 34, 182), normal: Qt.vector3d(0, 0, 1), dx: -90, dy: -110 },
        "panel": { anchor: Qt.vector3d(-190, 134, 90), normal: Qt.vector3d(0, 1, 0.35).normalized(),
                   dx: -80, dy: -70 },
    })

    // tank window centres (dm, from make_model.py H_TANKS)
    readonly property var tankX: [-1.99, -1.747, -1.504, -1.261]

    Node {
        id: printer
        scale: Qt.vector3d(100, 100, 100)

        ShellMaterial { id: mBody; baseColor: "#eef0f2"; roughness: 0.42; specularAmount: 0.45; xray: app.xray }
        ShellMaterial { id: mTop; baseColor: "#33373c"; roughness: 0.55; specularAmount: 0.45; xray: app.xray }
        ShellMaterial { id: mLid; baseColor: "#4f545a"; roughness: 0.62; specularAmount: 0.4; xray: app.xray }
        ShellMaterial { id: mPlate; baseColor: "#eceef0"; roughness: 0.3; specularAmount: 0.6; xray: app.xray }
        ShellMaterial { id: mTabs; baseColor: "#c9cdd1"; roughness: 0.4; xray: app.xray }
        ShellMaterial { id: mNotch; baseColor: "#a9aeb3"; roughness: 0.5; xray: app.xray }
        ShellMaterial { id: mLogo; baseColor: "#8c9298"; roughness: 0.32; specularAmount: 0.7; xray: app.xray }
        PrincipledMaterial { id: mHole; baseColor: "#0c0d0f"; roughness: 1.0; specularAmount: 0.05 }
        ShellMaterial { id: mHoleShell; baseColor: "#0c0d0f"; roughness: 1.0; specularAmount: 0.05; xray: app.xray }
        ShellMaterial { id: mInner; baseColor: "#646a71"; roughness: 0.6; specularAmount: 0.35; xray: app.xray }
        PrincipledMaterial { id: mTray; baseColor: "#c4c8cc"; roughness: 0.4; specularAmount: 0.5 }
        PrincipledMaterial { id: mButton; baseColor: "#41464c"; roughness: 0.35 }
        PrincipledMaterial { id: mRubber; baseColor: "#0a0a0a"; roughness: 0.95 }
        PrincipledMaterial { id: mTrim; baseColor: "#24272b"; roughness: 0.25; specularAmount: 0.8 }
        PrincipledMaterial { id: mBezel; baseColor: "#1b1d20"; roughness: 0.2; specularAmount: 0.8 }
        PrincipledMaterial {
            id: mLcd
            baseColor: "#07090b"
            roughness: 0.08
            specularAmount: 1.0
            clearcoatAmount: 0.8
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
        PrincipledMaterial {   // the wireless light
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

        Model { source: "meshes/hp_smart_tank_210/body_mesh.mesh"; materials: mBody; castsShadows: app.xray < 0.5; receivesShadows: true
                pickable: true; property string part: "front" }
        Model { source: "meshes/hp_smart_tank_210/panel_mesh.mesh"; materials: mTop; castsShadows: app.xray < 0.5; receivesShadows: true
                pickable: true; property string part: "panel" }
        Model { source: "meshes/hp_smart_tank_210/lid_mesh.mesh"; materials: mLid; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/hp_smart_tank_210/rear_cover_mesh.mesh"; materials: mTop; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/hp_smart_tank_210/slot_inner_mesh.mesh"; materials: mHoleShell }
        Model { source: "meshes/hp_smart_tank_210/slot_panel_mesh.mesh"; materials: mInner; receivesShadows: true }
        Model { source: "meshes/hp_smart_tank_210/tray_mesh.mesh"; materials: mTray; castsShadows: true; receivesShadows: true }
        Model { source: "meshes/hp_smart_tank_210/logo_mesh.mesh"; materials: mLogo; receivesShadows: true }
        Model { source: "meshes/hp_smart_tank_210/label_plate_mesh.mesh"; materials: mPlate; receivesShadows: true }
        Model { source: "meshes/hp_smart_tank_210/tank_tabs_mesh.mesh"; materials: mTabs; receivesShadows: true }
        Model { source: "meshes/hp_smart_tank_210/feet_mesh.mesh"; materials: mRubber }
        Model { source: "meshes/hp_smart_tank_210/buttons_mesh.mesh"; materials: mButton; pickable: true; property string part: "panel" }
        Model { source: "meshes/hp_smart_tank_210/power_ring_mesh.mesh"; materials: mRing }
        Model { source: "meshes/hp_smart_tank_210/leds_mesh.mesh"; materials: mLeds }

        Model { source: "meshes/hp_smart_tank_210/tank_cavity_mesh.mesh"; materials: mHole }
        Model { source: "meshes/hp_smart_tank_210/tank_windows_mesh.mesh"; materials: mWindow
                pickable: true; property string part: "tanks" }
        Repeater3D {
            model: 4
            Model {
                source: "meshes/hp_smart_tank_210/liquid_mesh.mesh"
                position: Qt.vector3d(style.tankX[index], 0.176, 1.578)
                scale: Qt.vector3d(1, 0.288, 1)
                materials: InkLiquid {
                    inkColor: app.inkColor(index)
                    time: app.time + index * 1.7
                    glow: app.hover === "tanks" ? 1.6 : 1.0
                    shownLevel: app.inkLevel(index)
                }
            }
        }

        // waste ink: service station, the felt pads under it, the side window
        Model { source: "meshes/hp_smart_tank_210/pad_cavity_mesh.mesh"; materials: mInner; receivesShadows: true }
        Model {
            source: "meshes/hp_smart_tank_210/pad_box_mesh.mesh"
            receivesShadows: true
            materials: PrincipledMaterial { baseColor: "#3b4148"; roughness: 0.55; specularAmount: 0.5 }
        }
        Model {
            source: "meshes/hp_smart_tank_210/pads_mesh.mesh"
            receivesShadows: true
            materials: PadFelt {
                reach: 0.85
                source: Qt.vector3d(1.70, 0.24, 0.25)
                highlight: app.hover === "pads" ? 1.0
                           : app.activity === "cleaning" ? 0.45 + 0.4 * Math.sin(app.time * 4) : 0.0
                shownFill: app.padFill
            }
        }
        Model { source: "meshes/hp_smart_tank_210/service_station_mesh.mesh"; receivesShadows: true
                materials: PrincipledMaterial { baseColor: "#272a2f"; roughness: 0.5; specularAmount: 0.4 } }
        Model { source: "meshes/hp_smart_tank_210/station_caps_mesh.mesh"; materials: mRubber }
        Model { source: "meshes/hp_smart_tank_210/pad_trim_mesh.mesh"; materials: mTrim }
        Model { source: "meshes/hp_smart_tank_210/pad_window_mesh.mesh"; materials: mPane
                pickable: true; property string part: "pads" }
    }

    // the inside, drawn while the shell is see-through (scene units, 1 mm)
    Mechanism {
        app: style.app
        xMin: -95; xMax: 105; parkX: 172
        railY: 96; headZ: 25
        carriageSize: Qt.vector3d(66, 40, 50)
        paperX: 13; paperY: 22; paperW: 210; paperL: 280; rearZ: -168
        // service station caps, then the drain down into the felt in the base
        drain: [Qt.vector3d(172, 58, 25), Qt.vector3d(172, 26, 25)]
    }

    // printed lettering (2D text placed in the scene, 1 unit = 1 mm)
    // round logo: the disc is a mesh, the letters are text
    BrandLogo { brand: "hp"; position: Qt.vector3d(7.3, 110, 181.9); size: 21; color: "#f4f6f8" }
    Label3D { text: "HP Smart Tank 210"; position: Qt.vector3d(171.5, 21.5, 182.0); size: 7.2
              family: app.colors.family; color: "#2f3439" }
    Repeater3D {
        model: ["K", "C", "M", "Y"]
        Label3D { text: modelData; position: Qt.vector3d(style.tankX[index] * 100, 55.5, 182.0)
                  size: 6.2; weight: Font.Bold; family: app.colors.family; color: "#5d646b" }
    }
}
