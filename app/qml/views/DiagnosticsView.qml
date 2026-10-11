import QtQuick
import QtQuick.Controls
import "../components"

Item {
    id: root
    // AURA_DIAGNOSTICS_FINAL_POLISH_FIX12
    // AURA_DIAGNOSTICS_COMPACT_FIDELITY_FIX11
    // AURA_DIAGNOSTICS_UI_PARITY_FIX10
    // AURA_DIAGNOSTICS_COLOR_PARITY_FIX9
    property bool lightMode: false
    property bool compactMode: false

    onVisibleChanged: {
        if (visible) {
            diagnosticsBridge.refreshDiagnostics()
            normalRing.requestPaint()
            compactLogo.requestPaint()
        }
    }
    onCompactModeChanged: {
        normalRing.requestPaint()
        compactLogo.requestPaint()
    }
    onLightModeChanged: {
        normalRing.requestPaint()
        compactLogo.requestPaint()
    }

    Connections {
        target: coreBridge
        function onDiagnosticsChanged() {
            normalRing.requestPaint()
            compactLogo.requestPaint()
        }
    }

    Timer {
        interval: 4000
        running: root.visible
        repeat: true
        onTriggered: diagnosticsBridge.refreshDiagnostics()
    }

    GlassPanel {
        id: panel
        x: 12
        y: 12
        width: Math.min(root.compactMode ? 500 : 560, Math.max(420, root.width - 24))
        height: root.compactMode ? 274 : 360
        radius: 8
        lightMode: root.lightMode
        accent: "#6DE8FF"

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: 7
            color: root.lightMode ? "#F7FBFCEB" : "#F0050D1C"
            border.width: 0
        }

        Rectangle {
            id: header
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: root.compactMode ? 35 : 40
            radius: 8
            color: root.lightMode ? "#EEF7FAFC" : "#ED071323"

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: root.lightMode ? "#245C899C" : "#1769D5E7"
            }

            Row {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 11
                spacing: 8

                Canvas {
                    width: 17
                    height: 17
                    antialiasing: true
                    onPaint: {
                        var c = getContext("2d")
                        c.clearRect(0,0,width,height)
                        c.strokeStyle = "#74EFFF"
                        c.lineWidth = 1.4
                        c.lineCap = "round"
                        c.lineJoin = "round"
                        c.beginPath()
                        c.moveTo(8.5,1.9)
                        c.lineTo(14,4.1)
                        c.lineTo(14,8.2)
                        c.bezierCurveTo(14,12.0,11.8,14.6,8.5,16.1)
                        c.bezierCurveTo(5.2,14.6,3,12.0,3,8.2)
                        c.lineTo(3,4.1)
                        c.closePath()
                        c.stroke()

                        c.strokeStyle = "#3CC8F3"
                        c.lineWidth = 1
                        c.globalAlpha = .72
                        c.beginPath()
                        c.moveTo(8.5,5.1)
                        c.lineTo(8.5,11.8)
                        c.moveTo(5.8,8.4)
                        c.lineTo(11.2,8.4)
                        c.stroke()
                        c.globalAlpha = 1
                    }
                }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.compactMode ? "ÉTAT DU SYSTÈME" : "AURA · ÉTAT DU SYSTÈME"
                    color: root.lightMode ? "#465E6D" : "#C3E8F2"
                    font.pixelSize: 9
                    font.weight: Font.DemiBold
                    font.letterSpacing: .8
                }
            }

            Row {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.rightMargin: 10
                spacing: 5

                Rectangle {
                    width: 70
                    height: 23
                    radius: 5
                    color: modeHover.hovered
                           ? (root.lightMode ? "#E7F4F8FA" : "#A8142A37")
                           : (root.lightMode ? "#C8FFFFFF" : "#9A091823")
                    border.width: 1
                    border.color: modeHover.hovered ? "#74EFFF"
                                                    : (root.lightMode ? "#365C7792" : "#2A2E52")
                    Text {
                        anchors.centerIn: parent
                        text: root.compactMode ? "NORMAL" : "COMPACT"
                        color: modeHover.hovered ? "#D9F7FF"
                                                : (root.lightMode ? "#576A80" : "#8E93BB")
                        font.pixelSize: 6
                        font.weight: Font.Bold
                    }
                    HoverHandler { id: modeHover }
                    TapHandler { onTapped: root.compactMode = !root.compactMode }
                }

                Rectangle {
                    width: 23
                    height: 23
                    radius: 5
                    color: closeHover.hovered
                           ? (root.lightMode ? "#E8F4F7FA" : "#FF0E132B")
                           : (root.lightMode ? "#C8FFFFFF" : "#9A091823")
                    border.width: 1
                    border.color: closeHover.hovered ? "#74EFFF"
                                                     : (root.lightMode ? "#365C7792" : "#2A2E52")
                    Text {
                        anchors.centerIn: parent
                        text: "×"
                        color: closeHover.hovered ? "#D9F7FF"
                                                 : (root.lightMode ? "#5D6F83" : "#8E93BB")
                        font.pixelSize: 12
                    }
                    HoverHandler { id: closeHover }
                    TapHandler { onTapped: bridge.setWorkspace("home") }
                }
            }
        }

        Item {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: header.bottom
            anchors.bottom: parent.bottom

            Row {
                id: normalMain
                visible: !root.compactMode
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 15
                anchors.rightMargin: 15
                anchors.topMargin: 15
                height: 208
                spacing: 17

                Item {
                    width: 214
                    height: 208

                    Rectangle {
                        anchors.right: parent.right
                        width: 1
                        height: parent.height
                        color: root.lightMode ? "#244E6B7C" : "#20506478"
                    }

                    Canvas {
                        id: normalRing
                        width: 184
                        height: 184
                        anchors.centerIn: parent
                        anchors.horizontalCenterOffset: -7
                        antialiasing: true
                        Component.onCompleted: requestPaint()
                        onVisibleChanged: if (visible) requestPaint()

                        onPaint: {
                            var c = getContext("2d")
                            c.clearRect(0,0,width,height)
                            var cx=92, cy=92
                            var ram=Math.max(0,Math.min(100,diagnosticsBridge.diagRamPercent))
                            var PI=Math.PI

                            function circle(r,col,w) {
                                c.strokeStyle=col
                                c.lineWidth=w
                                c.beginPath()
                                c.arc(cx,cy,r,0,PI*2)
                                c.stroke()
                            }

                            circle(72,root.lightMode ? "rgba(74,92,116,.35)" : "rgba(24,66,84,.54)",.75)
                            circle(63,root.lightMode ? "rgba(31,95,123,.34)" : "rgba(22,90,111,.56)",.70)
                            circle(54,root.lightMode ? "rgba(74,92,116,.30)" : "rgba(24,66,84,.54)",.75)
                            circle(45,root.lightMode ? "rgba(31,95,123,.30)" : "rgba(22,90,111,.56)",.70)
                            circle(36,root.lightMode ? "rgba(74,92,116,.28)" : "rgba(24,66,84,.54)",.75)

                            var centerGrad=c.createRadialGradient(cx,cy,2,cx,cy,27)
                            if (root.lightMode) {
                                centerGrad.addColorStop(0,"#F8FCFD")
                                centerGrad.addColorStop(1,"#E8F2F6")
                            } else {
                                centerGrad.addColorStop(0,"#071722")
                                centerGrad.addColorStop(1,"#030A10")
                            }
                            c.fillStyle=centerGrad
                            c.strokeStyle=root.lightMode ? "#5F8EA3" : "#276C80"
                            c.lineWidth=1
                            c.beginPath(); c.arc(cx,cy,27,0,PI*2); c.fill(); c.stroke()

                            var arcs=[
                                [3.32,4.16,"#67D9EE",2.2],
                                [4.20,4.80,"#63B9D2",2.2],
                                [4.88,5.62,"#7896C0",2.0],
                                [5.82,6.48,"#4CA6C6",2.0],
                                [.31,1.00,"#74EFFF",2.3],
                                [1.08,1.79,"#59B2CF",2.0],
                                [1.95,2.63,"#708DB5",1.9],
                                [2.70,3.18,"#6DE2F0",2.1]
                            ]
                            c.lineCap="round"
                            for (var i=0;i<arcs.length;i++) {
                                c.strokeStyle=arcs[i][2]
                                c.lineWidth=arcs[i][3]
                                c.beginPath(); c.arc(cx,cy,68,arcs[i][0],arcs[i][1]); c.stroke()
                            }

                            c.strokeStyle="#63D5E8"
                            c.lineWidth=1.8
                            c.globalAlpha=.34
                            c.beginPath()
                            c.arc(cx,cy,58,-PI/2,-PI/2+PI*2*(ram/100))
                            c.stroke()
                            c.globalAlpha=1

                            c.setLineDash([4,7])
                            c.strokeStyle="#74EFFF"
                            c.lineWidth=1.1
                            c.globalAlpha=.34
                            c.beginPath(); c.arc(cx,cy,49,0,PI*2); c.stroke()
                            c.setLineDash([])
                            c.globalAlpha=1

                            c.strokeStyle=root.lightMode ? "#5F7887" : "#2B6272"
                            c.lineWidth=.65
                            c.globalAlpha=.75
                            var ticks=[
                                [92,13,92,22],[92,162,92,171],
                                [13,92,22,92],[162,92,171,92],
                                [36,36,42,42],[142,142,148,148],
                                [142,42,148,36],[36,148,42,142]
                            ]
                            for (var t=0;t<ticks.length;t++) {
                                c.beginPath()
                                c.moveTo(ticks[t][0],ticks[t][1])
                                c.lineTo(ticks[t][2],ticks[t][3])
                                c.stroke()
                            }
                            c.globalAlpha=1

                            var nodes=[
                                [92,19,2.1,"#74EFFF"],
                                [153,60,1.8,"#68D9EA"],
                                [148,134,2.1,"#66B7CF"],
                                [75,161,1.7,"#68D9EA"],
                                [27,114,1.9,"#74EFFF"]
                            ]
                            for (var n=0;n<nodes.length;n++) {
                                c.fillStyle=nodes[n][3]
                                c.beginPath()
                                c.arc(nodes[n][0],nodes[n][1],nodes[n][2],0,PI*2)
                                c.fill()
                            }
                        }
                    }

                    Column {
                        anchors.centerIn: parent
                        anchors.horizontalCenterOffset: -7
                        spacing: 5
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: diagnosticsBridge.diagReady
                                  ? (Math.round(diagnosticsBridge.diagRamPercent) + "%")
                                  : "LECTURE…"
                            color: root.lightMode ? "#29485A" : "#DDF6FC"
                            font.pixelSize: diagnosticsBridge.diagReady ? 30 : 9
                            font.weight: diagnosticsBridge.diagReady ? Font.Light : Font.DemiBold
                            font.letterSpacing: diagnosticsBridge.diagReady ? 0 : 0.8
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: diagnosticsBridge.diagReady ? "MÉMOIRE CORES" : "ÉTAT SYSTÈME"
                            color: root.lightMode ? "#657C87" : "#6F8F9C"
                            font.pixelSize: 6
                            font.weight: Font.DemiBold
                            font.letterSpacing: 1.45
                        }
                    }
                }

                Column {
                    width: parent.width-231
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 12

                    Repeater {
                        model: [
                            ["CPU",diagnosticsBridge.diagCpuPercent,diagnosticsBridge.diagCpuText],
                            ["RAM",diagnosticsBridge.diagRamPercent,diagnosticsBridge.diagRamText],
                            ["VRAM",diagnosticsBridge.diagVramPercent,diagnosticsBridge.diagVramText],
                            ["DISQUE",diagnosticsBridge.diagDiskPercent,diagnosticsBridge.diagDiskText],
                            ["TEMP.",diagnosticsBridge.diagTempPercent,diagnosticsBridge.diagTempText]
                        ]
                        delegate: Row {
                            width: parent.width
                            height: 12
                            spacing: 10

                            Text {
                                width: 72
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData[0]
                                color: root.lightMode ? "#66778A" : "#58788D"
                                font.pixelSize: 8
                                font.weight: Font.DemiBold
                            }
                            Rectangle {
                                width: Math.max(95,parent.width-72-92)
                                height: 4
                                anchors.verticalCenter: parent.verticalCenter
                                radius: 2
                                color: root.lightMode ? "#245D8798" : "#FF0D1228"
                                Rectangle {
                                    width: parent.width*Math.max(0,Math.min(100,modelData[1]))/100
                                    height: parent.height
                                    radius: parent.radius
                                    gradient: Gradient {
                                        orientation: Gradient.Horizontal
                                        GradientStop { position: 0.0; color: "#418FAE" }
                                        GradientStop { position: 0.58; color: "#74EFFF" }
                                        GradientStop { position: 1.0; color: "#589DBA" }
                                    }
                                }
                            }
                            Text {
                                width: 72
                                anchors.verticalCenter: parent.verticalCenter
                                horizontalAlignment: Text.AlignRight
                                elide: Text.ElideRight
                                text: diagnosticsBridge.diagReady ? modelData[2] : "—"
                                color: root.lightMode ? "#506A7C" : "#A8DCE7"
                                font.pixelSize: 8
                                font.weight: Font.DemiBold
                            }
                        }
                    }

                    Row {
                        width: parent.width
                        height: 12
                        Text { width: 72; text: "RÉSEAU"; color: "#58788D"; font.pixelSize: 8; font.weight: Font.DemiBold }
                        Text { width: (parent.width-72)/2; text: diagnosticsBridge.diagReady ? ("↓ "+diagnosticsBridge.diagDownloadText) : "↓ —"; color: "#6FAFC0"; font.pixelSize: 8 }
                        Text { width: (parent.width-72)/2; text: diagnosticsBridge.diagReady ? ("↑ "+diagnosticsBridge.diagUploadText) : "↑ —"; color: "#74AFC0"; font.pixelSize: 8 }
                    }
                }
            }

            Grid {
                visible: !root.compactMode
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: normalMain.bottom
                anchors.leftMargin: 15
                anchors.rightMargin: 15
                anchors.topMargin: 14
                columns: 4
                columnSpacing: 8

                Repeater {
                    model: [
                        ["diag","DIAGNOSTIC RAPIDE",true],
                        ["mem","NETTOYAGE MÉMOIRE",false],
                        ["opt","OPTIMISER SYSTÈME",false],
                        ["gear","PARAMÈTRES AVANCÉS",true]
                    ]

                    delegate: Rectangle {
                        width: (parent.width-24)/4
                        height: 68
                        radius: 6
                        opacity: modelData[2] ? 1.0 : .34
                        color: actionHover.hovered && modelData[2]
                               ? (root.lightMode ? "#F0F7FAFC" : "#FF10152F")
                               : (root.lightMode ? "#D6FFFFFF" : "#7607121D")
                        border.width: 1
                        border.color: actionHover.hovered && modelData[2]
                                      ? "#4EAFC6"
                                      : (root.lightMode ? "#335A7893" : "#1B4657")

                        Column {
                            anchors.centerIn: parent
                            spacing: 7

                            Canvas {
                                id: actionIcon
                                property string iconType: modelData[0]
                                property bool iconEnabled: modelData[2]
                                width: 19
                                height: 19
                                anchors.horizontalCenter: parent.horizontalCenter
                                antialiasing: true
                                Component.onCompleted: requestPaint()
                                onPaint: {
                                    var c=getContext("2d")
                                    c.clearRect(0,0,width,height)
                                    c.strokeStyle = iconType==="gear" ? "#74EFFF"
                                                                      : (iconEnabled ? "#74EFFF" : "#456372")
                                    c.lineWidth=1.4
                                    c.lineCap="round"
                                    c.lineJoin="round"

                                    if (iconType==="diag") {
                                        c.beginPath(); c.arc(9.5,9.5,6.2,0,Math.PI*2); c.stroke()
                                        c.beginPath(); c.arc(9.5,9.5,1.8,0,Math.PI*2); c.stroke()
                                        c.beginPath()
                                        c.moveTo(9.5,.8);c.lineTo(9.5,3.2)
                                        c.moveTo(9.5,15.8);c.lineTo(9.5,18.2)
                                        c.moveTo(.8,9.5);c.lineTo(3.2,9.5)
                                        c.moveTo(15.8,9.5);c.lineTo(18.2,9.5)
                                        c.stroke()
                                    } else if (iconType==="mem") {
                                        c.beginPath()
                                        c.moveTo(5.5,16);c.bezierCurveTo(4,12.8,4.5,9.6,6.4,7)
                                        c.lineTo(8.7,3.5);c.lineTo(8.7,11)
                                        c.lineTo(10.4,9.2);c.lineTo(12.1,11)
                                        c.lineTo(13.5,9.6);c.bezierCurveTo(15.3,12.3,15.7,14.6,14.2,16)
                                        c.stroke()
                                        c.beginPath();c.moveTo(6.2,16);c.lineTo(14.5,16);c.stroke()
                                    } else if (iconType==="opt") {
                                        c.strokeRect(4.2,2.2,10.8,14.7)
                                        c.beginPath()
                                        c.moveTo(6.5,6);c.lineTo(12.8,6)
                                        c.moveTo(6.5,9.3);c.lineTo(8.8,9.3)
                                        c.moveTo(11,9.3);c.lineTo(12.8,9.3)
                                        c.moveTo(6.5,12.5);c.lineTo(11.5,12.5)
                                        c.stroke()
                                    } else {
                                        c.beginPath();c.arc(9.5,9.5,2.5,0,Math.PI*2);c.stroke()
                                        c.beginPath()
                                        c.moveTo(9.5,.8);c.lineTo(9.5,3)
                                        c.moveTo(9.5,16);c.lineTo(9.5,18.2)
                                        c.moveTo(.8,9.5);c.lineTo(3,9.5)
                                        c.moveTo(16,9.5);c.lineTo(18.2,9.5)
                                        c.moveTo(3.1,3.1);c.lineTo(4.8,4.8)
                                        c.moveTo(14.2,14.2);c.lineTo(15.9,15.9)
                                        c.moveTo(15.9,3.1);c.lineTo(14.2,4.8)
                                        c.moveTo(4.8,14.2);c.lineTo(3.1,15.9)
                                        c.stroke()
                                    }
                                }
                            }

                            Text {
                                width: parent.width
                                anchors.horizontalCenter: parent.horizontalCenter
                                horizontalAlignment: Text.AlignHCenter
                                wrapMode: Text.WordWrap
                                text: modelData[1]
                                color: root.lightMode ? "#677589" : "#6E8995"
                                font.pixelSize: 7
                                font.weight: Font.DemiBold
                            }
                        }

                        HoverHandler { id: actionHover }
                        TapHandler {
                            enabled: modelData[2]
                            onTapped: {
                                if (modelData[0]==="diag")
                                    diagnosticsBridge.refreshDiagnostics()
                                else if (modelData[0]==="gear")
                                    bridge.setWorkspace("settings")
                            }
                        }
                    }
                }
            }

            Row {
                id: compactMain
                visible: root.compactMode
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                anchors.topMargin: 13
                height: 169
                spacing: 22

                Item {
                    width: 169
                    height: 169

                    Canvas {
                        id: compactLogo
                        width: 166
                        height: 166
                        anchors.centerIn: parent
                        antialiasing: true
                        Component.onCompleted: requestPaint()
                        onVisibleChanged: if (visible) requestPaint()

                        onPaint: {
                            var c = getContext("2d")
                            c.clearRect(0, 0, width, height)

                            var s = width / 180.0
                            var PI = Math.PI
                            c.save()
                            c.scale(s, s)

                            function circle(r, col, w) {
                                c.strokeStyle = col
                                c.lineWidth = w
                                c.beginPath()
                                c.arc(90, 90, r, 0, PI * 2)
                                c.stroke()
                            }

                            circle(72, "rgba(109,232,255,.14)", .80)
                            circle(63, "rgba(63,140,255,.25)", .70)
                            circle(54, "rgba(109,232,255,.12)", .80)
                            circle(45, "rgba(63,140,255,.22)", .70)
                            circle(36, "rgba(109,232,255,.11)", .80)

                            var center = c.createRadialGradient(90,90,3,90,90,27)
                            center.addColorStop(0, "#071722")
                            center.addColorStop(1, "#030A10")
                            c.fillStyle = center
                            c.strokeStyle = "rgba(109,232,255,.17)"
                            c.lineWidth = 1
                            c.beginPath()
                            c.arc(90, 90, 27, 0, PI * 2)
                            c.fill()
                            c.stroke()

                            var arcs = [
                                [3.32,4.16,"#67D9EE",2.1],
                                [4.20,4.80,"#63B9D2",2.1],
                                [4.88,5.62,"#7896C0",1.9],
                                [5.82,6.48,"#4CA6C6",1.9],
                                [.31,1.00,"#74EFFF",2.2],
                                [1.08,1.79,"#59B2CF",1.9],
                                [1.95,2.63,"#708DB5",1.8],
                                [2.70,3.18,"#6DE2F0",2.0]
                            ]
                            c.lineCap = "round"
                            for (var i = 0; i < arcs.length; ++i) {
                                c.strokeStyle = arcs[i][2]
                                c.lineWidth = arcs[i][3]
                                c.globalAlpha = .84
                                c.beginPath()
                                c.arc(90, 90, 68, arcs[i][0], arcs[i][1])
                                c.stroke()
                            }
                            c.globalAlpha = 1

                            c.strokeStyle = "rgba(109,232,255,.26)"
                            c.lineWidth = .65
                            var ticks = [
                                [90,11,90,20],[90,160,90,169],
                                [11,90,20,90],[160,90,169,90],
                                [34,34,40,40],[140,140,146,146],
                                [140,40,146,34],[34,146,40,140]
                            ]
                            for (var t = 0; t < ticks.length; ++t) {
                                c.beginPath()
                                c.moveTo(ticks[t][0], ticks[t][1])
                                c.lineTo(ticks[t][2], ticks[t][3])
                                c.stroke()
                            }

                            var nodes = [
                                [90,17,2.1,"#76CFE4"],
                                [151,58,1.8,"#74EFFF"],
                                [146,132,2.1,"#7896C0"],
                                [73,159,1.7,"#74EFFF"],
                                [25,112,1.9,"#76CFE4"]
                            ]
                            for (var n = 0; n < nodes.length; ++n) {
                                c.fillStyle = nodes[n][3]
                                c.globalAlpha = .78
                                c.beginPath()
                                c.arc(nodes[n][0], nodes[n][1], nodes[n][2], 0, PI * 2)
                                c.fill()
                            }
                            c.globalAlpha = 1

                            function masterLogoPath() {
                                c.beginPath()
                                c.moveTo(36.9,147.6)
                                c.lineTo(82.44,34.2)
                                c.quadraticCurveTo(84.96,27,90,27)
                                c.quadraticCurveTo(95.04,27,97.56,34.2)
                                c.lineTo(147.6,147.6)
                                c.lineTo(118.44,147.6)
                                c.lineTo(107.28,128.88)
                                c.lineTo(94.5,128.88)
                                c.lineTo(101.7,117.9)
                                c.lineTo(112.5,117.9)
                                c.lineTo(90,59.4)
                                c.lineTo(59.76,147.6)
                                c.closePath()
                            }

                            c.save()
                            c.translate(90, 90)
                            c.scale(.72, .72)
                            c.translate(-90, -90)

                            var logoGrad = c.createLinearGradient(42,145,138,32)
                            logoGrad.addColorStop(0, "#63E7F4")
                            logoGrad.addColorStop(.52, "#68B8D5")
                            logoGrad.addColorStop(1, "#718CC7")

                            c.save()
                            c.globalAlpha = .12
                            c.fillStyle = logoGrad
                            c.shadowColor = "rgba(109,232,255,.24)"
                            c.shadowBlur = 5
                            masterLogoPath()
                            c.fill()
                            c.restore()

                            c.fillStyle = logoGrad
                            c.strokeStyle = "rgba(216,247,255,.13)"
                            c.lineWidth = 1.8
                            c.shadowColor = "rgba(109,232,255,.12)"
                            c.shadowBlur = 2
                            masterLogoPath()
                            c.fill()
                            c.stroke()
                            c.shadowBlur = 0
                            c.restore()

                            c.restore()
                        }
                    }
                }

                Column {
                    width: parent.width - 191
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 11

                    Repeater {
                        model: [
                            ["CPU",diagnosticsBridge.diagCpuPercent,diagnosticsBridge.diagCpuText],
                            ["RAM",diagnosticsBridge.diagRamPercent,diagnosticsBridge.diagRamText],
                            ["STOCKAGE",diagnosticsBridge.diagDiskPercent,diagnosticsBridge.diagDiskText],
                            ["TEMPÉRATURE",diagnosticsBridge.diagTempPercent,diagnosticsBridge.diagTempText]
                        ]

                        delegate: Row {
                            width: parent.width
                            height: 13
                            spacing: 10

                            Text {
                                width: 74
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData[0]
                                color: root.lightMode ? "#66778A" : "#638492"
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                            }

                            Rectangle {
                                width: Math.max(90, parent.width - 74 - 96)
                                height: 4
                                anchors.verticalCenter: parent.verticalCenter
                                radius: 2
                                color: root.lightMode ? "#245D8798" : "#CE08151F"

                                Rectangle {
                                    width: parent.width * Math.max(0,Math.min(100,modelData[1])) / 100
                                    height: parent.height
                                    radius: parent.radius
                                    gradient: Gradient {
                                        orientation: Gradient.Horizontal
                                        GradientStop { position: 0.0; color: "#418FAE" }
                                        GradientStop { position: 0.58; color: "#74EFFF" }
                                        GradientStop { position: 1.0; color: "#589DBA" }
                                    }
                                }
                            }

                            Text {
                                width: 76
                                anchors.verticalCenter: parent.verticalCenter
                                horizontalAlignment: Text.AlignRight
                                elide: Text.ElideRight
                                text: diagnosticsBridge.diagReady ? modelData[2] : "—"
                                color: root.lightMode ? "#506A7C" : "#A8DCE7"
                                font.pixelSize: 9
                                font.weight: Font.DemiBold
                            }
                        }
                    }

                    Row {
                        width: parent.width
                        height: 13

                        Text {
                            width: 74
                            text: "RÉSEAU"
                            color: root.lightMode ? "#66778A" : "#638492"
                            font.pixelSize: 9
                            font.weight: Font.DemiBold
                        }
                        Text {
                            width: (parent.width - 74) / 2
                            text: diagnosticsBridge.diagReady ? ("↓ " + diagnosticsBridge.diagDownloadText) : "↓ —"
                            color: "#6FAFC0"
                            font.pixelSize: 9
                        }
                        Text {
                            width: (parent.width - 74) / 2
                            text: diagnosticsBridge.diagReady ? ("↑ " + diagnosticsBridge.diagUploadText) : "↑ —"
                            color: "#74AFC0"
                            font.pixelSize: 9
                        }
                    }
                }
            }


            Rectangle {
                visible: root.compactMode
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                anchors.bottomMargin: 12
                height: 33
                radius: 5
                color: compactHover.hovered ? "#8A0A1C28" : "#7607121D"
                border.width: 1
                border.color: compactHover.hovered ? "#4EAFC6" : "#23404D"
                Text {
                    anchors.centerIn: parent
                    text: "VOIR LES DIAGNOSTICS"
                    color: compactHover.hovered ? "#D9F7FF" : "#76909B"
                    font.pixelSize: 8
                    font.weight: Font.DemiBold
                }
                HoverHandler { id: compactHover }
                TapHandler { onTapped: root.compactMode=false }
            }
        }
    }
}

