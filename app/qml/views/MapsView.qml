import QtQuick
import QtQuick.Controls
import "../components"

Item {
    id: root
    property bool lightMode: false
    readonly property color ink: lightMode ? "#17394D" : "#D8F7FF"
    readonly property color muted: lightMode ? "#557487" : "#91ADBC"
    property real zoomKm: 600
    Connections { target: mapsBridge; function onRouteChanged() { if (mapsBridge.routeReady) root.zoomKm = mapsBridge.routeSpanKm } }
    readonly property real mapLat: mapsBridge.routeReady ? mapsBridge.routeCenterLatitude : (mapsBridge.selectedPlace.latitude || 43.7)
    readonly property real mapLon: mapsBridge.routeReady ? mapsBridge.routeCenterLongitude : (mapsBridge.selectedPlace.longitude || 7.25)
    readonly property bool useRegionalGeometry: zoomKm <= 1500 && mapLat >= 30 && mapLat <= 72 && mapLon >= -14 && mapLon <= 38
    readonly property var activeGeometry: useRegionalGeometry ? mapsBridge.geometry : mapsBridge.worldGeometry
    Rectangle { anchors.fill: parent; radius: 18; color: root.lightMode ? "#EAF4F7" : "#06141D"; border.width: 1; border.color: "#2F7793A8" }
    GeoBaseMap {
        id: geo; objectName: "nativeMapsBaseMap"
        anchors.fill: parent; anchors.margins: 18
        lightMode: root.lightMode
        landPolygons: root.activeGeometry.land_polygons || []
        coastlines: root.activeGeometry.coastlines || []
        boundaries: root.activeGeometry.boundaries || []
        centerLatitude: root.mapLat
        centerLongitude: root.mapLon
        spanKm: root.zoomKm
        showMarker: !mapsBridge.routeReady && !!mapsBridge.selectedPlace.name
        markerLatitude: mapsBridge.selectedPlace.latitude || centerLatitude
        markerLongitude: mapsBridge.selectedPlace.longitude || centerLongitude
        routePoints: mapsBridge.routeGeometry
        originCoordinate: mapsBridge.origin.label ? [mapsBridge.origin.longitude, mapsBridge.origin.latitude] : []
        destinationCoordinate: mapsBridge.destination.label ? [mapsBridge.destination.longitude, mapsBridge.destination.latitude] : []
    }
    Rectangle {
        id: searchPanel
        x: 32; y: 32; width: Math.min(450, parent.width - 64); height: mapsBridge.places.length ? 192 : 92
        radius: 16; color: root.lightMode ? "#EFFFFFFF" : "#E60B2230"; border.width: 1; border.color: "#5474DDEA"
        Column { anchors.fill: parent; anchors.margins: 12; spacing: 8
            Text { text: "MAPS · AURA NATIVE"; color: root.ink; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1 }
            Row { width: parent.width; spacing: 8
                Rectangle { width: parent.width - 108; height: 34; radius: 10; color: root.lightMode ? "#F3FAFC" : "#102D3C"; border.width: 1; border.color: "#3C8DA9B9"
                    TextField { id: query; objectName: "nativeMapsSearch"; anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 8; placeholderText: "Rechercher un lieu"; color: root.ink; placeholderTextColor: root.muted; background: null; font.pixelSize: 10; onAccepted: mapsBridge.search(text) }
                }
                AuraButton { width: 100; height: 34; lightMode: root.lightMode; variant: "primary"; text: "RECHERCHER"; onClicked: mapsBridge.search(query.text) }
            }
            Text { visible: mapsBridge.loading || mapsBridge.error.length > 0; text: mapsBridge.loading ? "Recherche en cours…" : mapsBridge.error; color: root.muted; font.pixelSize: 9 }
            ListView { width: parent.width; height: Math.max(0, parent.height - 74); clip: true; model: mapsBridge.places
                delegate: Rectangle { width: parent.width; height: 32; radius: 8; color: placeHover.hovered ? "#275C7588" : "transparent"
                    Text { anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter; text: modelData.name + " · " + modelData.country; color: root.ink; font.pixelSize: 10 }
                    HoverHandler { id: placeHover }
                    TapHandler { onTapped: mapsBridge.select(index) }
                }
            }
        }
    }
    Rectangle {
        id: routePanel; objectName: "nativeRoutePanel"
        anchors.left: searchPanel.left; anchors.top: searchPanel.bottom; anchors.topMargin: 12
        width: searchPanel.width; height: mapsBridge.routeReady ? 344 : 258
        radius: 16; color: root.lightMode ? "#EFFFFFFF" : "#E60B2230"; border.width: 1; border.color: "#5474DDEA"
        Column { anchors.fill: parent; anchors.margins: 12; spacing: 7
            Text { text: "ITINÉRAIRE · VOITURE"; color: root.ink; font.pixelSize: 11; font.weight: Font.DemiBold; font.letterSpacing: 1 }
            Row { width: parent.width; height: 34; spacing: 7
                Text { width: 57; anchors.verticalCenter: parent.verticalCenter; text: "DÉPART"; color: root.muted; font.pixelSize: 9 }
                Rectangle { width: parent.width-146; height: 32; radius: 9; color: root.lightMode ? "#F3FAFC" : "#102D3C"; border.width: 1; border.color: "#3C8DA9B9"
                    TextField { id: originInput; objectName: "nativeRouteOriginInput"; anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 5; background: null; color: root.ink; placeholderTextColor: root.muted; placeholderText: "Ville de départ"; font.pixelSize: 10; onAccepted: mapsBridge.searchOrigin(text) }
                }
                AuraButton { width: 82; height: 32; lightMode: root.lightMode; text: "MA POSITION"; onClicked: mapsBridge.requestCurrentLocation() }
            }
            ListView { objectName: "nativeRouteOriginResults"; width: parent.width; height: mapsBridge.originCandidates.length ? 24 : 0; clip: true; model: mapsBridge.originCandidates
                delegate: Rectangle { width: parent.width; height: 24; radius: 6; color: originHover.hovered ? "#275C7588" : "transparent"
                    Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 7; text: modelData.label; color: root.ink; font.pixelSize: 9; elide: Text.ElideRight; width: parent.width-14 }
                    HoverHandler { id: originHover }
                    TapHandler { onTapped: { originInput.text=modelData.label; mapsBridge.selectOrigin(index) } }
                }
            }
            Text { width: parent.width; visible: mapsBridge.currentLocationState !== "idle" && mapsBridge.currentLocationState !== "ready"; text: mapsBridge.currentLocationLabel; color: root.lightMode ? "#A14149" : "#FFB6BF"; font.pixelSize: 9; wrapMode: Text.WordWrap }
            Row { width: parent.width; height: 34; spacing: 7
                Text { width: 57; anchors.verticalCenter: parent.verticalCenter; text: "ARRIVÉE"; color: root.muted; font.pixelSize: 9 }
                Rectangle { width: parent.width-146; height: 32; radius: 9; color: root.lightMode ? "#F3FAFC" : "#102D3C"; border.width: 1; border.color: "#3C8DA9B9"
                    TextField { id: destinationInput; objectName: "nativeRouteDestinationInput"; anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 5; background: null; color: root.ink; placeholderTextColor: root.muted; placeholderText: "Destination"; font.pixelSize: 10; onAccepted: mapsBridge.searchDestination(text) }
                }
                AuraButton { width: 75; height: 32; lightMode: root.lightMode; text: "CHERCHER"; onClicked: mapsBridge.searchDestination(destinationInput.text) }
            }
            ListView { objectName: "nativeRouteDestinationResults"; width: parent.width; height: mapsBridge.destinationCandidates.length ? 24 : 0; clip: true; model: mapsBridge.destinationCandidates
                delegate: Rectangle { width: parent.width; height: 24; radius: 6; color: destinationHover.hovered ? "#275C7588" : "transparent"
                    Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: 7; text: modelData.label; color: root.ink; font.pixelSize: 9; elide: Text.ElideRight; width: parent.width-14 }
                    HoverHandler { id: destinationHover }
                    TapHandler { onTapped: { destinationInput.text=modelData.label; mapsBridge.selectDestination(index) } }
                }
            }
            Row { width: parent.width; height: 35; spacing: 8
                AuraButton { objectName: "nativeRouteCalculate"; width: 235; height: 35; lightMode: root.lightMode; variant: "primary"; text: mapsBridge.routingState === "routing" ? "CALCUL EN COURS…" : "CALCULER L’ITINÉRAIRE"; enabled: mapsBridge.routingState !== "routing"; onClicked: mapsBridge.calculateRoute() }
                AuraButton { width: 75; height: 35; lightMode: root.lightMode; text: "EFFACER"; onClicked: { mapsBridge.clearRoute(); originInput.text=""; destinationInput.text="" } }
            }
            AuraButton { objectName: "nativeRouteGoogleMaps"; visible: mapsBridge.routeReady; width: parent.width; height: 30; lightMode: root.lightMode; text: "OUVRIR DANS GOOGLE MAPS"; onClicked: mapsBridge.openGoogleMaps() }
            Text { width: parent.width; visible: mapsBridge.routingState === "error"; wrapMode: Text.WordWrap; text: mapsBridge.routingErrorLabel; color: root.lightMode ? "#A14149" : "#FFB6BF"; font.pixelSize: 10 }
            Text { objectName: "nativeRouteMetrics"; visible: mapsBridge.routeReady; text: mapsBridge.routeDistanceLabel + "  ·  " + mapsBridge.routeDurationLabel; color: root.ink; font.pixelSize: 15; font.weight: Font.DemiBold }
            Text { visible: mapsBridge.routeReady && mapsBridge.routeInstructions.length; text: "ÉTAPES PRINCIPALES"; color: root.muted; font.pixelSize: 9 }
            Repeater { model: mapsBridge.routeReady ? Math.min(3,mapsBridge.routeInstructions.length) : 0
                Text { width: routePanel.width-24; elide: Text.ElideRight; text: (index+1) + ". " + mapsBridge.routeInstructions[index]; color: root.ink; font.pixelSize: 9 }
            }
            Text { text: "Calcul en ligne par OSRM · sans trafic temps réel"; color: root.muted; font.pixelSize: 8 }
        }
    }
    Rectangle { visible: !!mapsBridge.selectedPlace.name; anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 32; width: Math.min(340,parent.width-64); height: 44; radius: 12; color: root.lightMode ? "#EDFFFFFF" : "#E60B2230"; border.color: "#5474DDEA"; border.width: 1
        Text { anchors.centerIn: parent; text: mapsBridge.selectedPlace.name || ""; color: root.ink; font.pixelSize: 11 }
    }
    Row { anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 32; spacing: 6
        AuraButton { width: 34; height: 34; lightMode: root.lightMode; text: "+"; onClicked: root.zoomKm = Math.max(80, root.zoomKm / 1.5) }
        AuraButton { width: 34; height: 34; lightMode: root.lightMode; text: "−"; onClicked: root.zoomKm = Math.min(6000, root.zoomKm * 1.5) }
    }
    Text { anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 32; text: "© OpenStreetMap · OSRM   ·   Corriger la carte"; color: root.muted; font.pixelSize: 9
        TapHandler { onTapped: mapsBridge.openMapFix() }
    }
}
