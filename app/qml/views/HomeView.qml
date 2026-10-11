import QtQuick
import "../components"

Item {
    id: root
    property bool lightMode: false
    property bool foregroundHome: true
    property string heroDateText: ""

    function updateHeroDate() {
        var d = new Date()
        var days = ["DIMANCHE","LUNDI","MARDI","MERCREDI","JEUDI","VENDREDI","SAMEDI"]
        var months = ["JANVIER","FÉVRIER","MARS","AVRIL","MAI","JUIN","JUILLET","AOÛT","SEPTEMBRE","OCTOBRE","NOVEMBRE","DÉCEMBRE"]
        heroDateText = days[d.getDay()] + " "
                     + String(d.getDate()).padStart(2,"0") + " "
                     + months[d.getMonth()] + " " + d.getFullYear()
    }

    Component.onCompleted: updateHeroDate()
    Timer { interval: 30000; repeat: true; running: true; onTriggered: root.updateHeroDate() }

    Rectangle {
        id: hero
        anchors.fill: parent
        radius: 16
        color: root.lightMode ? "#FBFDFD" : "#010710"
        border.width: 1
        border.color: root.lightMode ? "#25388898" : "#1264C7DA"
        clip: true

        Canvas {
            visible: root.lightMode
            anchors.fill: parent
            antialiasing: true
            onPaint: {
                var c=getContext("2d")
                c.clearRect(0,0,width,height)
                var cx=width*.50,cy=height*.45
                var radius=Math.sqrt(width*width+height*height)*.58
                var g=c.createRadialGradient(cx,cy,Math.min(width,height)*.035,cx,cy,radius)
                g.addColorStop(0.00,"rgba(121,207,216,.28)")
                g.addColorStop(0.26,"rgba(159,221,228,.31)")
                g.addColorStop(0.44,"rgba(199,234,238,.42)")
                g.addColorStop(0.62,"rgba(229,246,248,.78)")
                g.addColorStop(0.80,"rgba(247,252,253,.97)")
                g.addColorStop(1.00,"#fbfdfd")
                c.fillStyle=g;c.fillRect(0,0,width,height)
            }
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
        }

        Rectangle {
            visible: !root.lightMode
            anchors.fill: parent
            radius: 15
            gradient: Gradient {
                GradientStop { position: 0.00; color: "#050C15" }
                GradientStop { position: 0.36; color: "#020914" }
                GradientStop { position: 0.70; color: "#010710" }
                GradientStop { position: 1.00; color: "#01050C" }
            }
        }

        // AURA_ORB_CLEANUP_FIX5
        // External bloom, side guides and straight center guide intentionally removed.

        AuraOrbP0436 {
            anchors.fill: parent
            lightMode: root.lightMode
            state: bridge.state
            targetFps: bridge.orbTargetFps
            pcmLevel: coreBridge.voiceAmplitude
            opacity: root.foregroundHome ? 1.0 : 0.60
        }

        Column {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.leftMargin: 22
            anchors.topMargin: 25
            spacing: 4

            Text {
                text: "NEURAL CORE"
                color: root.lightMode ? "#5C7989" : "#617D8E"
                font.pixelSize: 7
                font.letterSpacing: 2.1
            }
            Text {
                text: bridge.state
                color: root.lightMode ? "#173B50" : "#E8F8FC"
                font.pixelSize: 15
                font.weight: Font.DemiBold
                font.letterSpacing: 2.4
            }
            Text {
                text: runtimeMode === "native" ? "Conversation locale · available · Assistant not_migrated" : (coreBridge.connected ? "Runtime v2 online" : "Runtime v2 handshake")
                color: root.lightMode ? "#667E8C" : "#617D8E"
                font.pixelSize: 8
            }
            Rectangle {
                width: 66; height: 1
                color: root.lightMode ? "#2D5D8192" : "#3366CBDD"
                opacity: .50
            }
        }

        Column {
            visible: root.foregroundHome
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.rightMargin: 31
            anchors.topMargin: 28
            spacing: 1

            Text {
                anchors.right: parent.right
                text: "AURA"
                color: root.lightMode ? "#141D5268" : "#0C8EB4C4"
                font.pixelSize: 44
                font.weight: Font.Bold
                font.letterSpacing: 8.5
            }
            Text {
                anchors.right: parent.right
                text: bridge.clockText.split(" · ")[0]
                color: root.lightMode ? "#17394D" : "#E8F7FB"
                font.pixelSize: 31
                font.weight: Font.DemiBold
                font.letterSpacing: .5
            }
            Text {
                anchors.right: parent.right
                text: root.heroDateText
                color: root.lightMode ? "#5C7584" : "#607B8A"
                font.pixelSize: 6
                font.letterSpacing: 2.0
            }
        }
    }
}
