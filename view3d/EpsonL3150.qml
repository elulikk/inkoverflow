// Epson L3150/L3250 family (style "epson_l3150"): tank unit on the right, waste-ink pads
// behind a see-through door at the back, on the tank side. Meshes: meshes/epson_l3150/.
// `app` is the Printer3D root (data, time, hover, colours); scene units are 1 mm.
import QtQuick
import QtQuick3D

Node {
    id: style
    required property Item app

    readonly property string defaultTitle: "Impresora Epson"
    // the tanks seen from the front, left to right (the printer's labels: BK Y M C)
    readonly property var tankOrder: ["K", "Y", "M", "C"]
    // camera presets: yaw, pitch, distance, target
    readonly property var presets: ({
        "front":  [28, 16, 950, Qt.vector3d(0, 62, 25)],
        "tanks":  [24, 9, 470, Qt.vector3d(150, 36, 120)],
        "pads":   [150, 13, 470, Qt.vector3d(68, 30, -120)],
        "panel":  [-12, 46, 480, Qt.vector3d(-120, 145, 100)],
    })
    // where the floating labels point (and which way that spot faces)
    readonly property var callouts: ({
        "pads":  { anchor: Qt.vector3d(68, 36, -139), normal: Qt.vector3d(0, 0, -1), dx: -90, dy: -70 },
        "tanks": { anchor: Qt.vector3d(154, 52, 145), normal: Qt.vector3d(0.25, 0, 1).normalized(),
                   dx: 90, dy: -95 },
        "panel": { anchor: Qt.vector3d(-162, 153, 127), normal: Qt.vector3d(0, 1, 0.4).normalized(),
                   dx: -80, dy: -70 },
    })

    // ---- the printer (meshes in decimetres -> scene units of 1 mm) -------------
    Node {
        id: printer
        scale: Qt.vector3d(100, 100, 100)

        PrincipledMaterial { id: mHole; baseColor: "#040405"; roughness: 1.0; specularAmount: 0.05 }
        // the shell over the mechanism: see-through while the printer works (app.xray)
        PrincipledMaterial { id: mShell; baseColor: "#25282d"; roughness: 0.62; specularAmount: 0.8
                             opacity: 1 - 0.74 * app.xray
                             alphaMode: app.xray > 0.01 ? PrincipledMaterial.Blend : PrincipledMaterial.Default }
        PrincipledMaterial { id: mLidShell; baseColor: "#202327"; roughness: 0.8; specularAmount: 0.6
                             opacity: 1 - 0.74 * app.xray
                             alphaMode: app.xray > 0.01 ? PrincipledMaterial.Blend : PrincipledMaterial.Default }
        PrincipledMaterial { id: mGloss; baseColor: "#1c1e22"; roughness: 0.3; specularAmount: 0.9
                             clearcoatAmount: 0.35; clearcoatRoughnessAmount: 0.25
                             opacity: 1 - 0.74 * app.xray
                             alphaMode: app.xray > 0.01 ? PrincipledMaterial.Blend : PrincipledMaterial.Default }
        PrincipledMaterial { id: mHoleShell; baseColor: "#040405"; roughness: 1.0; specularAmount: 0.05
                             opacity: 1 - 0.74 * app.xray
                             alphaMode: app.xray > 0.01 ? PrincipledMaterial.Blend : PrincipledMaterial.Default }
        PrincipledMaterial { id: mTray; baseColor: "#2d3136"; roughness: 0.55; specularAmount: 0.6 }
        PrincipledMaterial { id: mButton; baseColor: "#2c2f35"; roughness: 0.35 }
        PrincipledMaterial { id: mRubber; baseColor: "#161718"; roughness: 0.95 }
        PrincipledMaterial { id: mScrew; baseColor: "#9aa3ad"; metalness: 1.0; roughness: 0.3 }
        PrincipledMaterial {
            id: mRing
            baseColor: "#101010"
            lighting: PrincipledMaterial.NoLighting
            readonly property real pulse: app.d.busy ? 0.55 + 0.45 * Math.sin(app.time * 5) : 1
            emissiveFactor: app.connected
                            ? (app.d.busy ? Qt.vector3d(2.6 * pulse, 1.6 * pulse, 0.2)
                                          : Qt.vector3d(0.35, 2.6, 0.9))
                            : Qt.vector3d(0.06, 0.07, 0.07)
        }
        PrincipledMaterial {
            id: mLeds
            baseColor: "#101010"
            lighting: PrincipledMaterial.NoLighting
            emissiveFactor: app.connected ? Qt.vector3d(0.15, 0.6, 0.55) : Qt.vector3d(0.03, 0.03, 0.03)
        }
        PrincipledMaterial {
            id: mWindow
            baseColor: "#aeb8c2"
            opacity: 0.13
            alphaMode: PrincipledMaterial.Blend
            roughness: 0.28
            specularAmount: 1.0
            emissiveFactor: app.hover === "tanks" ? Qt.vector3d(0.04, 0.16, 0.15) : Qt.vector3d(0, 0, 0)
        }
        PrincipledMaterial {
            id: mDoor
            baseColor: "#5a6b7a"
            opacity: 0.26
            alphaMode: PrincipledMaterial.Blend
            roughness: 0.12
            specularAmount: 1.0
            emissiveFactor: app.hover === "pads" ? Qt.vector3d(0.04, 0.18, 0.17) : Qt.vector3d(0, 0, 0)
        }

        Model { source: "meshes/epson_l3150/body_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/epson_l3150/scanner_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/epson_l3150/lid_mesh.mesh"; materials: mLidShell; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/epson_l3150/front_panel_mesh.mesh"; materials: mGloss; receivesShadows: true
                pickable: true; property string part: "front" }
        Model { source: "meshes/epson_l3150/slot_inner_mesh.mesh"; materials: mHoleShell }
        Model { source: "meshes/epson_l3150/tray_mesh.mesh"; materials: mTray; castsShadows: true; receivesShadows: true }
        Model { source: "meshes/epson_l3150/paper_support_mesh.mesh"; materials: mTray; castsShadows: true; receivesShadows: true }
        Model { source: "meshes/epson_l3150/feet_mesh.mesh"; materials: mRubber }
        Model { source: "meshes/epson_l3150/buttons_mesh.mesh"; materials: mButton; pickable: true; property string part: "panel" }
        Model { source: "meshes/epson_l3150/power_ring_mesh.mesh"; materials: mRing }
        Model { source: "meshes/epson_l3150/leds_mesh.mesh"; materials: mLeds }

        Model { source: "meshes/epson_l3150/tank_unit_mesh.mesh"; materials: mShell; castsShadows: app.xray < 0.5; receivesShadows: true
                pickable: true; property string part: "tanks" }
        Model { source: "meshes/epson_l3150/tank_cap_mesh.mesh"; materials: mLidShell; castsShadows: app.xray < 0.5; receivesShadows: true }
        Model { source: "meshes/epson_l3150/tank_cavity_mesh.mesh"; materials: mHole }
        Model { source: "meshes/epson_l3150/tank_windows_mesh.mesh"; materials: mWindow; pickable: true; property string part: "tanks" }

        Repeater3D {     // seen from the front, left to right: K Y M C (style.tankOrder)
            model: style.tankOrder
            Model {
                readonly property int ink: app.inkAt(modelData)
                source: "meshes/epson_l3150/liquid_mesh.mesh"
                position: Qt.vector3d(1.3095 + index * 0.152, 0.126, 1.215)
                scale: Qt.vector3d(1, 0.408, 1)
                materials: InkLiquid {
                    inkColor: app.inkColor(ink)
                    time: app.time + index * 1.7
                    glow: app.hover === "tanks" ? 1.6 : 1.0
                    shownLevel: app.inkLevel(ink)
                }
            }
        }

        Model { source: "meshes/epson_l3150/pad_cavity_mesh.mesh"; materials: mHoleShell }
        Model {   // the plastic box the pads stand in
            source: "meshes/epson_l3150/pad_box_mesh.mesh"
            receivesShadows: true
            materials: PrincipledMaterial { baseColor: "#3b4148"; roughness: 0.55; specularAmount: 0.5 }
        }
        Model {
            source: "meshes/epson_l3150/pads_mesh.mesh"
            receivesShadows: true
            materials: PadFelt {
                reach: 0.58
                source: Qt.vector3d(0.68, 0.52, -1.08)
                highlight: app.hover === "pads" ? 1.0
                           : app.activity === "cleaning" ? 0.45 + 0.4 * Math.sin(app.time * 4) : 0.0
                shownFill: app.padFill
            }
        }
        Model { source: "meshes/epson_l3150/pad_door_mesh.mesh"; materials: mDoor; pickable: true; property string part: "pads" }
        Model { source: "meshes/epson_l3150/pad_screw_mesh.mesh"; materials: mScrew }
    }

    // the inside, drawn while the shell is see-through (scene units, 1 mm)
    Mechanism {
        app: style.app
        xMin: -140; xMax: 55; parkX: 82
        railY: 80; headZ: 10
        carriageSize: Qt.vector3d(62, 38, 46)
        paperX: -25; paperY: 24; paperW: 200; paperL: 250; rearZ: -128
        // service station under the parked heads, then back to the pads behind the door
        drain: [Qt.vector3d(82, 34, 10), Qt.vector3d(82, 34, -104), Qt.vector3d(68, 34, -104),
                Qt.vector3d(68, 22, -104)]
    }

    // printed lettering (2D text placed in the scene, 1 unit = 1 mm)
    Node {
        position: Qt.vector3d(-25, 80, 142.2)
        scale: Qt.vector3d(0.1, 0.1, 0.1)
        Text {
            text: "EPSON"
            color: "#9fa5ad"
            font.family: "Arial"; font.pixelSize: 150; font.weight: Font.Bold
            font.letterSpacing: 6
            x: -width / 2; y: -height / 2
        }
    }
    Node {
        position: Qt.vector3d(153.75, 105, 144.2)
        scale: Qt.vector3d(0.1, 0.1, 0.1)
        Text {
            text: app.d.model || "L3150"
            color: "#8f969e"
            font.family: app.colors.family; font.pixelSize: 90; font.weight: Font.DemiBold
            x: -width / 2; y: -height / 2
        }
    }
    Repeater3D {
        model: style.tankOrder
        Node {
            position: Qt.vector3d(130.95 + index * 15.2, 7.0, 144.2)
            scale: Qt.vector3d(0.1, 0.1, 0.1)
            Text {
                text: modelData
                color: "#7d858e"
                font.family: app.colors.family; font.pixelSize: 55; font.weight: Font.Bold
                x: -width / 2; y: -height / 2
            }
        }
    }
}
