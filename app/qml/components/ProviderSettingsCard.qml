import QtQuick
Rectangle {
 id:root; property var providerData:({}); property bool lightMode:false; property string testState:"idle"; property string testMessage:""
 property string testStatus:""
 function statusLabel(s){return {authentication_failed:"⚠ CLÉ API INVALIDE",permission_denied:"⚠ ACCÈS REFUSÉ",rate_limited:"⚠ LIMITE API ATTEINTE",network_error:"⚠ ERREUR RÉSEAU",timeout:"⚠ DÉLAI DÉPASSÉ",provider_unavailable:"⚠ SERVICE INDISPONIBLE",invalid_configuration:"⚠ CONFIGURATION INVALIDE",invalid_response:"⚠ RÉPONSE API INVALIDE",unknown_error:"⚠ ERREUR DE CONNEXION"}[s]||"⚠ ERREUR DE CONNEXION"}
 Timer{id:testWatchdog;interval:15000;repeat:false;onTriggered:if(root.testState==="testing"){root.testState="error";root.testMessage="Le test de connexion a expiré"}}
 signal editSecret(string id,string name); signal removeSecret(string id); signal activate(string id,string model); signal saveLocal(string id,string model,string url); signal testProvider(string id)
 width:parent?parent.width:360; height:providerData.provider_id==="ollama"||providerData.provider_id==="custom_openai"?236:208; radius:14; color:lightMode?"#EAF7FA":"#B30A1A2B"; border.width:1; border.color:"#3272D3E5"
 Column{anchors.fill:parent;anchors.margins:12;spacing:6
  Row{width:parent.width;spacing:8
   Text{text:String(root.providerData.display_name||"").toUpperCase();color:lightMode?"#24495B":"#D7F5FF";font.bold:true;font.pixelSize:12}
   Text{text:root.providerData.provider_id==="ollama"?"● LOCAL":(root.providerData.configured?"● CONFIGURÉ":"○ NON CONFIGURÉ");color:root.providerData.provider_id==="ollama"?"#55D7A5":(root.providerData.configured?"#55D7A5":"#A1AFC2");font.pixelSize:9}
  }
  Text{width:parent.width;text:root.providerData.provider_id==="openai"?"API OpenAI":root.providerData.provider_id==="anthropic"?"API Anthropic Claude":root.providerData.provider_id==="gemini"?"API IA Gemini · Indépendant de Google Workspace":root.providerData.provider_id==="ollama"?"Modèle local":"Compatible OpenRouter, LM Studio, vLLM";color:lightMode?"#607582":"#91A6B5";font.pixelSize:9;elide:Text.ElideRight}
  ProviderModelSelector{id:modelSelector;width:parent.width;providerId:root.providerData.provider_id;selectedModel:String(root.providerData.selected_model||coreBridge.getProviderSelectedModel(root.providerData.provider_id)||"");lightMode:root.lightMode;models:coreBridge.getProviderModels(root.providerData.provider_id);onModelChosen:function(model){root.activate(root.providerData.provider_id,model)};onRefreshRequested:function(){coreBridge.refreshProviderModels(root.providerData.provider_id)}}
  AuraTextField{id:modelField;width:parent.width;visible:root.providerData.provider_id==="custom_openai";lightMode:root.lightMode;text:String(root.providerData.selected_model||"");placeholderText:"Modèle manuel";onEditingFinished:root.activate(root.providerData.provider_id,modelField.text)}
   AuraTextField{id:urlField;width:parent.width;visible:root.providerData.provider_id==="ollama"||root.providerData.provider_id==="custom_openai";lightMode:root.lightMode;text:String(root.providerData.base_url||"");placeholderText:root.providerData.provider_id==="ollama"?"http://127.0.0.1:11434":"Base URL";onEditingFinished:root.saveLocal(root.providerData.provider_id,modelSelector.selectedModel,text)}
  Row{spacing:7
   AuraButton{width:96;height:26;lightMode:root.lightMode;text:root.testState==="testing"?"TEST EN COURS...":(root.testState==="success"?"✓ CONNEXION RÉUSSIE":(root.testState==="error"?"⚠ RÉESSAYER":"TESTER"));visible:root.providerData.configured||root.providerData.provider_id==="ollama";enabled:root.testState!=="testing";onClicked:root.testProvider(root.providerData.provider_id)}
   Text{visible:root.testState==="error";text:root.statusLabel(root.testStatus);color:"#E6A4B4";font.pixelSize:8}
   Text{visible:root.providerData.configured&&root.providerData.provider_id!=="ollama";text:"••••••••";color:lightMode?"#607582":"#91A6B5";font.pixelSize:10}
   Rectangle{width:112;height:26;radius:8;color:"#17445A";visible:root.providerData.provider_id!=="ollama"
    Text{anchors.centerIn:parent;text:root.providerData.configured?"MODIFIER":"AJOUTER UNE CLÉ";color:"#C8F3FF";font.pixelSize:8}
    MouseArea{anchors.fill:parent;onClicked:root.editSecret(root.providerData.provider_id,root.providerData.display_name)}
   }
   Rectangle{width:92;height:26;radius:8;color:"#205C91A8";visible:root.providerData.provider_id==="ollama"
    Text{anchors.centerIn:parent;text:"ENREGISTRER";color:"#D7F5FF";font.pixelSize:8}
    MouseArea{anchors.fill:parent;onClicked:root.saveLocal(root.providerData.provider_id,modelSelector.selectedModel,urlField.text)}
   }
   Rectangle{width:82;height:26;radius:8;color:"#311D36";visible:root.providerData.configured&&root.providerData.provider_id!=="ollama"
    Text{anchors.centerIn:parent;text:"SUPPRIMER";color:"#F2B7C6";font.pixelSize:8}
    MouseArea{anchors.fill:parent;onClicked:root.removeSecret(root.providerData.provider_id)}
   }
  }
 Text{visible:root.testState!=="idle"&&root.testState!=="testing"&&root.testMessage.length>0;width:parent.width;text:root.testMessage;color:root.lightMode?"#607582":"#91A6B5";font.pixelSize:8;elide:Text.ElideRight}
 Connections{target:coreBridge;function onProviderTestStarted(providerId){if(providerId===root.providerData.provider_id){root.testState="testing";root.testStatus="";root.testMessage="";testWatchdog.restart()}}function onProviderTestFinished(providerId,result){if(providerId===root.providerData.provider_id){if(coreBridge.pcc3DebugEnabled)console.log("PCC3_QML_FINISHED provider="+providerId+" status="+String(result.status||"unknown_error"));if(root.testState==="testing"){testWatchdog.stop();root.testState=result.success?"success":"error";root.testStatus=String(result.status||"");root.testMessage=String(result.message||"")}}}}
 }
}
