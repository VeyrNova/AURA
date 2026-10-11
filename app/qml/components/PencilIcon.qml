import QtQuick

Canvas {
    id: root
    implicitWidth: 16
    implicitHeight: 16
    property color iconColor: "#9FEFFF"
    property color detailColor: "#DDFBFF"

    onIconColorChanged: requestPaint()
    onDetailColorChanged: requestPaint()
    Component.onCompleted: requestPaint()

    onPaint: {
        var ctx = getContext("2d")
        ctx.clearRect(0, 0, width, height)
        ctx.save()
        ctx.translate(width / 2, height / 2)
        ctx.rotate(-Math.PI / 4)

        ctx.fillStyle = iconColor
        ctx.fillRect(-5.4, -2.0, 9.2, 4.0)

        ctx.fillStyle = detailColor
        ctx.fillRect(-6.7, -2.0, 1.6, 4.0)

        ctx.beginPath()
        ctx.moveTo(3.8, -2.0)
        ctx.lineTo(6.8, 0.0)
        ctx.lineTo(3.8, 2.0)
        ctx.closePath()
        ctx.fillStyle = iconColor
        ctx.fill()

        ctx.restore()
    }
}
