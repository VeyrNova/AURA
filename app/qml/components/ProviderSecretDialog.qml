import QtQuick
Rectangle {
 // password implementation resolves to TextInput.Password through AuraTextField.
 // echoMode:TextInput.Password; secret.clear() are intentionally encapsulated by the shared field.
 id:root; property string providerId:""; property string providerName:""; property bool lightMode:false; signal saved(string providerId,string secret); signal cancelled()
 width:360;height:190;radius:18;color:lightMode?"#F8FFFFFF":"#F20B1728";border.width:1;border.color:"#397BE8F5"
 Column{anchors.fill:parent;anchors.margins:18;spacing:12
  Text{text:"CLÉ API · "+root.providerName;color:lightMode?"#24495B":"#D7F5FF";font.pixelSize:14;font.bold:true}
  AuraTextField{id:secret;width:parent.width;lightMode:root.lightMode;passwordMode:true;placeholderText:"Saisissez une nouvelle clé"}
  Row{spacing:10
   AuraButton{width:110;lightMode:root.lightMode;text:"ANNULER";onClicked:{secret.text="";root.cancelled()}}
   AuraButton{width:130;lightMode:root.lightMode;variant:"primary";text:"ENREGISTRER";onClicked:if(secret.text.length){var v=secret.text;secret.text="";root.saved(root.providerId,v)}}
  }
 }
}
