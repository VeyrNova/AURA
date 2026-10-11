import QtQuick

GlassPanel {
    id:root
    property bool lightMode:false
    property color text0:lightMode?"#15394F":"#AEEEFF"
    property color text1:lightMode?"#5B788B":"#587588"
    radius:16;accent:"#74EFFF"

    Rectangle{
        visible:root.lightMode
        anchors.fill:parent
        anchors.margins:1
        radius:15
        gradient:Gradient{
            GradientStop{position:0;color:"#FCFEFFFF"}
            GradientStop{position:1;color:"#E8F3F9FF"}
        }
        border.width:1
        border.color:"#355B91A4"
    }

    Column{
        anchors.fill:parent;anchors.margins:17;spacing:0
        Row{
            width:parent.width;height:33
            Text{text:"SYSTEM LIVE";color:root.lightMode?"#15394F":"#D8F7FF";font.pixelSize:9;font.letterSpacing:2}
            Item{width:Math.max(4,parent.width-172);height:1}
            Text{text:"v1.3.0 NATIVE · FIX5";color:root.text1;font.pixelSize:7;font.letterSpacing:1.1}
        }
        Rectangle{width:parent.width;height:1;color:root.lightMode?"#247A9CB3":"#1673E4FF"}
        Repeater{
            model:[
                ["DISPLAY GPU",bridge.backendLabel,"Qt Quick RHI · shell"],
                ["ORB RENDERER","QPAINTER P0436","LCG exact · 348 / 860"],
                ["VOICE RUNTIME","CAMILLA · OFFLINE","Bridge Core non connecté"],
                ["INTELLIGENCE","GROQ + GEMINI","Cloud route placeholder"],
                ["EVENT LINK","LOCAL READY","QML lifecycle"]
            ]
            delegate:Item{
                required property var modelData;width:parent.width;height:59
                Column{
                    anchors.verticalCenter:parent.verticalCenter;spacing:3
                    Text{text:modelData[0];color:root.lightMode?"#2C6885":"#4D6F84";font.pixelSize:7;font.letterSpacing:1.8}
                    Text{text:modelData[1];color:root.text0;font.pixelSize:11;font.weight:Font.Medium;width:root.width-34;elide:Text.ElideRight}
                    Text{text:modelData[2];color:root.text1;font.pixelSize:8}
                }
            }
        }
        Rectangle{width:parent.width;height:1;color:root.lightMode?"#247A9CB3":"#1673E4FF"}
        Item{
            width:parent.width;height:78
            Text{x:0;y:10;text:"LIVE PCM";color:root.text1;font.pixelSize:7;font.letterSpacing:1.7}
            Text{anchors.right:parent.right;y:10;text:bridge.state==="SPEAKING"?"0.42":bridge.state==="LISTENING"?"0.10":"0.00";color:"#82E9FF";font.pixelSize:8}
            Rectangle{
                anchors.left:parent.left;anchors.right:parent.right;anchors.bottom:parent.bottom;height:1
                color:"#74EFFF";opacity: bridge.state === "SPEAKING" ? .65 : .24
            }
        }
        Rectangle{
            width:parent.width;height:64;radius:9
            color:root.lightMode?"#99ECF6FA":"#8F04111C";border.width:1;border.color:root.lightMode?"#247A9CB3":"#1273E4FF"
            Row{
                anchors.fill:parent;anchors.margins:9;spacing:8
                Text{text:"◆";color:"#69DFFF";font.pixelSize:10}
                Text{width:parent.width-30;text:"LOCAL CONTROL\nP0436 peint via QPainter; Chromium absent.";color:root.text1;font.pixelSize:7;lineHeight:1.4;wrapMode:Text.WordWrap}
            }
        }
    }
}
