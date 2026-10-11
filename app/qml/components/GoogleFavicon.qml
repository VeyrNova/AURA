import QtQuick

Image {
    id: favicon
    property int iconSize: 14
    width: iconSize
    height: iconSize
    source: "../assets/google_favicon.png"
    fillMode: Image.PreserveAspectFit
    smooth: true
    mipmap: true
    asynchronous: false
}
