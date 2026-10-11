import QtQuick
Item {
 id:root; property var providerModel:[]; property bool lightMode:false; property string activeProvider:""; signal selected(string providerId); signal dismissed()
 anchors.fill:parent; visible:false; z:150
 MouseArea{anchors.fill:parent;onClicked:root.dismissed()}
 Rectangle{id:panel;width:Math.min(360,Math.max(300,parent.width-24));height:Math.min(parent.height-24,providerModel.length*58+20);anchors.top:parent.top;anchors.right:parent.right;anchors.topMargin:94;anchors.rightMargin:12;radius:16;color:root.lightMode?"#F5FAFC":"#F20B1728";border.width:1;border.color:"#55D9F5"
  Column{anchors.fill:parent;anchors.margins:10;spacing:4
   Repeater{model:root.providerModel;delegate:Rectangle{width:parent.width;height:50;radius:10;opacity:(modelData.configured||modelData.provider_id==="ollama")?1:.56;color:rowMouse.containsMouse?(root.lightMode?"#D9F2F7":"#28506A7A"):(modelData.provider_id===root.activeProvider?(root.lightMode?"#D4F4F8":"#254A7480"):"transparent");border.width:modelData.provider_id===root.activeProvider?1:0;border.color:"#55D9F5"
    Column{anchors.left:parent.left;anchors.right:status.left;anchors.verticalCenter:parent.verticalCenter;anchors.leftMargin:10;spacing:2
     Text{width:parent.width;text:String(modelData.display_name||"").toUpperCase();color:root.lightMode?"#17394D":"#D7F5FF";font.pixelSize:10;font.bold:true;elide:Text.ElideRight}
     Text{width:parent.width;text:String(modelData.selected_model||modelData.base_url||"");visible:text.length>0;color:root.lightMode?"#607582":"#91A6B5";font.pixelSize:8;elide:Text.ElideRight}
    }
    Text{id:status;anchors.right:parent.right;anchors.rightMargin:10;anchors.verticalCenter:parent.verticalCenter;text:modelData.provider_id==="ollama"?"● LOCAL":(modelData.configured?"● CONFIGURÉ":"○ NON CONFIGURÉ");color:modelData.configured||modelData.provider_id==="ollama"?"#55D7A5":"#A1AFC2";font.pixelSize:8}
    MouseArea{id:rowMouse;anchors.fill:parent;hoverEnabled:true;enabled:modelData.configured||modelData.provider_id==="ollama";onClicked:{root.selected(modelData.provider_id);root.visible=false}}
   }}
  }
 }
}
