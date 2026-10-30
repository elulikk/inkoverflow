// Inside of the printer, shown while the shell turns see-through (app.xray): the print
// carriage on its rail, the paper rollers, a sheet going through while printing (a blank
// one while feeding: rollers only, no ink, the heads stay parked), and the ink a head cleaning
// flushes from the parked heads into the waste pads. Shared by every printer style; each
// style file gives the positions in scene units (1 mm).
import QtQuick
import QtQuick3D

Node {
    id: mech
    required property Item app

    property real xMin: -120                 // carriage travel while printing
    property real xMax: 80
    property real parkX: 90                  // where it parks, over the service station
    property real railY: 80                  // carriage centre height
    property real headZ: 0                   // carriage centre depth (the line it prints on)
    property vector3d carriageSize: Qt.vector3d(64, 40, 46)
    property real paperX: 0                  // sheet centre
    property real paperY: 24                 // sheet height
    property real paperW: 200
    property real paperL: 250
    property real rearZ: -130                // the sheet is hidden behind this (rear wall)
    property var drain: []                   // tube from the service station to the pads
    // how much of the inside shows (0-1): the see-through shell, or more (a style whose
    // cover opens shows it while open)
    property real shown: app.xray
    // where the carriage waits when not printing: parked, or (cartridge printers) at the
    // place where the cartridges are changed while the scanner unit is up
    property real restX: parkX
    // the four small ink feeds on top of the carriage (tank printers); a cartridge style
    // draws its cartridges instead, following `cx`
    property bool showFeeds: true

    readonly property string mode: app.activity
    readonly property real headBottom: railY - carriageSize.y / 2
    readonly property var dropPath: [Qt.vector3d(parkX, headBottom, headZ)].concat(drain)

    visible: shown > 0.02
    opacity: Math.min(1, shown * 1.4)

    property real cx: parkX                  // carriage x, follows its goal smoothly
    property real printT: 0                  // seconds since printing (or feeding) started
    property real rollA: 0                   // roller angle, degrees
    readonly property bool sheetMoves: mode === "printing" || mode === "feeding"
    property real cleanT: 0                  // seconds since cleaning started
    // carriage centre height: it shakes a little while the heads are cleaned
    readonly property real cy: railY + (mode === "cleaning" ? Math.sin(cleanT * 9) * 1.2 : 0)

    function frac(v) { return v - Math.floor(v) }
    // point at fraction f (0-1) of the way along a polyline
    function pointAt(path, f) {
        if (path.length < 2) return path.length ? path[0] : Qt.vector3d(0, 0, 0)
        var total = 0, i
        for (i = 1; i < path.length; i++) total += path[i].minus(path[i - 1]).length()
        var want = f * total
        for (i = 1; i < path.length; i++) {
            var seg = path[i].minus(path[i - 1])
            var len = seg.length()
            if (want <= len || i === path.length - 1)
                return path[i - 1].plus(seg.times(len > 0 ? Math.min(1, want / len) : 0))
            want -= len
        }
        return path[path.length - 1]
    }

    FrameAnimation {
        running: mech.visible && mech.app.active
        onTriggered: {
            var dt = Math.min(frameTime, 0.05)
            var goal = mech.mode === "cleaning" ? mech.parkX : mech.restX
            if (mech.mode === "printing") {
                mech.printT += dt
                var mid = (mech.xMin + mech.xMax) / 2, amp = (mech.xMax - mech.xMin) / 2
                goal = mid + amp * Math.sin(mech.printT * 2.6)
            } else if (mech.mode === "feeding") {
                mech.printT += dt * 1.6          // a blank sheet goes through faster
            } else {
                mech.printT = 0
            }
            if (mech.sheetMoves)
                mech.rollA = (mech.rollA + dt * (mech.mode === "feeding" ? 420 : 160)) % 360
            mech.cleanT = mech.mode === "cleaning" ? mech.cleanT + dt : 0
            var k = 1 - Math.exp(-dt * (mech.mode === "printing" ? 14 : 3))
            mech.cx += (goal - mech.cx) * k
        }
    }

    PrincipledMaterial { id: mSteel; baseColor: "#a7b0ba"; metalness: 1.0; roughness: 0.22 }
    PrincipledMaterial { id: mRoller; baseColor: "#2a2d31"; roughness: 0.85; specularAmount: 0.3 }
    PrincipledMaterial { id: mRollerMark; baseColor: "#8a939c"; roughness: 0.5 }
    PrincipledMaterial { id: mCarriage; baseColor: "#2b3036"; roughness: 0.42; specularAmount: 0.6 }
    PrincipledMaterial {
        id: mHead
        baseColor: "#101214"
        lighting: PrincipledMaterial.NoLighting
        readonly property real on: mech.mode === "printing" ? 0.6 + 0.4 * Math.sin(mech.printT * 22)
                                 : mech.mode === "cleaning" ? 0.5 + 0.5 * Math.sin(mech.cleanT * 6) : 0
        emissiveFactor: Qt.vector3d(0.24 * 3 * on, 0.84 * 3 * on, 0.78 * 3 * on)
    }
    PrincipledMaterial {
        id: mTube
        baseColor: "#c4d0db"
        opacity: 0.35
        alphaMode: PrincipledMaterial.Blend
        roughness: 0.12
        specularAmount: 1.0
    }

    // rail and the carriage riding on it
    Model {
        source: "#Cylinder"
        position: Qt.vector3d((mech.xMin + mech.parkX) / 2, mech.railY + 6,
                              mech.headZ - mech.carriageSize.z / 2 - 5)
        eulerRotation: Qt.vector3d(0, 0, 90)
        scale: Qt.vector3d(0.06, (mech.parkX - mech.xMin + mech.carriageSize.x + 40) / 100, 0.06)
        materials: mSteel
    }
    Node {
        position: Qt.vector3d(mech.cx, mech.cy, mech.headZ)
        Model {
            source: "#Cube"
            scale: mech.carriageSize.times(0.01)
            materials: mCarriage
        }
        Repeater3D {     // the four ink feeds on top, K C M Y
            model: mech.showFeeds ? 4 : 0
            Model {
                source: "#Cube"
                position: Qt.vector3d((index - 1.5) * mech.carriageSize.x * 0.2,
                                      mech.carriageSize.y / 2 + 4, 0)
                scale: Qt.vector3d(mech.carriageSize.x * 0.0014, 0.08, mech.carriageSize.z * 0.006)
                materials: PrincipledMaterial {
                    baseColor: mech.app.inkColor(index)
                    roughness: 0.25
                    specularAmount: 0.8
                }
            }
        }
        Model {          // nozzle plate, glowing while it fires
            source: "#Cube"
            y: -mech.carriageSize.y / 2 - 1.2
            scale: Qt.vector3d(mech.carriageSize.x * 0.0075, 0.025, mech.carriageSize.z * 0.0075)
            materials: mHead
        }
    }

    // the paper rollers across the paper path: the feed roller behind the heads and the
    // exit roller in front of them. A light stripe on each shows them turn.
    Repeater3D {
        model: [mech.headZ - mech.carriageSize.z / 2 - 14, mech.headZ + mech.carriageSize.z / 2 + 26]
        Node {
            position: Qt.vector3d(mech.paperX, mech.paperY + 6, modelData)
            eulerRotation: Qt.vector3d(mech.rollA, 0, 0)       // turns about its own axis (x)
            Model {
                source: "#Cylinder"
                eulerRotation: Qt.vector3d(0, 0, 90)
                scale: Qt.vector3d(0.11, (mech.paperW + 20) / 100, 0.11)
                materials: mRoller
            }
            Repeater3D {   // rubber tyres and their marks
                model: 4
                Node {
                    x: (index - 1.5) * mech.paperW * 0.28
                    Model {
                        source: "#Cylinder"
                        eulerRotation: Qt.vector3d(0, 0, 90)
                        scale: Qt.vector3d(0.13, 0.18, 0.13)
                        materials: mRoller
                    }
                    Model {
                        source: "#Cube"
                        y: 6.4
                        scale: Qt.vector3d(0.185, 0.012, 0.03)
                        materials: mRollerMark
                    }
                }
            }
        }
    }

    // printing: ink spray under the heads, and the sheet
    Repeater3D {
        model: 4
        Model {
            readonly property real f: mech.frac(mech.printT * 5 + index / 4)
            visible: mech.mode === "printing"
            source: "#Sphere"
            position: Qt.vector3d(mech.cx + (index - 1.5) * 9,
                                  mech.headBottom - f * (mech.headBottom - mech.paperY - 1),
                                  mech.headZ + (index % 2 ? 4 : -4))
            scale: Qt.vector3d(0.03, 0.05, 0.03)
            materials: PrincipledMaterial {
                baseColor: mech.app.inkColor(index)
                lighting: PrincipledMaterial.NoLighting
            }
        }
    }
    Node {
        visible: mech.sheetMoves
        position: Qt.vector3d(mech.paperX - mech.paperW / 2, mech.paperY, 0)
        eulerRotation: Qt.vector3d(-90, 0, 0)     // flat: the 2D item's y is the scene's z
        Item {
            id: sheet
            readonly property real period: 12
            readonly property real u: (mech.printT % period) / period
            readonly property real fz: mech.headZ + Math.min(1, u / 0.82) * (mech.paperL + 40)
            readonly property real back: Math.max(fz - mech.paperL, mech.rearZ)
            readonly property real printed: Math.max(0, Math.min(mech.paperL, fz - mech.headZ))
            x: 0
            y: back
            width: mech.paperW
            height: Math.max(0, fz - back)
            opacity: u > 0.9 ? (1 - u) * 10 : 1
            Rectangle { anchors.fill: parent; color: "#f4f4ef" }
            Repeater {   // a nozzle-check-like pattern, printed from the leading edge back
                model: Math.floor((mech.paperL - 30) / 10)
                Row {
                    readonly property real o: 16 + index * 10      // distance from the front edge
                    readonly property real h: index % 3 === 2 ? 2 : 6
                    visible: mech.mode === "printing"
                             && o + h <= sheet.printed && sheet.fz - o - h >= sheet.back
                    x: 15
                    y: sheet.fz - o - h - sheet.back
                    spacing: 4
                    Repeater {
                        model: 4
                        Rectangle {
                            width: (mech.paperW - 30 - 12) / 4
                            height: parent.h
                            color: mech.app.inkColor(index)
                            opacity: 0.88
                        }
                    }
                }
            }
        }
    }

    // cleaning: the drain tube and the ink drops it carries to the pads
    Repeater3D {
        model: mech.drain.length > 1 ? mech.drain.length - 1 : 0
        Model {
            readonly property vector3d a: mech.drain[index]
            readonly property vector3d b: mech.drain[index + 1]
            readonly property vector3d dv: b.minus(a)
            visible: mech.mode === "cleaning"
            source: "#Cylinder"
            position: a.plus(b).times(0.5)
            // the segments are axis-aligned: the cylinder (along Y) only needs a quarter turn
            eulerRotation: Math.abs(dv.x) > Math.abs(dv.y) && Math.abs(dv.x) > Math.abs(dv.z)
                           ? Qt.vector3d(0, 0, 90)
                           : Math.abs(dv.z) > Math.abs(dv.y) ? Qt.vector3d(90, 0, 0)
                                                             : Qt.vector3d(0, 0, 0)
            scale: Qt.vector3d(0.08, dv.length() / 100, 0.08)
            materials: mTube
        }
    }
    Repeater3D {
        model: 12
        Model {
            visible: mech.mode === "cleaning" && mech.cleanT > index * 0.18
            source: "#Sphere"
            position: mech.pointAt(mech.dropPath, mech.frac(mech.cleanT * 0.42 + index / 12))
            scale: Qt.vector3d(0.09, 0.09, 0.09)
            materials: PrincipledMaterial {
                baseColor: "#101010"
                lighting: PrincipledMaterial.NoLighting
                readonly property color c: mech.app.inkColor(index % 4)
                emissiveFactor: Qt.vector3d(0.4 + c.r * 2.4, 0.4 + c.g * 2.4, 0.4 + c.b * 2.4)
            }
        }
    }
}
