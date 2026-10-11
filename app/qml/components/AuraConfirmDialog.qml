import QtQuick
Rectangle {
 id:root; property string title:"Confirmer"; property string message:""; property string confirmLabel:"CONFIRMER"; property string cancelLabel:"ANNULER"; property bool lightMode:false; property bool dangerMode:false; signal confirmed(); signal cancelled()
 anchors.fill:parent; color:"#88000000"; visible:false; z:200
 Rectangle{width:380;height:190;anchors.centerIn:parent;radius:18;color:lightMode?"#F5FAFC":"#F20B1728";border.width:1;border.color:dangerMode?"#D77A8A":"#397BE8F5"
  Column{anchors.fill:parent;anchors.margins:20;spacing:12
   Text{text:root.title;color:lightMode?"#17394D":"#D7F5FF";font.pixelSize:14;font.bold:true}
   Text{width:parent.width;text:root.message;wrapMode:Text.WordWrap;color:lightMode?"#607582":"#91A6B5";font.pixelSize:10}
   Row{spacing:10;anchors.right:parent.right
    AuraButton{width:100;lightMode:root.lightMode;text:root.cancelLabel;onClicked:{root.visible=false;root.cancelled()}}
    AuraButton{width:112;lightMode:root.lightMode;variant:root.dangerMode?"danger":"primary";text:root.confirmLabel;onClicked:{root.visible=false;root.confirmed()}}
   }
  }
 }
}
