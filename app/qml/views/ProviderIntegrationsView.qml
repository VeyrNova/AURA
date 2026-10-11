import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import "../components"
Item { id:root; property bool lightMode:false; property var bridge:coreBridge
 Rectangle{anchors.fill:parent;color:"transparent"}
 Flickable{anchors.fill:parent;contentWidth:width;contentHeight:column.implicitHeight+32;clip:true
  Column{id:column;x:12;y:12;width:Math.max(300,parent.width-24);spacing:12
   Text{text:"IA & INTÉGRATIONS";color:lightMode?"#24495B":"#D7F5FF";font.pixelSize:20;font.bold:true}
   Text{width:parent.width;text:"Configurez les moteurs d’intelligence artificielle et les services connectés à AURA.";wrapMode:Text.WordWrap;color:lightMode?"#607582":"#91A6B5";font.pixelSize:11}
   Rectangle{width:parent.width;height:84;radius:14;color:lightMode?"#DFFFFFFF":"#8A0B1A2B";border.width:1;border.color:"#3272D3E5"
    Row{anchors.fill:parent;anchors.margins:12;spacing:14
     Column{width:parent.width-150;spacing:4
      Text{text:"FOURNISSEUR PRINCIPAL";color:"#65DDF5";font.pixelSize:9}
      Text{text:bridge.activeProvider||"Sélectionner un fournisseur";color:lightMode?"#24495B":"#D7F5FF";font.pixelSize:13;font.bold:true}
      Text{text:bridge.activeModel||"Modèle non défini";color:lightMode?"#607582":"#91A6B5";font.pixelSize:9}
     }
     Rectangle{width:120;height:34;radius:9;color:lightMode?"#C9F2FF":"#205C91A8"
      Text{anchors.centerIn:parent;text:"CHOISIR";color:lightMode?"#123A4A":"#D7F5FF";font.pixelSize:9}
      MouseArea{anchors.fill:parent;onClicked:providerSelector.visible=!providerSelector.visible}
     }
    }
   }
   Repeater{model:bridge.providerConfigs;delegate:ProviderSettingsCard{providerData:modelData;lightMode:root.lightMode;onEditSecret:function(id,name){dialog.providerId=id;dialog.providerName=name;dialog.visible=true};onRemoveSecret:function(id){confirm.providerId=id;confirm.providerName=modelData.display_name;confirm.visible=true};onActivate:function(id,model){bridge.setActiveModel(id,model)};onSaveLocal:function(id,model,url){bridge.setActiveModel(id,model);bridge.setProviderBaseUrl(id,url)};onTestProvider:function(id){bridge.testProviderConnection(id)}}}
   Text{text:"GOOGLE WORKSPACE";color:lightMode?"#24495B":"#D7F5FF";font.pixelSize:13;font.bold:true}
   Text{width:parent.width;text:"Calendar et Tasks utilisent une connexion Google OAuth séparée.\nSélection du client OAuth et connexion disponibles dans une étape dédiée.";wrapMode:Text.WordWrap;color:lightMode?"#607582":"#91A6B5";font.pixelSize:10}
   Rectangle{width:parent.width;height:148;radius:12;color:lightMode?"#DFFFFFFF":"#8A0B1A2B";border.width:1;border.color:"#3272D3E5"
    Column{anchors.fill:parent;anchors.margins:12;spacing:8
     Row{width:parent.width;spacing:10
      Column{width:parent.width;spacing:3
       Text{text:"CLIENT OAUTH";color:lightMode?"#24495B":"#D7F5FF";font.pixelSize:10;font.bold:true}
       Text{text:bridge.googleOAuthClientStatus.configured?"● Configuré":"● Non configuré";color:bridge.googleOAuthClientStatus.configured?"#55D7A5":"#A1AFC2";font.pixelSize:9}
       Text{text:bridge.googleOAuthClientStatus.filename||"Aucun fichier importé";color:lightMode?"#607582":"#91A6B5";font.pixelSize:9}
      }
     }
     Text{width:parent.width;text:"Met à jour les autorisations du compte Google connecté.";wrapMode:Text.WordWrap;color:lightMode?"#607582":"#91A6B5";font.pixelSize:9}
     Flow{width:parent.width;spacing:8
      AuraButton{objectName:"nativeGoogleReauthorize";width:172;height:36;lightMode:root.lightMode;variant:"primary";text:bridge.googleWorkspaceStatus === "connecting" ? "AUTORISATION EN COURS…" : "RÉAUTORISER GOOGLE";enabled:bridge.googleWorkspaceStatus !== "connecting";onClicked:bridge.startGoogleWorkspaceOAuth()}
      AuraButton{width:172;height:36;lightMode:root.lightMode;variant:"secondary";text:bridge.googleOAuthClientStatus.configured ? "CHANGER LE CLIENT OAUTH" : "IMPORTER UN CLIENT OAUTH";onClicked:oauthDialog.open()}
     }
    }
   }
   Rectangle{width:parent.width;height:66;radius:12;color:lightMode?"#DFFFFFFF":"#8A0B1A2B";border.width:1;border.color:"#3272D3E5"
    Row{anchors.fill:parent;anchors.margins:10;spacing:12
     Column{width:parent.width-150;spacing:3
      Text{text:"LANGUE / LANGUAGE";color:lightMode?"#24495B":"#D7F5FF";font.pixelSize:10;font.bold:true}
      Text{text:coreBridge.locale === "en-US" ? "English" : "Français";color:lightMode?"#607582":"#91A6B5";font.pixelSize:9}
     }
     Row{spacing:6
      Repeater{model:[["FR","fr-FR"],["EN","en-US"]]
       delegate:Rectangle{objectName:"nativeLocale-"+modelData[1];width:54;height:32;radius:9;color:coreBridge.locale===modelData[1]?(lightMode?"#C9F2FF":"#205C91A8"):(lightMode?"#EFF7FA":"#40112130");border.color:"#55D9F5"
        Text{anchors.centerIn:parent;text:modelData[0];color:lightMode?"#123A4A":"#D7F5FF";font.pixelSize:9}
        MouseArea{anchors.fill:parent;onClicked:coreBridge.setLocale(modelData[1])}
       }
      }
     }
    }
   }
  }
 }
 ProviderSelectorPopup{id:providerSelector;providerModel:bridge.providerConfigs;activeProvider:bridge.activeProvider;lightMode:root.lightMode;onSelected:function(id){bridge.setActiveProvider(id);visible=false};onDismissed:visible=false}
 ProviderSecretDialog{id:dialog;anchors.centerIn:parent;visible:false;onSaved:function(id,secret){bridge.saveProviderSecret(id,secret);visible=false};onCancelled:visible=false}
 AuraConfirmDialog{id:confirm;property string providerId:"";property string providerName:"";title:"SUPPRIMER LA CLÉ "+providerName+" ?";message:"Cette action supprimera la clé API enregistrée pour ce fournisseur. Le modèle et les autres réglages seront conservés.";confirmLabel:"SUPPRIMER";lightMode:root.lightMode;dangerMode:true;onConfirmed:bridge.removeProviderSecret(providerId)}
 FileDialog{id:oauthDialog;title:"Sélectionner le client OAuth Google";nameFilters:["JSON (*.json)"];fileMode:FileDialog.OpenFile;onAccepted:bridge.importGoogleOAuthClient(selectedFile.toString().replace("file:///",""))}
}
