import QtQuick
import QtQuick.Controls
Rectangle {
 id:root
 objectName: "providerModelSelector_" + providerId
 property string providerId:""
 property string selectedModel:""
 property var models:[]
 property bool lightMode:false
 property string refreshState:"idle"
 property bool staleModel: refreshState==="success" && selectedModel.length>0 && models.every(function(m){return m.model_id!==selectedModel})
 property bool catalogError: refreshState==="error"
 signal modelChosen(string modelId)
 signal refreshRequested()
 width:parent?parent.width:300; height:84; radius:10; color:lightMode?"#EAF7FA":"#182A39"; border.color:"#3272D3E5"
 Column{anchors.fill:parent;anchors.margins:8;spacing:5
  Row{width:parent.width;spacing:6
   Text{width:parent.width-92;text:root.selectedModel.length?root.selectedModel:"Choisissez un modèle";color:root.staleModel?"#F2C27B":(root.lightMode?"#123A4A":"#D7F5FF");elide:Text.ElideRight}
   Rectangle{width:86;height:24;radius:7;color:"#205C91A8"
    Text{anchors.centerIn:parent;text:"CHOISIR";color:"#D7F5FF";font.pixelSize:9}
    MouseArea{anchors.fill:parent;onClicked:popup.open()}
   }
  }
  Text{visible:root.catalogError;text:"⚠ IMPOSSIBLE D’ACTUALISER LES MODÈLES";color:"#F2C27B";font.pixelSize:9}
  Text{visible:!root.catalogError&&root.staleModel;text:"⚠ MODÈLE INDISPONIBLE";color:"#F2C27B";font.pixelSize:9}
  Row{spacing:8
   Text{text:root.models.length+" modèles";color:root.lightMode?"#607582":"#91A6B5";font.pixelSize:9}
   AuraButton{objectName:"providerModelRefreshButton_"+root.providerId;width:112;height:26;lightMode:root.lightMode;variant:"secondary";text:root.refreshState==="loading"?"ACTUALISATION...":"ACTUALISER";enabled:root.refreshState!=="loading";onClicked:root.refreshRequested()}
  }
 }
 Popup{id:popup;objectName:"providerModelPopup_"+root.providerId;width:Math.min(Math.max(root.width,380),460);height:Math.min(500,130+root.models.length*58);modal:true;focus:true;property string filter:"";closePolicy:Popup.CloseOnEscape|Popup.CloseOnPressOutside
  background:Rectangle{radius:16;color:"#102333F5";border.width:1;border.color:"#55D9F5"}
  Column{anchors.fill:parent;anchors.margins:10;spacing:7
   Text{text:"CHOISIR UN MODÈLE";color:"#D7F5FF";font.bold:true;font.pixelSize:13}
   Text{text:root.providerId.toUpperCase();color:"#72DDF5";font.pixelSize:9}
   AuraTextField{objectName:"providerModelSearchField_"+root.providerId;width:parent.width;placeholderText:"Rechercher un modèle...";onTextChanged:popup.filter=text}
   Text{visible:root.models.length===0;text:"Aucun modèle correspondant";color:"#91AFC0";font.pixelSize:10}
   ListView{objectName:"providerModelList_"+root.providerId;width:parent.width;height:parent.height-100;clip:true;spacing:4;model:root.models
    delegate:Rectangle{width:ListView.view.width;height:50;radius:9;color:rowMouse.pressed?"#276D86":(rowMouse.containsMouse?"#1E4D63":"#162F40");border.width:1;border.color:modelData.model_id===root.selectedModel?"#55D9F5":"#2D5265";visible:{var q=popup.filter.toLowerCase();return !q||String(modelData.model_id).toLowerCase().indexOf(q)>=0||String(modelData.display_name).toLowerCase().indexOf(q)>=0}
     Column{anchors.left:parent.left;anchors.leftMargin:12;anchors.verticalCenter:parent.verticalCenter;spacing:2
      Text{text:modelData.display_name;color:"#D7F5FF";font.bold:true;font.pixelSize:10}
      Text{text:modelData.model_id;color:"#91B4C4";font.pixelSize:9}
     }
     Text{anchors.right:parent.right;anchors.rightMargin:12;anchors.verticalCenter:parent.verticalCenter;visible:modelData.model_id===root.selectedModel;text:"ACTIF";color:"#55D9F5";font.pixelSize:8}
     MouseArea{id:rowMouse;anchors.fill:parent;hoverEnabled:true;onClicked:{root.modelChosen(modelData.model_id);popup.close()}}
    }
    ScrollBar.vertical:ScrollBar{policy:ScrollBar.AsNeeded
     contentItem:Rectangle{implicitWidth:5;radius:3;color:"#55D9F5"}
     background:Rectangle{color:"#142A38"}
    }
   }
  }
 }
 Connections{target:coreBridge
  function onProviderModelsRefreshStarted(providerId){if(providerId===root.providerId)root.refreshState="loading"}
  function onProviderModelsRefreshFinished(providerId,values,metadata){if(providerId===root.providerId){root.refreshState=metadata.status==="success"?"success":"error";root.models=values}}
 }
}
