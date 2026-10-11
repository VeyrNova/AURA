import QtQuick
import QtQuick.Effects

Item {
    id: root

    property Item backdropSource: null
    property real sourceX: 0
    property real sourceY: 0
    property bool lightMode: false
    property color accent: "#74EFFF"
    property real cornerRadius: 20
    property real blurStrength: 0.78
    property real saturationBoost: 0.18
    property bool liveBackdrop: true
    property real lensX: 0.50
    property real lensY: 0.36
    property real darkOpacity: 1.0
    property real lightOpacity: 1.0

    // Soft external depth. Kept separate from the sampled backdrop.
    Rectangle {
        anchors.fill: parent
        anchors.topMargin: 9
        anchors.leftMargin: 2
        anchors.rightMargin: -2
        anchors.bottomMargin: -9
        radius: root.cornerRadius
        color: root.lightMode ? "#18345062" : "#56000000"
        opacity: root.lightMode ? 0.07 : 0.22
    }

    ShaderEffectSource {
        id: backdropCapture
        sourceItem: root.backdropSource
        sourceRect: Qt.rect(root.sourceX, root.sourceY, root.width, root.height)
        textureSize: Qt.size(Math.max(1, root.width), Math.max(1, root.height))
        live: root.liveBackdrop
        recursive: true
        hideSource: false
        visible: false
    }

    Item {
        id: roundedMask
        anchors.fill: parent
        visible: false
        layer.enabled: true

        Rectangle {
            anchors.fill: parent
            radius: root.cornerRadius
            color: "white"
        }
    }

    MultiEffect {
        anchors.fill: parent
        source: backdropCapture
        blurEnabled: true
        blur: root.blurStrength
        blurMax: 48
        saturation: root.saturationBoost
        brightness: root.lightMode ? 0.06 : -0.04
        maskEnabled: true
        maskSource: roundedMask
        opacity: root.lightMode ? 0.68 : 0.58
    }

    Rectangle {
        anchors.fill: parent
        radius: root.cornerRadius
        border.width: 1
        border.color: root.lightMode ? "#526B94A7" : "#2E73E4FF"

        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: root.lightMode ? "#D9FFFFFF" : "#AD071422"
            }
            GradientStop {
                position: 0.50
                color: root.lightMode ? "#C8F2F8FB" : "#9E05111D"
            }
            GradientStop {
                position: 1.0
                color: root.lightMode ? "#BDE6F1F7" : "#8F030B14"
            }
        }
        opacity: root.lightMode ? root.lightOpacity : root.darkOpacity
    }

    // Inner optical rim: two very fine layers make the material read as
    // curved glass instead of a translucent painted rectangle.
    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: Math.max(0, root.cornerRadius - 1)
        color: "transparent"
        border.width: 1
        border.color: root.lightMode ? "#72FFFFFF" : "#12FFFFFF"
    }

    Canvas {
        id: liquidSpecular
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var c = getContext("2d")
            c.clearRect(0, 0, width, height)
            c.save()

            // Canvas is rectangular by default. Clip every optical layer to
            // the exact same rounded silhouette as the glass body so no
            // square glow remains visible behind dock/composer corners.
            var cr = Math.max(0, Math.min(root.cornerRadius, Math.min(width, height) * 0.5))
            c.beginPath()
            c.moveTo(cr, 0)
            c.lineTo(width - cr, 0)
            c.quadraticCurveTo(width, 0, width, cr)
            c.lineTo(width, height - cr)
            c.quadraticCurveTo(width, height, width - cr, height)
            c.lineTo(cr, height)
            c.quadraticCurveTo(0, height, 0, height - cr)
            c.lineTo(0, cr)
            c.quadraticCurveTo(0, 0, cr, 0)
            c.closePath()
            c.clip()

            var gx = width * root.lensX
            var gy = height * root.lensY
            var r = Math.max(width, height) * 0.78

            var g = c.createRadialGradient(gx, gy, 0, gx, gy, r)
            if (root.lightMode) {
                g.addColorStop(0.00, "rgba(255,255,255,0.58)")
                g.addColorStop(0.20, "rgba(135,231,244,0.18)")
                g.addColorStop(0.46, "rgba(88,185,255,0.07)")
                g.addColorStop(1.00, "rgba(88,185,255,0)")
            } else {
                g.addColorStop(0.00, "rgba(132,237,255,0.21)")
                g.addColorStop(0.22, "rgba(88,185,255,0.075)")
                g.addColorStop(0.44, "rgba(88,185,255,0)")
                g.addColorStop(1.00, "rgba(88,185,255,0)")
            }

            c.fillStyle = g
            c.fillRect(0, 0, width, height)

            var vg = c.createRadialGradient(width*0.50, height*0.88, 0,
                                            width*0.50, height*0.88,
                                            Math.max(width,height)*0.45)
            vg.addColorStop(0.0, root.lightMode
                            ? "rgba(102,156,199,0.045)"
                            : "rgba(173,110,255,0.09)")
            vg.addColorStop(1.0, "rgba(173,110,255,0)")
            c.fillStyle = vg
            c.fillRect(0, 0, width, height)

            var top = c.createLinearGradient(0,0,0,height*0.36)
            top.addColorStop(0, root.lightMode
                             ? "rgba(255,255,255,0.54)"
                             : "rgba(255,255,255,0.052)")
            top.addColorStop(1, "rgba(255,255,255,0)")
            c.fillStyle = top
            c.fillRect(0,0,width,height*0.36)
            c.restore()
        }

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        Connections {
            target: root
            function onLightModeChanged() { liquidSpecular.requestPaint() }
            function onLensXChanged() { liquidSpecular.requestPaint() }
            function onLensYChanged() { liquidSpecular.requestPaint() }
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: root.cornerRadius * 0.82
        anchors.rightMargin: root.cornerRadius * 0.82
        height: 1
        color: "white"
        opacity: root.lightMode ? 0.72 : 0.07
    }
}
