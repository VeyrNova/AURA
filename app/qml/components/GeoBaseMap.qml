import QtQuick

Item {
    id: root
    objectName: "geoBaseMap"
    property bool lightMode: false
    property var landPolygons: []
    property var coastlines: []
    property var boundaries: []
    property real centerLatitude: 43.7
    property real centerLongitude: 7.25
    property real spanKm: 600
    property bool showMarker: false
    property var routePoints: []
    property var originCoordinate: []
    property var destinationCoordinate: []
    readonly property int routePointCount: routePoints.length
    readonly property bool routeReady: routePointCount >= 2
    property real markerLatitude: centerLatitude
    property real markerLongitude: centerLongitude
    readonly property int landFeatureCount: landPolygons.length
    readonly property int coastlineFeatureCount: coastlines.length
    readonly property bool geometryReady: mapBaseReady
    readonly property int geometryCount: landPolygons.length + coastlines.length + boundaries.length
    readonly property bool mapBaseReady: landPolygons.length > 0 && coastlines.length > 0
    onLandPolygonsChanged: base.requestPaint()
    onCoastlinesChanged: base.requestPaint()
    onBoundariesChanged: base.requestPaint()
    onCenterLatitudeChanged: { base.requestPaint(); routeLayer.requestPaint() }
    onCenterLongitudeChanged: { base.requestPaint(); routeLayer.requestPaint() }
    onSpanKmChanged: { base.requestPaint(); routeLayer.requestPaint() }
    onWidthChanged: { base.requestPaint(); routeLayer.requestPaint() }
    onHeightChanged: { base.requestPaint(); routeLayer.requestPaint() }
    onLightModeChanged: base.requestPaint()
    onRoutePointsChanged: routeLayer.requestPaint()

    Rectangle { anchors.fill: parent; color: root.lightMode ? "#B7D5E0" : "#082538" }
    Canvas {
        id: base; anchors.fill: parent; visible: root.mapBaseReady
        function mercatorX(lon) { return (Number(lon) + 180) / 360 }
        function mercatorY(lat) { var r = Math.max(-85, Math.min(85, Number(lat))) * Math.PI / 180; return (1 - Math.log(Math.tan(Math.PI/4 + r/2))/Math.PI)/2 }
        function point(coord) {
            var x0 = mercatorX(root.centerLongitude), y0 = mercatorY(root.centerLatitude)
            var cosLat = Math.max(.1, Math.abs(Math.cos(root.centerLatitude*Math.PI/180)))
            var worldWidth = root.spanKm / (40075.016686*cosLat)
            return {x: width * (.5 + (mercatorX(coord[0])-x0)/worldWidth),
                    y: height*.5 + width*(mercatorY(coord[1])-y0)/worldWidth}
        }
        function trace(ctx, lines, close) {
            for (var i=0; i<lines.length; i++) {
                var line=lines[i]; if (!line || line.length<2) continue
                var p=point(line[0]); ctx.moveTo(p.x,p.y)
                for (var j=1;j<line.length;j++) { p=point(line[j]); ctx.lineTo(p.x,p.y) }
                if (close) ctx.closePath()
            }
        }
        onPaint: {
            var c=getContext("2d"); c.clearRect(0,0,width,height)
            if (!root.mapBaseReady) return
            c.beginPath(); trace(c,root.landPolygons,true); c.fillStyle=root.lightMode?"#D7E2DA":"#173A38"; c.fill()
            c.beginPath(); trace(c,root.coastlines,false); c.strokeStyle=root.lightMode?"#537D81":"#72B9BA"; c.lineWidth=1.6; c.stroke()
            c.beginPath(); trace(c,root.boundaries,false); c.strokeStyle=root.lightMode?"#91A9A4":"#45696D"; c.lineWidth=.7; c.stroke()
        }
    }
    Canvas {
        id: routeLayer; objectName: "geoRouteLayer"; anchors.fill: parent; visible: root.routeReady
        onPaint: {
            var c=getContext("2d"); c.clearRect(0,0,width,height)
            if (!root.routeReady) return
            c.beginPath()
            for (var i=0;i<root.routePoints.length;i++) {
                var p=base.point(root.routePoints[i])
                if (i===0) c.moveTo(p.x,p.y); else c.lineTo(p.x,p.y)
            }
            c.strokeStyle=root.lightMode?"#D9FFFFFF":"#B8002638"; c.lineWidth=8; c.lineJoin="round"; c.stroke()
            c.strokeStyle="#67E8FA"; c.lineWidth=3.5; c.stroke()
        }
    }
    Rectangle { objectName: "geoOriginMarker"; visible: root.routeReady && root.originCoordinate.length===2; width: 22; height: 22; radius: 11; color: "#28A8C2"; border.width: 2; border.color: "#D6FBFF";
        x: base.point(root.originCoordinate).x-width/2; y: base.point(root.originCoordinate).y-height/2
        Text { anchors.centerIn: parent; text: "A"; color: "#FFFFFF"; font.pixelSize: 11; font.bold: true }
    }
    Rectangle { objectName: "geoDestinationMarker"; visible: root.routeReady && root.destinationCoordinate.length===2; width: 22; height: 22; radius: 11; color: "#176C9C"; border.width: 2; border.color: "#D6FBFF";
        x: base.point(root.destinationCoordinate).x-width/2; y: base.point(root.destinationCoordinate).y-height/2
        Text { anchors.centerIn: parent; text: "B"; color: "#FFFFFF"; font.pixelSize: 11; font.bold: true }
    }
    Text { anchors.centerIn: parent; visible: !root.mapBaseReady; width: Math.min(parent.width-30,360); horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
        text: "FOND CARTOGRAPHIQUE LOCAL INDISPONIBLE\nAjoutez des données géographiques vectorielles au workspace."; color: root.lightMode?"#365568":"#B7D7E0"; font.pixelSize: 11 }
    Rectangle { visible: root.showMarker && root.mapBaseReady; x: base.point([root.markerLongitude, root.markerLatitude]).x-width/2; y: base.point([root.markerLongitude, root.markerLatitude]).y-height/2; width: 15; height: 15; radius: 8; color: "#74EFFF"; border.width: 2; border.color: "#163846" }
}
