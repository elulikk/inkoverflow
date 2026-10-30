// Vista 3D de InkOverflow: the printer in a small photo studio, with a game-style HUD.
// Data comes from `bridge` (printer3d.Bridge); nothing here talks to the printer.
// Info and buttons either stay on screen (bridge.pinned) or open as a card while the
// cursor is on that part of the printer (printer, tanks, pads). While the printer prints
// or cleans, its shell turns see-through and Mechanism.qml shows what happens inside.
// Vista 2D (bridge.mode2d): the 3D scene is not created at all; Printer2D.qml draws the
// printer as flat sprites instead, under the same HUD, callouts and cards.
// Right-click on the FPS counter caps the view at 30 frames per second (bridge.fps30).
import QtQuick
import QtQuick.Shapes
import QtQuick3D
import QtQuick3D.Helpers

Item {
    id: root
    width: 1100
    height: 700

    // ---- data -----------------------------------------------------------------------
    readonly property bool hasBridge: typeof bridge !== "undefined" && bridge !== null
    readonly property var d: hasBridge ? bridge.data : ({})
    readonly property bool dark: d.dark === undefined ? true : d.dark
    readonly property bool connected: !!d.connected
    readonly property var inks: d.inks || []
    readonly property var pads: d.pads || []
    readonly property real worst: d.worst === undefined ? -1 : d.worst
    readonly property real padFill: worst < 0 ? 0.0 : Math.min(worst, 105) / 100
    readonly property var actions: d.actions || ({})
    // what the printer is doing: "", "printing", "feeding", "cleaning" or "error"
    readonly property string activity: d.activity || ""
    readonly property real progress: d.progress === undefined ? -1 : d.progress
    // info always on screen, or only while the cursor is on that part
    readonly property bool pinned: hasBridge ? bridge.pinned : true
    // printer style: which model is drawn (default the Epson L3150 family)
    readonly property var styleFiles: ({ "epson_l3150": "EpsonL3150.qml",
                                         "hp_smart_tank_580": "HpSmartTank580.qml",
                                         "epson_xp2100": "EpsonXP2100.qml" })
    readonly property string style: styleFiles[d.style] !== undefined ? d.style : "epson_l3150"
    // 2D sprites instead of the 3D scene, and the 30 FPS cap (both remembered by the bridge)
    readonly property bool flat: hasBridge ? bridge.mode2d : false
    readonly property bool cap30: hasBridge ? bridge.fps30 : false
    readonly property var view3d: scene3d.item            // the View3D, null in 2D
    // the loaded style: the 3D style file, or the 2D sprites (same properties)
    readonly property var model3d: flat ? sprites.item : view3d ? view3d.printer : null
    property alias colors: pal                            // for the style files
    // where the ink is: tanks (default) or cartridges (the style says so, with their code)
    readonly property bool cartridges: !!(model3d && model3d.cartridges)
    readonly property string inkPart: model3d && model3d.inkPart ? model3d.inkPart : "Tanques"
    readonly property string cartridgeCode: model3d && model3d.cartridgeCode ? model3d.cartridgeCode : ""
    // cartridges at 15 % or less, as "Negro (206), Cian (206)"; "" when none
    readonly property string lowCartridges: {
        if (!cartridges) return ""
        var out = []
        for (var i = 0; i < inks.length; i++)
            if (inks[i].level >= 0 && inks[i].level <= 15)
                out.push(inks[i].name + (cartridgeCode ? " (" + cartridgeCode + ")" : ""))
        return out.join(", ")
    }

    // see-through shell (0-1): while printing or cleaning, or asked for with "Interior"
    property bool xrayManual: false
    property real xray: activity !== "" || xrayManual ? 1 : 0
    Behavior on xray { NumberAnimation { duration: 900; easing.type: Easing.InOutCubic } }
    // turn to where the action is: the sheet in front, or the heads draining into the pads
    onActivityChanged: {
        if (activity === "printing" || activity === "feeding") preset("front")
        else if (activity === "cleaning") preset("pads")
    }

    // 3D: the scene loads its style file itself (scene3d); 2D: the sprites draw every style
    function loadScene() {
        if (flat) {
            if (!sprites.item) sprites.setSource("Printer2D.qml", { "app": root })
        } else {
            sprites.source = ""
            if (view3d) view3d.loadPrinter()
        }
    }
    // called once a printer is drawn (3D or 2D)
    function styleReady() {
        preset("front")
        // start on the new printer at once instead of flying over from the old one
        yaw = goalYaw; pitch = goalPitch; dist = goalDist; target = goalTarget
        zoom = goalZoom; center = goalCenter
        idle = 10
    }
    onStyleChanged: if (!flat && view3d) view3d.loadPrinter()
    onFlatChanged: loadScene()
    Component.onCompleted: loadScene()

    function sevColor(pct) {
        return pct < 0 ? pal.muted : pct >= 90 ? pal.bad : pct >= 70 ? pal.warn : pal.ok
    }
    function inkLevel(i) {
        var ink = inks[i]
        return !ink || ink.level < 0 ? 0.72 : Math.max(0.03, ink.level / 100)
    }
    function inkColor(i) {
        var ink = inks[i]
        return ink ? ink.color : ["#1d1d1f", "#00a3e0", "#d6007e", "#f5d000"][i]
    }
    // index in `inks` of the colour with this letter (K, C, M, Y), so a style can place
    // its tanks in the printer's own order whatever order the reading lists them in
    function inkAt(letter) {
        var starts = { "K": ["Negro", "Black"], "C": ["Cian", "Cyan"],
                       "M": ["Magenta"], "Y": ["Amarillo", "Yellow"] }[letter] || []
        for (var i = 0; i < inks.length; i++)
            for (var j = 0; j < starts.length; j++)
                if (String(inks[i].name).indexOf(starts[j]) === 0) return i
        return Math.max(0, "KCMY".indexOf(letter))
    }
    function canDo(name) { return actions[name] === "" }
    function act(name) { if (hasBridge && canDo(name)) bridge.action(name) }
    // why the actions are off, each reason once
    function actionNotes(names) {
        var out = []
        for (var i = 0; i < names.length; i++) {
            var why = actions[names[i]]
            if (why && out.indexOf(why) < 0) out.push(why)
        }
        return out.join("\n")
    }

    QtObject {
        id: pal
        readonly property color accent: "#3dd6c6"
        readonly property color ok: "#3ecf8e"
        readonly property color warn: "#f2a93b"
        readonly property color bad: "#ff5d5d"
        readonly property color bg0: root.dark ? "#0a0e13" : "#f4f6f9"
        readonly property color bg1: root.dark ? "#18212b" : "#d9dfe6"
        readonly property color panel: root.dark ? Qt.rgba(0.07, 0.10, 0.13, 0.86)
                                                 : Qt.rgba(1, 1, 1, 0.88)
        readonly property color line: root.dark ? Qt.rgba(1, 1, 1, 0.09) : Qt.rgba(0, 0, 0, 0.10)
        readonly property color text: root.dark ? "#e8eef4" : "#1b1f24"
        readonly property color muted: root.dark ? "#8796a6" : "#5f6670"
        readonly property color btn: root.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.05)
        readonly property color btnHover: root.dark ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(0, 0, 0, 0.09)
        readonly property color floor: root.dark ? "#0d1115" : "#9aa3ad"
        readonly property string family: "Segoe UI"
    }

    // ---- camera state: goals set by the user, current values follow smoothly --------
    property real goalYaw: 28
    property real goalPitch: 16
    property real goalDist: 950
    property vector3d goalTarget: Qt.vector3d(0, 62, 25)
    property real yaw: goalYaw
    property real pitch: goalPitch
    property real dist: goalDist
    property vector3d target: goalTarget
    // 2D camera: zoom and the sprite point in the middle of the view
    property real goalZoom: 1
    property point goalCenter: Qt.point(340, 200)
    property real zoom: goalZoom
    property point center: goalCenter
    property bool spin: true
    property real idle: 10          // seconds since the user last moved the camera
    property real tick: 0           // bumped every frame: callouts follow the camera
    property real time: 0
    property string hover: ""       // part under the cursor
    property string shot: "front"
    property bool active: true      // false while the page is hidden: no frames, no GPU

    function preset(name) {
        shot = name
        if (name === "spin") { spin = !spin; idle = 10; return }
        var p = model3d ? model3d.presets[name] : undefined
        if (!p) return
        idle = name === "front" ? 6 : -30   // a close-up stays put a while
        if (flat) {                         // 2D: [zoom, x, y]
            goalZoom = p[0]; goalCenter = Qt.point(p[1], p[2])
            return
        }
        // turn the short way round
        var y = p[0]
        while (y - goalYaw > 180) y -= 360
        while (y - goalYaw < -180) y += 360
        goalYaw = y; goalPitch = p[1]; goalDist = p[2]; goalTarget = p[3]
    }

    Connections {
        target: root.hasBridge ? bridge : null
        function onCameraRequested(name) { root.preset(name) }
    }

    // ---- frame rate: below bridge.minFps for bridge.fpsSeconds in a row, 3D turns off ---
    property real fps: 0
    property real fpsTime: 0
    property int fpsFrames: 0
    property real warmup: 0         // seconds since the view became active
    property int slowSeconds: 0
    onActiveChanged: { warmup = 0; slowSeconds = 0; fpsTime = 0; fpsFrames = 0 }

    function countFrame(ft) {
        if (ft > 0.25) {            // a stall (window hidden, dialog, shader build): not a rate
            fpsTime = 0; fpsFrames = 0
            return
        }
        warmup += ft
        fpsTime += ft
        fpsFrames += 1
        if (fpsTime < 1.0) return
        fps = fpsFrames / fpsTime
        fpsTime = 0; fpsFrames = 0
        var limit = hasBridge ? bridge.minFps : 20
        if (warmup > 4 && fps < limit) slowSeconds += 1
        else slowSeconds = 0
        // 2D is what a slow computer falls back to: it is never turned off
        if (hasBridge && bridge.fpsGuard && !flat && slowSeconds >= bridge.fpsSeconds) {
            slowSeconds = -100000   // once
            bridge.reportLowFps(fps)
        }
    }

    // one step of the view: the clock, the camera following its goals, the callouts
    function step(ft) {
        countFrame(ft)
        var dt = Math.min(ft, 0.05)
        time += dt
        idle += dt
        if (openPart !== "") idle = Math.min(idle, 0)   // card open: hold still
        var k = 1 - Math.exp(-dt * 7)
        if (flat) {
            zoom += (goalZoom - zoom) * k
            center = Qt.point(center.x + (goalCenter.x - center.x) * k,
                              center.y + (goalCenter.y - center.y) * k)
        } else {
            if (spin && idle > 4)
                goalYaw += dt * 7 * Math.min(1, (idle - 4) / 2)
            yaw += (goalYaw - yaw) * k
            pitch += (goalPitch - pitch) * k
            dist += (goalDist - dist) * k
            target = target.plus(goalTarget.minus(target).times(k))
        }
        tick += 1
    }
    // 30 FPS cap: a step only every 1/30 s; ticks in between change nothing, so nothing is
    // drawn for them. The leftover carries over, so the average holds at 30 on any screen.
    property real sinceStep: 0
    property real stepBudget: 0
    onCap30Changed: { stepBudget = 0; fpsTime = 0; fpsFrames = 0 }
    FrameAnimation {
        running: root.active
        onTriggered: {
            root.sinceStep += frameTime
            if (root.cap30) {
                root.stepBudget += frameTime
                if (root.stepBudget < 1 / 30 - 0.001) return
                root.stepBudget = Math.min(1 / 30, root.stepBudget - 1 / 30)
            }
            var ft = root.sinceStep
            root.sinceStep = 0
            root.step(ft)
        }
    }

    // ---- backdrop ---------------------------------------------------------------------
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: pal.bg1 }
            GradientStop { position: 1.0; color: pal.bg0 }
        }
    }
    // soft spotlight behind the printer
    Rectangle {
        width: Math.max(parent.width, parent.height) * 1.1
        height: width
        radius: width / 2
        x: (parent.width - width) / 2
        y: parent.height * 0.52 - height / 2
        opacity: root.dark ? 0.55 : 0.6
        gradient: Gradient {
            orientation: Gradient.Vertical
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 0.5; color: root.dark ? "#22303d" : "#ffffff" }
            GradientStop { position: 1.0; color: "transparent" }
        }
    }

    // ---- the 2D sprites (Printer2D.qml), loaded by loadScene() while flat -----------------
    Loader {
        id: sprites
        anchors.fill: parent
    }

    // ---- the 3D scene, only created while not flat -------------------------------------------
    Loader {
        id: scene3d
        anchors.fill: parent
        active: !root.flat
        sourceComponent: scene3dComponent
    }
    Component {
        id: scene3dComponent
    View3D {
        id: view
        camera: cam
        readonly property var printer: printerLoader.item
        function loadPrinter() {
            if (printerLoader.item && printerLoader.styleName === root.style) return
            printerLoader.styleName = root.style
            printerLoader.setSource(root.styleFiles[root.style], { "app": root })
        }
        Component.onCompleted: loadPrinter()

        environment: ExtendedSceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.VeryHigh
            specularAAEnabled: true
            lightProbe: Texture { source: "studio.hdr" }
            probeExposure: 0.42
            aoEnabled: true
            aoStrength: 55
            aoDistance: 18
            aoSoftness: 45
            aoSampleRate: 3
            tonemapMode: SceneEnvironment.TonemapModeFilmic
            exposure: 1.0
            glowEnabled: true
            glowStrength: 1.1
            glowIntensity: 0.45
            glowBloom: 0.0
            glowHDRMinimumValue: 1.6
            glowBlendMode: ExtendedSceneEnvironment.GlowBlendMode.Additive
            glowLevel: ExtendedSceneEnvironment.GlowLevel.One | ExtendedSceneEnvironment.GlowLevel.Two
                       | ExtendedSceneEnvironment.GlowLevel.Three
        }

        Node {
            id: rig
            position: root.target
            eulerRotation: Qt.vector3d(-root.pitch, root.yaw, 0)
            PerspectiveCamera {
                id: cam
                z: root.dist
                fieldOfView: 30
                clipNear: 10
                clipFar: 20000
            }
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(-58, -35, 0)
            brightness: 0.9
            color: "#fff6ec"
            castsShadow: true
            shadowMapQuality: Light.ShadowMapQualityVeryHigh
            shadowFactor: 55
            shadowBias: 2
            shadowMapFar: 4000
            pcfFactor: 6
            softShadowQuality: Light.PCF16
        }
        DirectionalLight {
            eulerRotation: Qt.vector3d(-20, 150, 0)
            brightness: 0.4
            color: "#bcd8ff"
        }

        // turntable
        Model {
            source: "#Cylinder"
            y: -3
            scale: Qt.vector3d(6.4, 0.06, 6.4)
            receivesShadows: true
            materials: PrincipledMaterial {
                baseColor: pal.floor
                roughness: 0.32
                metalness: 0.0
                specularAmount: 0.6
            }
        }
        Model {
            source: "#Cylinder"
            y: -4.2
            scale: Qt.vector3d(6.48, 0.03, 6.48)
            materials: PrincipledMaterial {
                baseColor: "black"
                emissiveFactor: Qt.vector3d(0.24 * 3.2, 0.84 * 3.2, 0.78 * 3.2)
                lighting: PrincipledMaterial.NoLighting
            }
        }

        // ---- the printer: one QML file per style (EpsonL3150.qml, HpSmartTank580.qml, EpsonXP2100.qml)
        Loader3D {
            id: printerLoader
            property string styleName
            onLoaded: Qt.callLater(root.styleReady)
        }
    }
    }

    // ---- mouse: drag to orbit, wheel to zoom, hover to highlight, click to focus ---------
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        property point last
        property bool dragged
        cursorShape: pressed ? Qt.ClosedHandCursor : root.hover !== "" ? Qt.PointingHandCursor : Qt.OpenHandCursor
        onPressed: (m) => { last = Qt.point(m.x, m.y); dragged = false }
        onPositionChanged: (m) => {
            if (pressed) {
                var dx = m.x - last.x, dy = m.y - last.y
                if (Math.abs(dx) + Math.abs(dy) > 2) dragged = true
                if (root.flat) {        // 2D: drag to move the sheet
                    var kk = root.model3d ? root.model3d.k : 1
                    root.goalCenter = Qt.point(Math.max(0, Math.min(680, root.goalCenter.x - dx / kk)),
                                               Math.max(0, Math.min(400, root.goalCenter.y - dy / kk)))
                } else {
                    root.goalYaw -= dx * 0.35
                    root.goalPitch = Math.max(-4, Math.min(80, root.goalPitch + dy * 0.25))
                }
                last = Qt.point(m.x, m.y)
                root.idle = 0
            } else if (root.flat) {
                root.hover = root.model3d ? root.model3d.partAt(m.x, m.y) : ""
            } else if (root.view3d) {
                var hit = root.view3d.pick(m.x, m.y)
                root.hover = hit.objectHit && hit.objectHit.part !== undefined ? hit.objectHit.part : ""
            }
        }
        onReleased: (m) => {
            if (!dragged && root.hover !== "")
                root.preset(root.hover)
        }
        onExited: root.hover = ""
        onDoubleClicked: root.preset("front")
        onWheel: (w) => {
            if (root.flat)
                root.goalZoom = Math.max(0.6, Math.min(4, root.goalZoom * Math.pow(1.001, w.angleDelta.y)))
            else root.goalDist = Math.max(300, Math.min(2200, root.goalDist * Math.pow(0.999, w.angleDelta.y)))
            root.idle = 0
        }
    }

    // ---- which hover card is open -----------------------------------------------------------
    // the body and the panel are one group: the printer's own card
    function group(part) { return part === "front" ? "panel" : part }
    readonly property string hoverGroup: mouse.pressed ? "" : group(hover)
    property string openPart: ""    // card open now ("" = none; always "" when pinned)
    property bool cardHover: false  // the cursor is on the open card
    function updateOpen() {
        if (pinned) { openPart = ""; closeTimer.stop(); switchTimer.stop(); return }
        if (hoverGroup !== "") {
            closeTimer.stop()
            if (openPart === "") openPart = hoverGroup
            else if (hoverGroup !== openPart && !cardHover) switchTimer.restart()
            else switchTimer.stop()
        } else {
            switchTimer.stop()
            if (cardHover) closeTimer.stop()
            else if (openPart !== "") closeTimer.restart()
        }
    }
    onHoverGroupChanged: updateOpen()
    onCardHoverChanged: updateOpen()
    onPinnedChanged: { cardHover = false; updateOpen() }
    Timer {   // a moment to reach the card from the part
        id: closeTimer
        interval: 700
        onTriggered: if (!root.cardHover && root.hoverGroup === "") root.openPart = ""
    }
    Timer {   // passing over another part on the way to the card does not switch at once
        id: switchTimer
        interval: 350
        onTriggered: if (!root.cardHover && root.hoverGroup !== "") root.openPart = root.hoverGroup
    }

    // ---- HUD pieces ---------------------------------------------------------------------------
    component Panel: Rectangle {
        color: pal.panel
        radius: 14
        border.color: pal.line
    }
    component Caption: Text {
        color: pal.muted
        font.family: pal.family
        font.pixelSize: 11
        font.letterSpacing: 1.4
        font.weight: Font.DemiBold
    }
    component Note: Text {
        wrapMode: Text.WordWrap
        visible: text !== ""
        color: pal.muted
        font.family: pal.family
        font.pixelSize: 11
    }
    component HudButton: Rectangle {
        id: hb
        property string text
        property string sub
        property bool on: true
        property bool danger: false
        property bool primary: false
        property bool checked: false
        signal clicked
        implicitHeight: sub !== "" ? 44 : 34
        implicitWidth: Math.max(label.implicitWidth, subLabel.implicitWidth) + 28
        radius: 9
        opacity: on ? 1 : 0.4
        color: primary ? (ma.containsMouse && on ? Qt.lighter(pal.accent, 1.1) : pal.accent)
             : checked ? Qt.rgba(0.24, 0.84, 0.78, 0.18)
             : ma.containsMouse && on ? pal.btnHover : pal.btn
        border.color: danger ? Qt.rgba(1, 0.36, 0.36, 0.55) : checked ? pal.accent : pal.line
        Behavior on color { ColorAnimation { duration: 120 } }
        Column {
            anchors.centerIn: parent
            width: parent.width - 12
            Text {
                id: label
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                text: hb.text
                color: hb.primary ? "#06231f" : hb.danger ? pal.bad : pal.text
                font.family: pal.family; font.pixelSize: 13; font.weight: Font.DemiBold
            }
            Text {
                id: subLabel
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                visible: hb.sub !== ""
                text: hb.sub
                color: hb.primary ? "#06231f" : pal.muted
                font.family: pal.family; font.pixelSize: 10
            }
        }
        MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: hb.on ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: if (hb.on) hb.clicked()
        }
    }

    // ---- what each part shows: the same content in the fixed panels and the hover cards -----
    component PadsContent: Column {
        id: pc
        spacing: 12
        Row {
            width: pc.width
            Caption { text: "ALMOHADILLAS"; width: parent.width - big.width }
            Text {
                id: big
                text: root.worst < 0 ? "--" : root.worst.toFixed(1) + "%"
                color: root.sevColor(root.worst)
                font.family: pal.family; font.pixelSize: 22; font.weight: Font.Bold
                anchors.bottom: parent.bottom
            }
        }
        Repeater {
            model: root.pads
            Column {
                width: pc.width
                spacing: 5
                Row {
                    width: parent.width
                    Text { text: modelData.label; color: pal.text; font.family: pal.family; font.pixelSize: 13
                           width: parent.width - pct.width; elide: Text.ElideRight }
                    Text { id: pct; text: modelData.pct.toFixed(1) + "%"; color: root.sevColor(modelData.pct)
                           font.family: pal.family; font.pixelSize: 13; font.weight: Font.DemiBold }
                }
                Rectangle {
                    width: parent.width; height: 6; radius: 3; color: pal.btn
                    Rectangle {
                        height: parent.height; radius: 3
                        width: parent.width * Math.min(1, modelData.pct / 100)
                        color: root.sevColor(modelData.pct)
                        Behavior on width { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } }
                    }
                }
                Text { text: modelData.detail; color: pal.muted; font.family: pal.family; font.pixelSize: 11 }
            }
        }
        Note {
            visible: root.pads.length === 0
            width: pc.width
            text: root.connected ? (d.note || "Este modelo no tiene contadores de almohadillas definidos.")
                                 : "Conecta la impresora por USB y pulsa Actualizar."
            font.pixelSize: 12
        }
        Rectangle { width: pc.width; height: 1; color: pal.line }
        Grid {
            columns: 2
            spacing: 8
            width: pc.width
            readonly property real cell: (width - spacing) / 2
            HudButton { width: parent.cell; text: "Simular"; on: !!d.canReset
                        onClicked: bridge.reset("dry") }
            HudButton { width: parent.cell; text: "Guardar copia"; on: !!d.canReset
                        onClicked: bridge.backup() }
            HudButton { width: parent.cell; text: "Reseteo temporal"; on: !!d.canReset
                        onClicked: bridge.reset("temp") }
            HudButton { width: parent.cell; text: "Reseteo permanente"; danger: true; on: !!d.canReset
                        onClicked: bridge.reset("perm") }
        }
        Note {
            width: pc.width
            text: d.canReset ? "Cada reseteo pide confirmación. El permanente guarda antes una copia."
                             : (d.why || "")
        }
    }

    component InkContent: Column {
        id: ic
        spacing: 10
        Caption { text: root.cartridges ? "CARTUCHOS" + (root.cartridgeCode ? " " + root.cartridgeCode : "")
                                        : "TINTA" }
        Row {
            spacing: 10
            Repeater {
                model: root.inks
                Column {
                    spacing: 4
                    Rectangle {
                        width: 50; height: 46; radius: 7
                        color: pal.btn; border.color: pal.line
                        clip: true
                        Rectangle {
                            anchors.bottom: parent.bottom
                            width: parent.width
                            height: parent.height * (modelData.level < 0 ? 0.72 : modelData.level / 100)
                            color: modelData.color
                            opacity: modelData.level < 0 ? 0.45 : 0.9
                        }
                        Text {
                            anchors.centerIn: parent
                            text: modelData.level < 0 ? "?" : modelData.level + "%"
                            color: "white"; style: Text.Outline; styleColor: "#80000000"
                            font.family: pal.family; font.pixelSize: 12; font.weight: Font.Bold
                        }
                    }
                    Text { text: modelData.name; color: pal.muted; font.family: pal.family; font.pixelSize: 11
                           width: 50; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight }
                }
            }
        }
        Note {
            width: ic.width
            visible: text !== ""
            color: root.lowCartridges !== "" ? pal.warn : pal.muted
            text: !root.cartridges
                  ? (d.inkMeasured ? "" : "La impresora no mide los tanques: mirá el visor de cada uno.")
                  : !root.connected ? ""
                  : !d.inkMeasured ? "La impresora no informó el nivel de los cartuchos: pulsá Actualizar."
                  : root.lowCartridges !== ""
                    ? "Por agotarse: " + root.lowCartridges + ". Tené a mano el repuesto: "
                      + "la impresora se detiene cuando uno se vacía."
                  : "Nivel estimado por el chip de cada cartucho" + (root.cartridgeCode ? " Epson " + root.cartridgeCode : "") + "."
        }
        HudButton {
            visible: root.cartridges
            width: ic.width
            text: root.shot === "tanks" ? "Cerrar el escáner" : "Levantar el escáner y ver los cartuchos"
            onClicked: root.preset(root.shot === "tanks" ? "front" : "tanks")
        }
        Rectangle { width: ic.width; height: 1; color: pal.line; visible: (d.stats || []).length > 0 }
        Grid {
            columns: 2
            columnSpacing: 12
            rowSpacing: 4
            visible: (d.stats || []).length > 0
            Repeater {
                model: (d.stats || []).reduce(function (acc, kv) { return acc.concat(kv) }, [])
                Text {
                    text: modelData
                    color: index % 2 ? pal.text : pal.muted
                    font.family: pal.family; font.pixelSize: 12
                    font.weight: index % 2 ? Font.DemiBold : Font.Normal
                }
            }
        }
    }

    component PrintContent: Column {
        id: prc
        spacing: 10
        Row {
            width: prc.width
            Caption { text: "IMPRESORA"; width: parent.width - st.width
                      anchors.verticalCenter: parent.verticalCenter }
            Text {
                id: st
                text: d.status || "Sin conexión"
                color: root.connected ? (d.busy ? pal.warn : pal.ok) : pal.muted
                font.family: pal.family; font.pixelSize: 13; font.weight: Font.DemiBold
            }
        }
        Caption { text: "PRUEBAS DE IMPRESIÓN"; font.pixelSize: 10 }
        Grid {
            columns: 2
            spacing: 8
            width: prc.width
            readonly property real cell: (width - spacing) / 2
            HudButton { width: parent.cell; text: "Test de inyectores"; on: root.canDo("nozzle")
                        onClicked: root.act("nozzle") }
            HudButton { width: parent.cell; text: "Test alternativo"; on: root.canDo("nozzle2")
                        onClicked: root.act("nozzle2") }
            HudButton { width: parent.cell; text: "Patrón de color"; on: root.canDo("color")
                        onClicked: root.act("color") }
            HudButton { width: parent.cell; text: "Página de prueba"; sub: d.pageName || ""
                        on: root.canDo("page"); onClicked: root.act("page") }
        }
        HudButton {
            width: prc.width
            text: "Expulsar hoja"
            sub: "Gira los rodillos una vez · sin tinta"
            on: root.canDo("feed")
            onClicked: root.act("feed")
        }
        Rectangle { width: prc.width; height: 1; color: pal.line }
        HudButton {
            width: prc.width
            text: "Limpiar cabezales"
            sub: d.cleanLabel ? "Modo: " + d.cleanLabel : ""
            on: root.canDo("clean")
            onClicked: root.act("clean")
        }
        Note {
            width: prc.width
            text: root.actionNotes(["nozzle", "page", "clean"])
                  || "Cada acción pide confirmación antes de enviar nada a la impresora."
        }
    }

    // ---- callouts anchored to the model ------------------------------------------------------
    // pinned: a small label per part. Not pinned: a pulsing dot per part, and the part's card
    // (its info and buttons) while the cursor is on that part or on the card.
    component Callout: Item {
        id: co
        anchors.fill: parent
        property vector3d anchor: spot && spot.anchor ? spot.anchor : Qt.vector3d(0, 0, 0)
        property vector3d normal: spot && spot.normal ? spot.normal : Qt.vector3d(0, 0, 1)
        property string title
        property string value
        property string sub
        property color tint: pal.accent
        property string part
        property Component card            // what the open card holds
        property real cardWidth: 300
        // anchor, facing and label offset come from the style file
        readonly property var spot: root.model3d ? root.model3d.callouts[part] : undefined
        property real dx: spot ? spot.dx : 70
        property real dy: spot ? spot.dy : -60
        // where the spot is on screen: 2D sprite point, or the 3D anchor seen by the camera
        readonly property vector3d sp: {
            root.tick
            if (root.flat) {
                if (!spot) return Qt.vector3d(0, 0, 0)
                var p = root.model3d.toScreen(spot.x, spot.y)
                return Qt.vector3d(p.x, p.y, 0)
            }
            return root.view3d ? root.view3d.mapFrom3DScene(anchor) : Qt.vector3d(0, 0, 0)
        }
        readonly property real facing: {
            root.tick
            if (root.flat) return 1                  // everything faces the viewer in 2D
            if (!root.view3d) return 0
            var c = root.view3d.camera.scenePosition
            return c.minus(anchor).normalized().dotProduct(normal)
        }
        readonly property bool open: !root.pinned && root.openPart === part
        readonly property bool lit: root.group(root.hover) === part || open
        readonly property bool showLine: root.pinned || open
        // a card stays readable even when its spot turns away from the camera
        opacity: open ? 1 : Math.max(0, Math.min(1, (facing - 0.08) * 3.5))
        visible: opacity > 0.01

        Shape {
            anchors.fill: parent
            visible: co.showLine
            ShapePath {
                strokeColor: co.tint
                strokeWidth: co.lit ? 2 : 1.4
                fillColor: "transparent"
                startX: co.sp.x; startY: co.sp.y
                PathLine { x: co.sp.x + co.dx * 0.55; y: co.sp.y + co.dy }
                PathLine { x: co.sp.x + co.dx; y: co.sp.y + co.dy }
            }
        }
        // the spot: a ring, pulsing while it waits for the cursor
        Rectangle {
            id: ring
            readonly property real pulse: co.showLine ? 0 : (root.time * 0.8) % 1
            x: co.sp.x - width / 2; y: co.sp.y - height / 2
            width: 10 + pulse * 18; height: width; radius: width / 2
            color: "transparent"; border.color: co.tint; border.width: 1.5
            opacity: co.showLine ? 0 : 1 - pulse
        }
        Rectangle {
            x: co.sp.x - 5; y: co.sp.y - 5; width: 10; height: 10; radius: 5
            color: "transparent"; border.color: co.tint; border.width: 2
            Rectangle { anchors.centerIn: parent; width: 4; height: 4; radius: 2; color: co.tint }
        }
        // pinned: the small label
        Rectangle {
            id: tag
            visible: root.pinned
            x: co.dx > 0 ? co.sp.x + co.dx + 4 : co.sp.x + co.dx - width - 4
            y: co.sp.y + co.dy - height / 2
            width: col.implicitWidth + 22
            height: col.implicitHeight + 14
            radius: 8
            color: pal.panel
            border.color: co.lit ? co.tint : pal.line
            Column {
                id: col
                anchors.centerIn: parent
                spacing: 1
                Text { text: co.title; color: pal.muted; font.family: pal.family; font.pixelSize: 10
                       font.letterSpacing: 1.2; font.weight: Font.DemiBold }
                Text { text: co.value; color: co.tint; font.family: pal.family; font.pixelSize: 17
                       font.weight: Font.Bold; visible: text !== "" }
                Text { text: co.sub; color: pal.muted; font.family: pal.family; font.pixelSize: 11
                       visible: text !== "" }
            }
        }
        // not pinned: the card
        Panel {
            id: cardPanel
            visible: co.open
            width: co.cardWidth
            height: cardLoader.height + 32
            border.color: co.tint
            readonly property real wantX: co.dx > 0 ? co.sp.x + co.dx + 4 : co.sp.x + co.dx - width - 4
            readonly property real wantY: co.sp.y + co.dy - 24
            x: Math.max(12, Math.min(root.width - width - 12, wantX))
            y: Math.max(12, Math.min(root.height - height - 80, wantY))
            scale: co.open ? 1 : 0.92
            Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
            MouseArea { anchors.fill: parent }    // clicks on the card do not orbit the camera
            HoverHandler { onHoveredChanged: root.cardHover = hovered }
            Loader {
                id: cardLoader
                x: 16; y: 16
                width: parent.width - 32
                active: co.open
                sourceComponent: co.card
                onLoaded: item.width = Qt.binding(function () { return cardLoader.width })
                height: item ? item.implicitHeight : 0
            }
        }
    }

    Item {
        anchors.fill: parent
        visible: root.model3d !== null
        Callout {
            part: "pads"
            title: "ALMOHADILLAS"
            value: root.worst < 0 ? "--" : root.worst.toFixed(1) + "%"
            sub: root.worst < 0 ? "sin lectura" : root.worst >= 90 ? "nivel crítico"
                 : root.worst >= 70 ? "nivel alto" : "nivel normal"
            tint: root.sevColor(root.worst)
            card: PadsContent {}
        }
        Callout {
            part: "tanks"
            title: root.cartridges ? "CARTUCHOS" + (root.cartridgeCode ? " " + root.cartridgeCode : "") : "TINTA"
            value: d.inkMeasured ? root.inks.map(function (k) { return k.level < 0 ? "--" : k.level }).join(" · ")
                                 : root.cartridges ? "--" : "Visor"
            sub: root.lowCartridges !== "" ? "por agotarse: " + root.lowCartridges
                 : d.inkMeasured ? "nivel estimado por la impresora"
                 : root.cartridges ? "sin lectura" : "esta impresora no mide los tanques"
            tint: root.lowCartridges !== "" ? pal.warn : pal.accent
            card: InkContent {}
        }
        Callout {
            part: "panel"
            title: "ESTADO"
            value: d.status || "Sin conexión"
            tint: root.connected ? (d.busy ? pal.warn : pal.ok) : pal.muted
            card: PrintContent {}
            cardWidth: 320
        }
    }

    // ---- HUD ------------------------------------------------------------------------------
    // title block, top left
    Column {
        x: 22; y: 18
        spacing: 2
        Caption { text: (root.flat ? "VISTA 2D · " : "VISTA 3D · ") + (root.connected ? "CONECTADA" : "SIN CONEXIÓN") }
        Text {
            text: d.title || (root.model3d ? root.model3d.defaultTitle : "")
            color: pal.text
            font.family: pal.family; font.pixelSize: 26; font.weight: Font.Bold
        }
        Row {
            spacing: 8
            Rectangle {
                width: chip.implicitWidth + 18; height: 22; radius: 11
                anchors.verticalCenter: parent.verticalCenter
                color: Qt.rgba(stat.tint.r, stat.tint.g, stat.tint.b, 0.16)
                border.color: Qt.rgba(stat.tint.r, stat.tint.g, stat.tint.b, 0.55)
                QtObject { id: stat; property color tint: root.connected ? (d.busy ? pal.warn : pal.ok) : pal.muted }
                Text { id: chip; anchors.centerIn: parent; text: d.status || "Sin conexión"
                       color: stat.tint; font.family: pal.family; font.pixelSize: 12; font.weight: Font.DemiBold }
            }
            Text {
                text: "Serie " + (d.serial || "--")
                color: pal.muted; font.family: pal.family; font.pixelSize: 13
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    // what the printer is doing, top centre
    Panel {
        id: banner
        visible: opacity > 0.01
        opacity: root.activity !== "" ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 250 } }
        anchors.horizontalCenter: parent.horizontalCenter
        y: 18
        width: Math.min(420, Math.max(260, bannerCol.implicitWidth + 36))
        height: bannerCol.implicitHeight + 24
        readonly property color tone: root.activity === "error" ? pal.bad : pal.warn
        border.color: tone
        Column {
            id: bannerCol
            x: 18; y: 12
            width: parent.width - 36
            spacing: 6
            Row {
                spacing: 8
                Rectangle {
                    width: 9; height: 9; radius: 4.5
                    anchors.verticalCenter: parent.verticalCenter
                    color: banner.tone
                    opacity: 0.45 + 0.55 * Math.abs(Math.sin(root.time * 3))
                }
                Caption {
                    text: root.activity === "cleaning" ? "LIMPIANDO CABEZALES"
                          : root.activity === "printing" ? "IMPRIMIENDO"
                          : root.activity === "feeding" ? "EXPULSANDO HOJA"
                          : root.activity === "error" ? "ERROR · TRABAJO DETENIDO" : ""
                    color: banner.tone
                }
                Caption {
                    visible: root.progress >= 0
                    text: Math.round(root.progress * 100) + " %"
                    color: pal.text
                }
            }
            Text {
                width: parent.width
                visible: text !== ""
                text: d.activityText || ""
                elide: Text.ElideRight
                color: pal.text; font.family: pal.family; font.pixelSize: 12
            }
            Rectangle {
                visible: root.progress >= 0
                width: parent.width; height: 5; radius: 2.5; color: pal.btn
                Rectangle {
                    height: parent.height; radius: 2.5; color: pal.warn
                    width: parent.width * Math.max(0, Math.min(1, root.progress))
                    Behavior on width { NumberAnimation { duration: 900 } }
                }
            }
        }
    }

    // pinned: pads and printer panels on the right, ink at the bottom left
    Column {
        visible: root.pinned
        anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: 16
        spacing: 12
        Panel {
            width: 300
            height: padsFixed.implicitHeight + 32
            PadsContent { id: padsFixed; x: 16; y: 16; width: parent.width - 32 }
        }
        Panel {
            width: 300
            height: printFixed.implicitHeight + 32
            PrintContent { id: printFixed; x: 16; y: 16; width: parent.width - 32 }
        }
    }
    Panel {
        visible: root.pinned
        anchors.left: parent.left; anchors.bottom: parent.bottom
        anchors.margins: 16
        width: 300
        height: inkFixed.implicitHeight + 32
        InkContent { id: inkFixed; x: 16; y: 16; width: parent.width - 32 }
    }

    // camera bar, bottom centre
    Panel {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 16
        width: camRow.implicitWidth + 16
        height: 50
        Row {
            id: camRow
            anchors.centerIn: parent
            spacing: 6
            HudButton { text: "Frente"; checked: root.shot === "front"; onClicked: root.preset("front") }
            HudButton { text: root.inkPart; checked: root.shot === "tanks"; onClicked: root.preset("tanks") }
            HudButton { text: "Almohadillas"; checked: root.shot === "pads"; onClicked: root.preset("pads") }
            HudButton { text: "Panel"; checked: root.shot === "panel"; onClicked: root.preset("panel") }
            Rectangle { width: 1; height: 26; color: pal.line; anchors.verticalCenter: parent.verticalCenter }
            HudButton { text: root.spin ? "Giro: sí" : "Giro: no"; checked: root.spin; visible: !root.flat
                        onClicked: root.preset("spin") }
            HudButton { text: root.flat ? "Vista: 2D" : "Vista: 3D"; checked: root.flat
                        onClicked: if (root.hasBridge) bridge.mode2d = !bridge.mode2d }
            HudButton { text: root.pinned ? "Info: fija" : "Info: al pasar"; checked: root.pinned
                        onClicked: if (root.hasBridge) bridge.pinned = !bridge.pinned }
            HudButton { text: "Interior"; checked: root.xrayManual || root.activity !== ""
                        onClicked: root.xrayManual = !root.xrayManual }
            HudButton { text: "Actualizar"; primary: true; on: d.canRead === undefined ? true : !!d.canRead
                        onClicked: if (root.hasBridge) bridge.refresh() }
        }
    }
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 72
        text: (root.pinned ? "" : "Pasa el cursor por la impresora, " + (root.cartridges ? "el escáner (cartuchos)" : "los tanques")
                                  + " o las almohadillas · ")
              + (root.flat ? "Arrastra para mover" : "Arrastra para girar")
              + " · rueda para acercar · clic en una pieza para enfocarla"
        color: pal.muted; opacity: 0.8
        font.family: pal.family; font.pixelSize: 11
    }
    Text {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 10
        visible: root.fps > 0
        text: Math.round(root.fps) + " FPS" + (root.cap30 ? " · tope 30" : "")
        color: root.fps < (root.hasBridge ? bridge.minFps : 20) ? pal.bad : pal.muted
        opacity: fpsMouse.containsMouse ? 1 : 0.7
        font.family: pal.family; font.pixelSize: 10
        // right-click: cap at 30 FPS, or lift the cap
        MouseArea {
            id: fpsMouse
            anchors.fill: parent
            anchors.margins: -6
            hoverEnabled: true
            acceptedButtons: Qt.RightButton
            onClicked: if (root.hasBridge) bridge.fps30 = !bridge.fps30
        }
        Panel {
            visible: fpsMouse.containsMouse
            anchors.right: parent.right
            anchors.bottom: parent.top
            anchors.bottomMargin: 8
            width: fpsTip.implicitWidth + 20
            height: fpsTip.implicitHeight + 12
            radius: 8
            Text {
                id: fpsTip
                anchors.centerIn: parent
                text: "Clic derecho: " + (root.cap30 ? "quitar el tope de 30 FPS" : "limitar a 30 FPS")
                color: pal.text; font.family: pal.family; font.pixelSize: 11
            }
        }
    }
}
