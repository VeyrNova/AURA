import QtQuick
import Aura.Native 1.0

Item {
    id:root
    property bool lightMode:false
    property string state:"IDLE"
    property int targetFps:40
    property real pcmLevel:0.0

    NeuralOrbItem {
        id:renderer
        anchors.fill:parent
        state:root.state
        lightMode:root.lightMode
        targetFps:root.targetFps
        pcmLevel:root.pcmLevel
    }

    Image {
        id:lockup
        readonly property real orbRadius:Math.min(root.width,root.height)*.305
        width:orbRadius*.72
        height:width*1.10
        x:root.width*.50-width/2
        y:root.height*.455+orbRadius*.015-height/2
        source: root.lightMode ? auraAssetBase+"AURA_LOGO_LOCKUP_ARCTIC.svg" : auraAssetBase+"AURA_LOGO_LOCKUP_MASTER.svg"
        fillMode:Image.PreserveAspectFit
        mipmap:true
        opacity:.98
        scale:1.0

        SequentialAnimation on scale{
            running:true;loops:Animation.Infinite
            NumberAnimation{to:root.state==="SPEAKING"?1.026:1.004;duration:780;easing.type:Easing.InOutSine}
            NumberAnimation{to:.998;duration:920;easing.type:Easing.InOutSine}
        }
    }
}
