import QtQuick
import QtQuick.Controls
import "../components"

Item {
    id: root

    property bool lightMode: false
    property var forecastDays: []
    property var weatherGrid: ({})
    property var terrainGrid: ({})
    property var particles: []
    property string activeLayer: "wind"
    property bool searchOpen: false
    property real phase: 0.0
    property int particleCount: width > 1500 ? 420 : 330
    property int trailLength: 14

    readonly property color bg0: lightMode ? "#E9F3F6" : "#02080E"
    readonly property color bg1: lightMode ? "#DDECF0" : "#031019"
    readonly property color panel: lightMode ? "#F1F8FA" : "#061720"
    readonly property color panelSoft: lightMode ? "#E7F1F4" : "#081D27"
    readonly property color line: lightMode ? "#9CC4CE" : "#1A4D5D"
    readonly property color cyan: "#55E7FA"
    readonly property color cyan2: "#32B9E8"
    readonly property color violet: "#8A5CFF"
    readonly property color textMain: lightMode ? "#153646" : "#EAFBFF"
    readonly property color textSoft: lightMode ? "#4E7180" : "#9BC4D1"
    readonly property color textDim: lightMode ? "#708B97" : "#648A99"

    readonly property var layers: [
        { key: "wind", label: "VENT" },
        { key: "rain", label: "PLUIE" },
        { key: "temperature", label: "TEMP." },
        { key: "clouds", label: "NUAGES" },
        { key: "pressure", label: "PRESSION" }
    ]

    function tempText(v) {
        return Number(v).toFixed(1).replace(".0", "") + "°"
    }

    function forecastSlot(i) {
        if (i >= 0 && i < forecastDays.length && forecastDays[i])
            return forecastDays[i]
        return {
            day: "—",
            date: "",
            label: "",
            icon: "·",
            max: null,
            min: null,
            rain: null
        }
    }

    function syncData() {
        try { forecastDays = JSON.parse(weatherBridge.forecastJson || "[]") }
        catch (e) { forecastDays = [] }

        try { weatherGrid = JSON.parse(weatherBridge.windFieldJson || "{}") }
        catch (e2) { weatherGrid = ({}) }

        try { terrainGrid = JSON.parse(weatherBridge.terrainJson || "{}") }
        catch (e3) { terrainGrid = ({}) }

        initParticles()
        scalarField.requestPaint()
        flowCanvas.requestPaint()
        if (forecastCanvas)
            forecastCanvas.requestPaint()
    }

    function gridSamples() {
        var g = weatherGrid || {}
        if (g.wind_field instanceof Array) return g.wind_field
        if (g.field instanceof Array) return g.field
        if (g.points instanceof Array) return g.points
        if (g.samples instanceof Array) return g.samples
        if (g instanceof Array) return g
        return []
    }

    function gridCols() {
        var g = weatherGrid || {}
        var c = Number(g.cols || g.columns || g.grid_cols || 0)
        if (c > 1) return c
        var n = gridSamples().length
        return n === 35 ? 7 : Math.max(2, Math.round(Math.sqrt(Math.max(4, n))))
    }

    function gridRows() {
        var g = weatherGrid || {}
        var r = Number(g.rows || g.grid_rows || 0)
        if (r > 1) return r
        var n = gridSamples().length
        var c = gridCols()
        return n > 0 ? Math.max(2, Math.ceil(n / c)) : 5
    }

    function valueOf(obj, names, fallback) {
        if (!obj) return fallback
        for (var i=0; i<names.length; ++i) {
            var v = obj[names[i]]
            if (v !== undefined && v !== null && v !== "")
                return Number(v)
        }
        return fallback
    }

    function normalizedSample(obj) {
        return {
            speed: valueOf(obj, ["speed","wind_speed","windSpeed","wind_speed_10m"], Number(weatherBridge.windSpeed || 0)),
            degrees: valueOf(obj, ["degrees","direction","wind_degrees","windDegrees","wind_direction_10m"], Number(weatherBridge.windDegrees || 0)),
            temperature: valueOf(obj, ["temperature","temp","temperature_2m"], Number(weatherBridge.temperature || 0)),
            rain: valueOf(obj, ["rain","precipitation","precip"], Number(weatherBridge.precipitation || 0)),
            clouds: valueOf(obj, ["clouds","cloud_cover","cloudCover"], 25),
            pressure: valueOf(obj, ["pressure","surface_pressure","surfacePressure"], 1013)
        }
    }

    function mapCenterLat() {
        var v = Number(root.terrainGrid.center_lat)
        return isFinite(v) && Math.abs(v) <= 90 ? v : Number(weatherBridge.latitude || 0)
    }

    function mapCenterLon() {
        var v = Number(root.terrainGrid.center_lon)
        return isFinite(v) ? v : Number(weatherBridge.longitude || 0)
    }

    function mapSpanKm() {
        var s = Number(root.terrainGrid.span_km || 300)
        return Math.max(80, Math.min(900, s))
    }

    function mercatorX(lon) {
        var v = ((Number(lon) + 180) % 360 + 360) % 360 - 180
        return (v + 180.0) / 360.0
    }

    function mercatorY(lat) {
        var clamped = Math.max(-85.05112878, Math.min(85.05112878, Number(lat)))
        var r = clamped * Math.PI / 180.0
        return (1.0 - Math.log(Math.tan(Math.PI/4.0 + r/2.0)) / Math.PI) / 2.0
    }

    function screenToGeo(x, y, w, h) {
        var lat0 = mapCenterLat()
        var lon0 = mapCenterLon()
        var cx = mercatorX(lon0)
        var cy = mercatorY(lat0)
        var cosLat = Math.max(.10, Math.abs(Math.cos(lat0 * Math.PI / 180.0)))
        var worldWidth = mapSpanKm() / (40075.016686 * cosLat)
        var worldHeight = worldWidth * h / Math.max(1, w)

        var mx = cx + ((x / Math.max(1,w)) - .5) * worldWidth
        var my = cy + ((y / Math.max(1,h)) - .5) * worldHeight

        var lon = mx * 360.0 - 180.0
        var n = Math.PI * (1.0 - 2.0 * my)
        var lat = Math.atan(Math.sinh(n)) * 180.0 / Math.PI

        // Keep longitude continuous around the active center, including dateline views.
        while (lon - lon0 > 180) lon -= 360
        while (lon - lon0 < -180) lon += 360
        return {lat:lat, lon:lon}
    }

    function sampleGridAtScreen(x, y, w, h) {
        var g = weatherGrid || {}
        var geo = screenToGeo(x,y,w,h)
        var latMin = Number(g.lat_min)
        var latMax = Number(g.lat_max)
        var lonMin = Number(g.lon_min)
        var lonMax = Number(g.lon_max)

        if (!isFinite(latMin) || !isFinite(latMax) ||
            !isFinite(lonMin) || !isFinite(lonMax) ||
            latMax <= latMin || lonMax <= lonMin)
            return sampleGrid(x/Math.max(1,w), y/Math.max(1,h))

        var nx = (geo.lon-lonMin)/(lonMax-lonMin)
        var ny = (latMax-geo.lat)/(latMax-latMin)
        return sampleGrid(nx,ny)
    }

    function sampleGrid(nx, ny) {
        var list = gridSamples()
        if (!list || list.length < 4)
            return normalizedSample(null)

        var cols = gridCols()
        var rows = gridRows()

        nx = Math.max(0, Math.min(0.9999, nx))
        ny = Math.max(0, Math.min(0.9999, ny))

        var fx = nx * (cols - 1)
        var fy = ny * (rows - 1)
        var x0 = Math.floor(fx)
        var y0 = Math.floor(fy)
        var x1 = Math.min(cols - 1, x0 + 1)
        var y1 = Math.min(rows - 1, y0 + 1)
        var tx = fx - x0
        var ty = fy - y0

        function at(x,y) {
            var idx = y * cols + x
            if (idx < 0 || idx >= list.length) return normalizedSample(null)
            return normalizedSample(list[idx])
        }

        var a = at(x0,y0)
        var b = at(x1,y0)
        var c = at(x0,y1)
        var d = at(x1,y1)

        function lerp(v0,v1,t) { return v0 + (v1-v0)*t }
        function bi(v00,v10,v01,v11) {
            return lerp(lerp(v00,v10,tx), lerp(v01,v11,tx), ty)
        }

        // Interpolate vector components instead of angles to avoid 359°/0° discontinuities.
        function uv(s) {
            var toDeg = (s.degrees + 180.0) % 360.0
            var rad = toDeg * Math.PI / 180.0
            return {u: Math.sin(rad) * s.speed, v: -Math.cos(rad) * s.speed}
        }

        var ua=uv(a), ub=uv(b), uc=uv(c), ud=uv(d)
        var u=bi(ua.u,ub.u,uc.u,ud.u)
        var v=bi(ua.v,ub.v,uc.v,ud.v)
        var sp=Math.sqrt(u*u+v*v)
        var toRad=Math.atan2(u,-v)
        var fromDeg=(toRad*180/Math.PI + 180 + 360) % 360

        return {
            speed: sp,
            degrees: fromDeg,
            temperature: bi(a.temperature,b.temperature,c.temperature,d.temperature),
            rain: bi(a.rain,b.rain,c.rain,d.rain),
            clouds: bi(a.clouds,b.clouds,c.clouds,d.clouds),
            pressure: bi(a.pressure,b.pressure,c.pressure,d.pressure)
        }
    }

    function flowVector(x, y, sample) {
        var s = sample || sampleGridAtScreen(
            x, y, Math.max(1,mapFrame.width), Math.max(1,mapFrame.height)
        )
        var toDeg = (s.degrees + 180.0) % 360.0
        var rad = toDeg * Math.PI / 180.0

        var baseX = Math.sin(rad)
        var baseY = -Math.cos(rad)

        // Multi-scale curl: enough curvature to feel organic without reversing the real flow.
        var bendA = Math.sin(x * 0.0067 + y * 0.0048 + root.phase * 1.45) * 0.095
        var bendB = Math.sin(x * 0.0029 - y * 0.0072 + root.phase * 0.92) * 0.052
        var bend = bendA + bendB
        var px = -baseY
        var py = baseX

        // Keep weak winds visually legible while preserving the actual local bearing.
        var mag = 1.05 + Math.min(2.45, s.speed * 0.135)
        return {
            x: (baseX + px*bend) * mag,
            y: (baseY + py*bend) * mag,
            speed: s.speed
        }
    }

    function initParticles() {
        var arr=[]
        var w=Math.max(200,mapFrame.width)
        var h=Math.max(200,mapFrame.height)
        for (var i=0;i<particleCount;i++) {
            var x=(i*97.37)%w
            var y=(i*53.21 + (i%11)*17)%h
            arr.push({x:x,y:y,age:i%110,maxAge:105+(i%85),trail:[]})
        }
        particles=arr
    }

    function windFromText() {
        return weatherBridge.windDirection || "—"
    }

    function windToText() {
        if (!weatherBridge.locationName)
            return "—"
        var deg=(Number(weatherBridge.windDegrees || 0)+180)%360
        var dirs=["N","NE","E","SE","S","SO","O","NO"]
        return dirs[Math.round(deg/45)%8]
    }

    function synthesis() {
        if (!weatherBridge.locationName)
            return weatherBridge.loading ? "Initialisation du contexte météo…" : "Recherche une ville pour activer le contexte."
        var s=weatherBridge.locationName+" : "+tempText(weatherBridge.temperature)+", "+weatherBridge.weatherLabel.toLowerCase()
        s+=". Ressenti "+tempText(weatherBridge.feelsLike)+", humidité "+weatherBridge.humidity+" %, vent "+Number(weatherBridge.windSpeed).toFixed(0)+" km/h "+weatherBridge.windDirection
        if (forecastDays.length>1)
            s+=". Demain : "+forecastDays[1].label.toLowerCase()+", "+tempText(forecastDays[1].max)+" / "+tempText(forecastDays[1].min)+"."
        return s
    }

    onVisibleChanged: if (visible) weatherBridge.ensureLoaded()

    Component.onCompleted: {
        syncData()
        weatherBridge.ensureLoaded()
    }

    onWidthChanged: initParticles()
    onHeightChanged: initParticles()

    Connections {
        target: weatherBridge
        function onWeatherChanged() { root.syncData() }
    }

    Timer {
        interval: 34
        repeat: true
        running: root.visible
        onTriggered: {
            root.phase += 0.022
            flowCanvas.requestPaint()
            focusHalo.requestPaint()
        }
    }

    Timer {
        interval: 900000
        repeat: true
        running: root.visible
        onTriggered: weatherBridge.refresh()
    }

    Rectangle {
        anchors.fill: parent
        color: root.bg0
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.lightMode ? "#EFF8FA" : "#02080E" }
            GradientStop { position: 0.48; color: root.lightMode ? "#E4F0F3" : "#03111A" }
            GradientStop { position: 1.0; color: root.lightMode ? "#D9E9ED" : "#02070C" }
        }
    }

    // Premium app-level weather toolbar.
    Rectangle {
        id: header
        z: 100
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: 10
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        height: 50
        radius: 12
        color: root.lightMode ? "#EFF8FA" : "#061821"
        opacity: 0.97
        border.width: 1
        border.color: root.lightMode ? "#A7CED7" : "#245A6A"

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10

            Rectangle {
                width: 6
                height: 6
                radius: 3
                color: weatherBridge.loading ? "#E7BC73" : root.cyan
            }

            Text {
                text: "AURA · MÉTÉO"
                color: root.cyan
                font.pixelSize: 10
                font.weight: Font.DemiBold
                font.letterSpacing: 1.6
            }

            Text {
                width: 300
                text: weatherBridge.locationName
                      ? weatherBridge.locationName + (weatherBridge.locationDetail ? " · " + weatherBridge.locationDetail : "")
                      : "LOCALISATION MÉTÉO"
                elide: Text.ElideRight
                color: root.textMain
                font.pixelSize: 11
                font.weight: Font.DemiBold
            }
        }

        Row {
            anchors.centerIn: parent
            spacing: 6
            Repeater {
                model: [
                    ["OPEN-METEO","#80EAB8"],
                    [weatherBridge.loading?"SYNC":(weatherBridge.locationName?"LIVE":"STANDBY"),weatherBridge.loading?"#E4BA72":"#80EAB8"],
                    ["COUCHE · "+root.activeLayer.toUpperCase(),"#7FA8B8"]
                ]
                Rectangle {
                    height: 24
                    width: statusText.implicitWidth+18
                    radius: 12
                    color: root.lightMode ? "#E6F0F3" : "#04131B"
                    border.width: 1
                    border.color: root.lightMode ? "#B8D3DA" : "#153F4D"
                    Text {
                        id: statusText
                        anchors.centerIn: parent
                        text: modelData[0]
                        color: modelData[1]
                        font.pixelSize: 8
                        font.weight: Font.DemiBold
                        font.letterSpacing: 0.65
                    }
                }
            }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6

            Rectangle {
                id: searchShell
                width: root.searchOpen ? 344 : 38
                height: 34
                radius: 11
                color: root.lightMode ? "#EAF5F8" : "#061B24"
                border.width: 1
                border.color: cityInput.activeFocus
                              ? root.cyan
                              : (searchHover.hovered
                                 ? (root.lightMode ? "#85D9E8" : "#2E7185")
                                 : (root.lightMode ? "#A7CED7" : "#225363"))
                Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 1
                    radius: 10
                    color: root.lightMode ? "#F5FBFD" : "#082431"
                    opacity: root.searchOpen ? 0.98 : 0.9
                }

                Rectangle {
                    anchors.fill: parent
                    radius: 11
                    color: "transparent"
                    border.width: 1
                    border.color: root.searchOpen ? Qt.rgba(0.33, 0.91, 0.98, 0.18)
                                                  : Qt.rgba(0.33, 0.91, 0.98, 0.07)
                }

                Rectangle {
                    x: 1
                    y: 1
                    width: parent.width - 2
                    height: 12
                    radius: 10
                    color: root.lightMode ? Qt.rgba(1, 1, 1, 0.40) : Qt.rgba(1, 1, 1, 0.03)
                }

                HoverHandler {
                    id: searchHover
                }

                Rectangle {
                    id: searchIconOrb
                    width: 24
                    height: 24
                    radius: 12
                    anchors.left: parent.left
                    anchors.leftMargin: 6
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.lightMode ? "#FFFFFF" : "#0A2A36"
                    border.width: 1
                    border.color: cityInput.activeFocus ? root.cyan : (root.lightMode ? "#B8DCE5" : "#1E5566")

                    Text {
                        anchors.centerIn: parent
                        text: "⌕"
                        color: root.cyan
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                    }

                    TapHandler {
                        onTapped: {
                            if (!root.searchOpen) {
                                root.searchOpen = true
                                cityInput.forceActiveFocus()
                                cityInput.selectAll()
                            } else if (cityInput.text.trim().length >= 2) {
                                weatherBridge.searchLocations(cityInput.text.trim())
                            } else {
                                cityInput.forceActiveFocus()
                            }
                        }
                    }
                }

                TextField {
                    id: cityInput
                    visible: root.searchOpen
                    opacity: root.searchOpen ? 1 : 0
                    anchors.left: parent.left
                    anchors.leftMargin: 40
                    anchors.right: parent.right
                    anchors.rightMargin: 58
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    text: weatherBridge.lastQuery
                    placeholderText: "Rechercher une ville, région ou pays"
                    color: root.textMain
                    placeholderTextColor: root.textDim
                    font.pixelSize: 10
                    font.weight: Font.Medium
                    verticalAlignment: TextInput.AlignVCenter
                    selectByMouse: true
                    clip: true
                    background: null
                    onAccepted: {
                        if (text.trim().length >= 2) {
                            weatherBridge.searchLocations(text.trim())
                        }
                    }
                    Keys.onEscapePressed: {
                        root.searchOpen = false
                        focus = false
                    }
                }

                Rectangle {
                    id: clearChip
                    visible: root.searchOpen && cityInput.text.length > 0
                    width: 18
                    height: 18
                    radius: 9
                    anchors.right: submitButton.left
                    anchors.rightMargin: 6
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.lightMode ? "#E4F4F8" : "#0A2934"
                    border.width: 1
                    border.color: root.lightMode ? "#B7DCE5" : "#1D5566"

                    Text {
                        anchors.centerIn: parent
                        text: "×"
                        color: root.textSoft
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }

                    TapHandler {
                        onTapped: {
                            cityInput.clear()
                            cityInput.forceActiveFocus()
                        }
                    }
                }

                Rectangle {
                    id: cityResultsPanel
                    visible: weatherBridge.cityResults.length > 0
                    x: 0; y: parent.height + 6; width: 344
                    height: Math.min(180, weatherBridge.cityResults.length * 42 + 8)
                    radius: 12; color: root.lightMode ? "#F5FBFD" : "#0A202D"
                    border.width: 1; border.color: root.cyan; z: 20
                    Column { anchors.fill: parent; anchors.margins: 4; spacing: 2
                        Repeater { model: weatherBridge.cityResults
                            delegate: Rectangle { width: cityResultsPanel.width - 8; height: 38; radius: 8
                                color: cityHover.hovered ? (root.lightMode ? "#DDF4F8" : "#123846") : "transparent"
                                HoverHandler { id: cityHover }
                                Text { anchors.left: parent.left; anchors.leftMargin: 10; anchors.verticalCenter: parent.verticalCenter; text: modelData.name + (modelData.country ? " · " + modelData.country : ""); color: root.textMain; font.pixelSize: 10 }
                                TapHandler { onTapped: { weatherBridge.selectCity(modelData); root.searchOpen = false } }
                            }
                        }
                    }
                }

                Rectangle {
                    id: submitButton
                    width: 28
                    height: 26
                    radius: 8
                    anchors.right: parent.right
                    anchors.rightMargin: 4
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.searchOpen ? (root.lightMode ? "#DFF5FB" : "#0C2F3B")
                                           : (root.lightMode ? "#ECF7FA" : "#082532")
                    border.width: 1
                    border.color: root.searchOpen ? root.cyan : (root.lightMode ? "#B7DCE5" : "#1D5566")

                    Text {
                        anchors.centerIn: parent
                        text: "⌕"
                        color: root.cyan
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                    }

                    TapHandler {
                        onTapped: {
                            if (!root.searchOpen) {
                                root.searchOpen = true
                                cityInput.forceActiveFocus()
                                cityInput.selectAll()
                            } else if (cityInput.text.trim().length >= 2) {
                                weatherBridge.searchLocations(cityInput.text.trim())
                            } else {
                                cityInput.forceActiveFocus()
                            }
                        }
                    }
                }
            }

            Rectangle {
                width: 88
                height: 32
                radius: 9
                color: refreshHover.hovered ? (root.lightMode ? "#D7EBF0" : "#0B2B36") : (root.lightMode ? "#E8F2F5" : "#08202A")
                border.width: 1
                border.color: root.lightMode ? "#A7CED7" : "#225363"
                Text {
                    anchors.centerIn: parent
                    text: "ACTUALISER"
                    color: root.lightMode ? "#1D6075" : "#CFF8FF"
                    font.pixelSize: 8
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.6
                }
                HoverHandler { id: refreshHover }
                TapHandler { enabled: !weatherBridge.loading; onTapped: weatherBridge.refresh() }
            }
        }
    }

    // Left current conditions.
    Item {
        id: leftRail
        z: 40
        x: 38
        y: 92
        width: 304
        height: parent.height-130

        Text {
            text: "⌖  LOCATION"
            color: root.textDim
            opacity: 0.72
            font.pixelSize: 9
            font.weight: Font.DemiBold
            font.letterSpacing: 1.4
        }

        Text {
            y: 28
            width: 280
            text: weatherBridge.locationName || "—"
            elide: Text.ElideRight
            color: root.textMain
            font.pixelSize: 17
            font.weight: Font.DemiBold
        }

        Text {
            x: 196
            y: 80
            width: 86
            horizontalAlignment: Text.AlignHCenter
            text: weatherBridge.weatherIcon
            color: root.cyan
            opacity: root.lightMode ? 0.16 : 0.20
            font.pixelSize: 58
            font.weight: Font.ExtraLight
        }

        Row {
            x: -2
            y: 82
            spacing: 3
            Text {
                text: weatherBridge.locationName ? Number(weatherBridge.temperature).toFixed(1).replace(".0","") : "—"
                color: root.textMain
                font.pixelSize: 94
                font.weight: Font.ExtraLight
                font.letterSpacing: -4
            }
            Text {
                text: "°"
                color: root.cyan
                font.pixelSize: 25
                font.weight: Font.Light
                topPadding: 8
            }
        }

        Text {
            y: 188
            width: 290
            text: weatherBridge.weatherLabel.toUpperCase()
            color: root.lightMode ? "#315868" : "#C7EEF7"
            font.pixelSize: 13
            font.letterSpacing: 2.0
        }

        Text {
            y: 218
            text: weatherBridge.locationName ? "RESSENTI  "+root.tempText(weatherBridge.feelsLike) : "RESSENTI  —"
            color: root.textDim
            opacity: 0.66
            font.pixelSize: 9
            font.letterSpacing: 1.2
        }

        Row {
            y: 258
            spacing: 8
            Repeater {
                model: [
                    ["≋","VENT",weatherBridge.locationName?Number(weatherBridge.windSpeed).toFixed(0)+" km/h":"—"],
                    ["◌","HUMIDITÉ",weatherBridge.locationName?weatherBridge.humidity+" %":"—"],
                    ["◜","PLUIE",weatherBridge.locationName?Number(weatherBridge.precipitation).toFixed(1)+" mm":"—"]
                ]

                Rectangle {
                    width: 92
                    height: 84
                    radius: 12
                    color: root.panel
                    opacity: 0.88
                    border.width: 1
                    border.color: root.lightMode ? "#BDD8DE" : "#163E4B"

                    Text { x:11; y:13; text:modelData[0]; color:root.cyan; font.pixelSize:15 }
                    Text { x:34; y:14; text:modelData[1]; color:root.textDim; font.pixelSize:8; font.weight:Font.DemiBold; font.letterSpacing:0.75 }
                    Text { x:34; y:42; text:modelData[2]; color:root.textMain; font.pixelSize:11; font.weight:Font.Medium }
                }
            }
        }

        Rectangle {
            id: synthesisCard
            y: 370
            width: 304
            height: 196
            radius: 16
            color: root.panel
            opacity: 0.91
            border.width: 1
            border.color: root.lightMode ? "#A9CCD5" : "#174555"

            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                radius: 15
                color: "transparent"
                border.width: 1
                border.color: root.lightMode ? "#FFFFFF" : "#0D2D39"
                opacity: 0.38
            }

            Text {
                x:14; y:13
                text:"AURA SYNTHESIS"
                color:root.cyan
                opacity:0.76
                font.pixelSize:9
                font.weight:Font.DemiBold
                font.letterSpacing:1.35
            }

            Rectangle {
                x: width-54; y:12
                width:38; height:18; radius:9
                color: root.lightMode ? "#DDECEF" : "#08222C"
                border.width:1
                border.color: root.lightMode ? "#B4D3DA" : "#174657"
                Text { anchors.centerIn:parent; text:weatherBridge.loading?"SYNC":"LIVE"; color:root.cyan; font.pixelSize:7; font.weight:Font.DemiBold }
            }

            Text {
                x:14; y:47
                width:parent.width-28
                height:94
                wrapMode:Text.WordWrap
                elide:Text.ElideRight
                maximumLineCount:5
                text:root.synthesis()
                color:root.lightMode ? "#466B79" : "#B8D9E5"
                opacity:0.84
                font.pixelSize:10
                lineHeight:1.36
            }

            Text {
                x:14; y:132
                text:weatherBridge.updatedAt ? "LIVE · "+weatherBridge.updatedAt : "LIVE"
                color:root.textDim
                opacity:0.52
                font.pixelSize:7
                font.weight:Font.DemiBold
                font.letterSpacing:0.8
            }

            Row {
                x:14; y:158; spacing:6
                Repeater {
                    model:[root.activeLayer.toUpperCase(),weatherBridge.windDirection||"—",weatherBridge.humidity+"%"]
                    Rectangle {
                        height:22
                        width:tagText.implicitWidth+16
                        radius:11
                        color:root.lightMode?"#E2EEF1":"#071F29"
                        border.width:1
                        border.color:root.lightMode?"#B9D4DB":"#153F4C"
                        Text { id:tagText; anchors.centerIn:parent; text:modelData; color:root.textSoft; font.pixelSize:7; font.weight:Font.DemiBold; font.letterSpacing:0.55 }
                    }
                }
            }
        }
    }

    // Main premium weather map.
    Rectangle {
        id: mapFrame
        z: 20
        x: 350
        y: 78
        width: Math.max(640,parent.width-x-22)
        height: Math.max(520,parent.height-y-44)
        radius: 18
        clip: true
        color: root.lightMode ? "#D6E7EB" : "#021019"
        border.width: 1
        border.color: root.lightMode ? "#8FB9C4" : "#1D5263"

        GeoBaseMap {
            id: sharedGeoBase; objectName: "weatherGeoBaseMap"
            anchors.fill: parent
            lightMode: root.lightMode
            landPolygons: root.mapSpanKm() <= 1500 && root.mapCenterLat() >= 30 && root.mapCenterLat() <= 72 && root.mapCenterLon() >= -14 && root.mapCenterLon() <= 38 ? (weatherBridge.regionalGeometry.land_polygons || []) : (weatherBridge.worldGeometry.land_polygons || [])
            coastlines: root.mapSpanKm() <= 1500 && root.mapCenterLat() >= 30 && root.mapCenterLat() <= 72 && root.mapCenterLon() >= -14 && root.mapCenterLon() <= 38 ? (weatherBridge.regionalGeometry.coastlines || []) : (weatherBridge.worldGeometry.coastlines || [])
            boundaries: []
            centerLatitude: root.mapCenterLat()
            centerLongitude: root.mapCenterLon()
            spanKm: root.mapSpanKm()
            showMarker: !!weatherBridge.locationName
            markerLatitude: weatherBridge.latitude
            markerLongitude: weatherBridge.longitude
        }
        Rectangle { objectName: "weatherGeographyUnavailable"; z: 100; visible: !sharedGeoBase.mapBaseReady; anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter; anchors.topMargin: 16; width: Math.min(parent.width-32,390); height: 34; radius: 10; color: root.lightMode ? "#E8FFFFFF" : "#E60A2331"; border.width: 1; border.color: "#6A8CA8B7"
            Text { anchors.centerIn: parent; text: "FOND GÉOGRAPHIQUE LOCAL INDISPONIBLE"; color: root.textMain; font.pixelSize: 9; font.weight: Font.DemiBold }
        }

        Canvas {
            id: glassSheen
            anchors.fill: parent
            opacity: root.lightMode ? 0.22 : 0.52

            onPaint: {
                var c=getContext("2d")
                c.clearRect(0,0,width,height)
                var g=c.createLinearGradient(0,0,0,150)
                g.addColorStop(0,"rgba(121,240,255,.075)")
                g.addColorStop(.35,"rgba(66,154,192,.025)")
                g.addColorStop(1,"rgba(0,0,0,0)")
                c.fillStyle=g
                c.fillRect(0,0,width,150)

                var edge=c.createLinearGradient(0,0,width,0)
                edge.addColorStop(0,"rgba(86,226,244,.025)")
                edge.addColorStop(.72,"rgba(86,226,244,0)")
                edge.addColorStop(1,"rgba(144,88,255,.045)")
                c.fillStyle=edge
                c.fillRect(0,0,width,90)
            }

            Component.onCompleted: requestPaint()
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
        }

        // Cinematic topographic base.
        // Real geographic terrain from cached high-resolution Terrarium DEM tiles.
        // Premium real geography:
        // Cinematic map atmosphere: subtle vignetting, horizon bloom and glass sheen.
        Canvas {
            id: mapAtmosphere
            anchors.fill: parent
            opacity: root.lightMode ? 0.42 : 0.92

            onPaint: {
                var c=getContext("2d")
                c.clearRect(0,0,width,height)

                var sky=c.createLinearGradient(0,0,0,height)
                sky.addColorStop(0,"rgba(63,213,239,.060)")
                sky.addColorStop(.32,"rgba(20,92,116,.022)")
                sky.addColorStop(1,"rgba(0,0,0,.095)")
                c.fillStyle=sky
                c.fillRect(0,0,width,height)

                var leftGlow=c.createRadialGradient(width*.27,height*.34,20,width*.27,height*.34,width*.46)
                leftGlow.addColorStop(0,"rgba(21,192,193,.080)")
                leftGlow.addColorStop(.52,"rgba(21,104,118,.026)")
                leftGlow.addColorStop(1,"rgba(0,0,0,0)")
                c.fillStyle=leftGlow
                c.fillRect(0,0,width,height)

                var coastGlow=c.createRadialGradient(width*.70,height*.50,20,width*.70,height*.50,width*.38)
                coastGlow.addColorStop(0,"rgba(76,176,232,.055)")
                coastGlow.addColorStop(.62,"rgba(75,82,190,.018)")
                coastGlow.addColorStop(1,"rgba(0,0,0,0)")
                c.fillStyle=coastGlow
                c.fillRect(0,0,width,height)

                var vignette=c.createRadialGradient(width*.5,height*.48,width*.28,width*.5,height*.48,width*.72)
                vignette.addColorStop(0,"rgba(0,0,0,0)")
                vignette.addColorStop(.70,"rgba(0,0,0,.025)")
                vignette.addColorStop(1,"rgba(0,0,0,.20)")
                c.fillStyle=vignette
                c.fillRect(0,0,width,height)
            }

            Component.onCompleted: requestPaint()
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
        }

        // Smooth scalar weather overlay, deliberately not a square heat map.
        Canvas {
            id: scalarField
            objectName: "weatherScalarOverlay"
            anchors.fill: parent
            opacity: root.lightMode ? 0.28 : 0.47

            function fieldColor(s) {
                if(root.activeLayer==="rain"){
                    var r=Math.max(0,Math.min(1,s.rain/6))
                    return "rgba("+Math.round(55+110*r)+","+Math.round(180-65*r)+",255,"+(0.025+0.08*r)+")"
                }
                if(root.activeLayer==="temperature"){
                    var t=Math.max(0,Math.min(1,(s.temperature-5)/30))
                    return "rgba("+Math.round(55+180*t)+","+Math.round(135-50*t)+","+Math.round(235-110*t)+",.07)"
                }
                if(root.activeLayer==="clouds"){
                    var cl=Math.max(0,Math.min(1,s.clouds/100))
                    return "rgba(200,235,245,"+(0.018+0.08*cl)+")"
                }
                if(root.activeLayer==="pressure"){
                    var pr=Math.max(0,Math.min(1,(s.pressure-980)/70))
                    return "rgba("+Math.round(115+60*pr)+","+Math.round(75+85*pr)+",245,.07)"
                }
                var w=Math.max(0,Math.min(1,s.speed/35))
                return w<.45 ? "rgba(28,205,220,.070)" : (w<.75 ? "rgba(41,120,241,.075)" : "rgba(129,69,246,.085)")
            }

            onPaint: {
                var c=getContext("2d")
                c.clearRect(0,0,width,height)
                var cols=7, rows=5
                for(var yy=0;yy<rows;yy++){
                    for(var xx=0;xx<cols;xx++){
                        var nx=xx/(cols-1), ny=yy/(rows-1)
                        var px=nx*width, py=ny*height
                        var s=root.sampleGridAtScreen(px,py,width,height)
                        var rad=Math.max(width/cols,height/rows)*2.35
                        var g=c.createRadialGradient(px,py,3,px,py,rad)
                        g.addColorStop(0,fieldColor(s))
                        g.addColorStop(1,"rgba(0,0,0,0)")
                        c.fillStyle=g
                        c.fillRect(px-rad,py-rad,rad*2,rad*2)
                    }
                }
            }
        }

        // Windy-like continuous particle trajectories.
        Canvas {
            id: flowCanvas
            anchors.fill: parent
            opacity: root.activeLayer==="wind" ? 0.96 : 0.34

            onPaint: {
                var c=getContext("2d")
                c.clearRect(0,0,width,height)

                if(root.activeLayer!=="wind"){
                    // Keep a restrained atmospheric motion for non-wind layers.
                    c.strokeStyle="rgba(92,220,244,.10)"
                    c.lineWidth=1
                    for(var k=0;k<26;k++){
                        var yy=(k*41+root.phase*18)%height
                        c.beginPath()
                        c.moveTo((k*79)%width,yy)
                        c.lineTo(Math.min(width,(k*79)%width+44),yy+Math.sin(k)*8)
                        c.stroke()
                    }
                    return
                }

                if(!root.particles || root.particles.length!==root.particleCount)
                    root.initParticles()

                var arr=root.particles
                for(var i=0;i<arr.length;i++){
                    var p=arr[i]
                    var s=root.sampleGridAtScreen(p.x,p.y,width,height)
                    var v=root.flowVector(p.x,p.y,s)

                    p.trail.push({x:p.x,y:p.y})
                    while(p.trail.length>root.trailLength)p.trail.shift()

                    p.x+=v.x
                    p.y+=v.y
                    p.age++

                    if(p.x<-24||p.x>width+24||p.y<-24||p.y>height+24||p.age>p.maxAge){
                        p.x=(i*113.7+root.phase*37)%Math.max(1,width)
                        p.y=(i*61.3+root.phase*19)%Math.max(1,height)
                        p.age=0
                        p.maxAge=105+(i%95)
                        p.trail=[]
                    }

                    if(p.trail.length>1){
                        for(var t=1;t<p.trail.length;t++){
                            var a=p.trail[t-1], b=p.trail[t]
                            var alpha=(t/p.trail.length)*(0.055+Math.min(.30,s.speed/78))
                            var purple=(i%13===0)
                            c.strokeStyle=purple ? "rgba(151,96,255,"+alpha+")" : "rgba(72,224,255,"+alpha+")"
                            c.lineWidth=t===p.trail.length-1 ? 1.18 : 0.72
                            c.beginPath()
                            c.moveTo(a.x,a.y)
                            c.lineTo(b.x,b.y)
                            c.stroke()
                        }

                        if(i%11===0 && p.trail.length>2){
                            var headAlpha=0.18+Math.min(.32,s.speed/70)
                            c.beginPath()
                            c.arc(p.x,p.y,1.25,0,Math.PI*2)
                            c.fillStyle="rgba(112,239,255,"+headAlpha+")"
                            c.fill()
                        }
                    }
                }
                root.particles=arr
            }
        }

        // Focal selection bloom.
        Canvas {
            id: focusHalo
            anchors.fill: parent
            opacity: weatherBridge.locationName ? 1 : 0

            onPaint: {
                var c=getContext("2d")
                c.clearRect(0,0,width,height)
                var x=width*.50, y=height*.50

                var glow=c.createRadialGradient(x,y,4,x,y,210)
                glow.addColorStop(0,"rgba(65,235,252,.17)")
                glow.addColorStop(.30,"rgba(35,163,199,.070)")
                glow.addColorStop(.62,"rgba(117,75,219,.020)")
                glow.addColorStop(1,"rgba(0,0,0,0)")
                c.fillStyle=glow
                c.fillRect(x-190,y-190,380,380)

                var r=14+Math.sin(root.phase*2)*3.2
                c.beginPath();c.arc(x,y,r,0,Math.PI*2)
                c.strokeStyle="rgba(91,235,255,.58)"
                c.lineWidth=1.1;c.stroke()

                c.beginPath();c.arc(x,y,r+7,0,Math.PI*2)
                c.strokeStyle="rgba(137,93,255,.16)"
                c.lineWidth=.8;c.stroke()

                c.strokeStyle="rgba(104,234,255,.30)"
                c.lineWidth=.8
                c.beginPath();c.moveTo(x-24,y);c.lineTo(x-9,y);c.stroke()
                c.beginPath();c.moveTo(x+9,y);c.lineTo(x+24,y);c.stroke()
                c.beginPath();c.moveTo(x,y-24);c.lineTo(x,y-9);c.stroke()
                c.beginPath();c.moveTo(x,y+9);c.lineTo(x,y+24);c.stroke()

                c.beginPath();c.arc(x,y,3.1,0,Math.PI*2)
                c.fillStyle=root.cyan;c.fill()
            }
        }

        Rectangle {
            z: 39
            anchors.fill: parent
            anchors.margins: 1
            radius: 17
            color: "transparent"
            border.width: 1
            border.color: root.lightMode ? "rgba(255,255,255,.48)" : "rgba(104,226,244,.075)"
        }

        // Layer toolbar.
        Rectangle {
            z: 40
            x: 14
            y: 14
            height: 38
            width: layerRow.implicitWidth+18
            radius: 11
            color: root.lightMode ? "#E9F3F5" : "#03141C"
            opacity: 0.94
            border.width: 1
            border.color: root.lightMode ? "#A6CDD6" : "#1A4F5F"

            Row {
                id: layerRow
                anchors.centerIn: parent
                spacing: 4

                Text {
                    text:"COUCHES"
                    color:root.textDim
                    opacity:0.70
                    font.pixelSize:8
                    font.weight:Font.DemiBold
                    font.letterSpacing:1.1
                    leftPadding:5
                    rightPadding:4
                    anchors.verticalCenter:parent.verticalCenter
                }

                Repeater {
                    model: root.layers
                    Rectangle {
                        height:28
                        width:layerText.implicitWidth+16
                        radius:8
                        color:root.activeLayer===modelData.key ? (root.lightMode?"#CFEAF0":"#0C3140") : "transparent"
                        border.width:root.activeLayer===modelData.key ? 1 : 0
                        border.color:root.cyan

                        Text {
                            id:layerText
                            anchors.centerIn:parent
                            text:modelData.label
                            color:root.activeLayer===modelData.key ? root.textMain : root.textDim
                            opacity:root.activeLayer===modelData.key ? 1 : .62
                            font.pixelSize:8
                            font.weight:Font.DemiBold
                            font.letterSpacing:.6
                        }

                        TapHandler {
                            onTapped: {
                                root.activeLayer=modelData.key
                                scalarField.requestPaint()
                                flowCanvas.requestPaint()
                            }
                        }
                    }
                }
            }
        }

        Text {
            z: 38
            x: 18
            y: 66
            text: weatherBridge.locationName ? "MÉDITERRANÉE · "+weatherBridge.locationName.toUpperCase()+" · LIVE FIELD" : "ATMOSPHERIC FIELD"
            color: root.textDim
            opacity: 0.44
            font.pixelSize: 8
            font.weight: Font.DemiBold
            font.letterSpacing: 1.4
        }

        // Real-wind compass.
        Rectangle {
            z: 42
            anchors.top: parent.top
            anchors.right: detailCard.left
            anchors.topMargin: 62
            anchors.rightMargin: 14
            width: 126
            height: 52
            radius: 12
            color: root.lightMode ? "#EDF6F8" : "#041720"
            opacity: 0.90
            border.width: 1
            border.color: root.lightMode ? "#A7CDD5" : "#174B5A"

            Text {
                x:11; y:9
                text:"VENT RÉEL"
                color:root.textDim
                opacity:.68
                font.pixelSize:7
                font.weight:Font.DemiBold
                font.letterSpacing:.9
            }

            Text {
                x:11; y:27
                text:"↗"
                rotation: Number(weatherBridge.windDegrees || 0)+180
                transformOrigin: Item.Center
                color:root.cyan
                font.pixelSize:13
                font.weight:Font.DemiBold
            }

            Text {
                x:35; y:29
                text:"DE "+root.windFromText()+" · VERS "+root.windToText()
                color:root.textMain
                font.pixelSize:8
                font.weight:Font.DemiBold
            }
        }

        Rectangle {
            z: 42
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.topMargin: 14
            anchors.rightMargin: 14
            width:124
            height:34
            radius:10
            color:root.lightMode?"#E9F3F5":"#03141C"
            opacity:.94
            border.width:1
            border.color:root.lightMode?"#A6CDD6":"#1A4F5F"
            Row {
                anchors.centerIn:parent
                spacing:8
                Text { text:"▶"; color:root.cyan; font.pixelSize:9 }
                Text { text:"ANIMATION"; color:root.textSoft; font.pixelSize:8; font.weight:Font.DemiBold }
                Text { text:"LIVE"; color:root.violet; font.pixelSize:7; font.weight:Font.DemiBold }
            }
        }

        // Compact field-detail HUD.
        Rectangle {
            id: detailCard
            z: 41
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.topMargin: 62
            anchors.rightMargin: 14
            width: mapFrame.width>860 ? 196 : 0
            height: 224
            visible: width>0
            radius: 13
            color: root.lightMode ? "#EDF6F8" : "#041720"
            opacity: .76
            border.width: 1
            border.color: root.lightMode ? "#A7CDD5" : "#174B5A"

            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                radius: 12
                color: "transparent"
                border.width: 1
                border.color: root.lightMode ? "#FFFFFF" : "#0C2C37"
                opacity: .34
            }

            Column {
                anchors.fill:parent
                anchors.margins:14
                spacing:8

                Text { text:"DÉTAILS DU CHAMP"; color:root.textDim; opacity:.72; font.pixelSize:8; font.weight:Font.DemiBold; font.letterSpacing:1.0 }
                Rectangle { width:parent.width; height:1; color:root.lightMode?"#C2DADF":"#11343F" }
                Text { text:root.activeLayer.toUpperCase()+" · CHAMP"; color:root.textSoft; font.pixelSize:9; font.weight:Font.DemiBold; font.letterSpacing:1.0 }
                Text {
                    text: root.activeLayer==="wind"
                          ? (weatherBridge.locationName ? Number(weatherBridge.windSpeed).toFixed(0)+" km/h · → "+root.windToText() : "—")
                          : (root.activeLayer==="temperature" ? root.tempText(weatherBridge.temperature)
                             : root.activeLayer==="rain" ? Number(weatherBridge.precipitation).toFixed(1)+" mm"
                             : root.activeLayer==="clouds" ? weatherBridge.weatherLabel : "1013 hPa")
                    color:root.textMain
                    font.pixelSize:24
                    font.weight:Font.Light
                }

                Rectangle {
                    width:parent.width
                    height:34
                    radius:8
                    color:root.lightMode?"#DFEDF0":"#08232D"
                    border.width:1
                    border.color:root.lightMode?"#BAD6DC":"#154755"
                    Text { anchors.left:parent.left; anchors.leftMargin:9; anchors.verticalCenter:parent.verticalCenter; text:"POINT ACTUEL"; color:root.textDim; font.pixelSize:7; font.weight:Font.DemiBold }
                    Text { anchors.right:parent.right; anchors.rightMargin:9; anchors.verticalCenter:parent.verticalCenter; text:root.activeLayer==="wind"?(weatherBridge.locationName?Number(weatherBridge.windSpeed).toFixed(0)+" km/h · → "+root.windToText():"—"):root.tempText(weatherBridge.temperature); color:root.textMain; font.pixelSize:9; font.weight:Font.DemiBold }
                }

                Repeater {
                    model:[
                        ["Direction","De "+root.windFromText()+" → "+root.windToText()],
                        ["Humidité",weatherBridge.humidity+" %"],
                        ["Précip.",Number(weatherBridge.precipitation).toFixed(1)+" mm"],
                        ["Ressenti",root.tempText(weatherBridge.feelsLike)],
                        ["Source","Open-Meteo"]
                    ]
                    Row {
                        width:parent.width
                        Text { width:parent.width*.52; text:modelData[0]; color:root.textDim; opacity:.7; font.pixelSize:8 }
                        Text { width:parent.width*.48; horizontalAlignment:Text.AlignRight; text:modelData[1]; color:root.textSoft; font.pixelSize:8 }
                    }
                }
            }
        }

        // Location tag.
        Rectangle {
            z: 43
            x: mapFrame.width*.50+18
            y: mapFrame.height*.50-14
            height:28
            width:targetLabel.implicitWidth+16
            radius:7
            color:root.lightMode?"#EDF6F8":"#03151E"
            opacity:.95
            border.width:1
            border.color:root.lightMode?"#A8CED6":"#1D5363"
            visible:weatherBridge.locationName.length>0
            Text { id:targetLabel; anchors.centerIn:parent; text:weatherBridge.locationName; color:root.textMain; font.pixelSize:8; font.weight:Font.DemiBold; font.letterSpacing:.5 }
        }

        // Active-layer scale: restrained Windy-like weather legend.
        Rectangle {
            z: 43
            anchors.left: parent.left
            anchors.bottom: forecastStrip.top
            anchors.leftMargin: 18
            anchors.bottomMargin: 10
            width: 212
            height: 38
            radius: 10
            color: root.lightMode ? "#EAF4F6" : "#03151E"
            opacity: .76
            border.width: 1
            border.color: root.lightMode ? "#A8CED6" : "#174A59"

            Text {
                x:10; y:7
                text: root.activeLayer==="wind" ? "VITESSE DU VENT"
                     : root.activeLayer==="rain" ? "PRÉCIPITATIONS"
                     : root.activeLayer==="temperature" ? "TEMPÉRATURE"
                     : root.activeLayer==="clouds" ? "COUVERTURE NUAGEUSE" : "PRESSION"
                color: root.textDim
                opacity: .72
                font.pixelSize: 7
                font.weight: Font.DemiBold
                font.letterSpacing: .8
            }

            Rectangle {
                x:10; y:21
                width:130; height:5; radius:3
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "#21BFC5" }
                    GradientStop { position: .42; color: "#2C8AE7" }
                    GradientStop { position: .72; color: "#655DDC" }
                    GradientStop { position: 1.0; color: "#9B4CE2" }
                }
            }

            Text {
                anchors.right: parent.right
                anchors.rightMargin: 10
                y:17
                text: root.activeLayer==="wind" ? Number(weatherBridge.windSpeed).toFixed(0)+" km/h"
                     : root.activeLayer==="temperature" ? root.tempText(weatherBridge.temperature)
                     : root.activeLayer==="rain" ? Number(weatherBridge.precipitation).toFixed(1)+" mm"
                     : root.activeLayer==="clouds" ? weatherBridge.weatherLabel : "1013 hPa"
                color: root.textMain
                font.pixelSize: 8
                font.weight: Font.DemiBold
            }
        }

        // Premium forecast strip.
        Rectangle {
            id: forecastStrip
            z: 44
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            anchors.bottomMargin: 14
            height: 96
            radius: 13
            color: root.lightMode ? "#EDF6F8" : "#03151E"
            opacity: .86
            border.width: 1
            border.color: root.lightMode ? "#A6CDD5" : "#174B5A"

            Canvas {
                id: forecastCanvas
                anchors.fill:parent
                anchors.margins:8

                function roundedRect(c,x,y,w,h,r) {
                    var rr=Math.min(r,w/2,h/2)
                    c.beginPath()
                    c.moveTo(x+rr,y)
                    c.lineTo(x+w-rr,y)
                    c.quadraticCurveTo(x+w,y,x+w,y+rr)
                    c.lineTo(x+w,y+h-rr)
                    c.quadraticCurveTo(x+w,y+h,x+w-rr,y+h)
                    c.lineTo(x+rr,y+h)
                    c.quadraticCurveTo(x,y+h,x,y+h-rr)
                    c.lineTo(x,y+rr)
                    c.quadraticCurveTo(x,y,x+rr,y)
                    c.closePath()
                }

                function txt(c,text,x,y,font,color,alpha) {
                    c.save()
                    c.globalAlpha = alpha === undefined ? 1.0 : alpha
                    c.font = font
                    c.fillStyle = color
                    c.textAlign = "center"
                    c.textBaseline = "middle"
                    c.fillText(String(text),x,y)
                    c.restore()
                }

                onPaint: {
                    var c=getContext("2d")
                    c.clearRect(0,0,width,height)

                    var gap=4
                    var cellW=(width-gap*6)/7
                    var cellH=height
                    var hasAny=root.forecastDays && root.forecastDays.length>0

                    for(var i=0;i<7;i++){
                        var x=i*(cellW+gap)
                        var data=root.forecastSlot(i)
                        var has=i<root.forecastDays.length && root.forecastDays[i]!==undefined && root.forecastDays[i]!==null

                        if(i===0 && has){
                            roundedRect(c,x,0,cellW,cellH,10)
                            c.fillStyle=root.lightMode?"#D7EDF2":"#0B3040"
                            c.fill()
                            c.strokeStyle=root.cyan
                            c.lineWidth=1
                            c.stroke()
                        }

                        var alpha=has?1.0:.34
                        txt(
                            c,
                            has ? data.day : "—",
                            x+cellW/2,
                            13,
                            "600 8px 'Segoe UI'",
                            i===0 && has ? root.cyan : root.textDim,
                            alpha
                        )

                        txt(
                            c,
                            has ? data.icon : "·",
                            x+cellW/2,
                            35,
                            "18px 'Segoe UI Symbol'",
                            root.cyan2,
                            alpha
                        )

                        var temps=has
                            ? root.tempText(data.max)+" / "+root.tempText(data.min)
                            : "— / —"
                        txt(
                            c,
                            temps,
                            x+cellW/2,
                            57,
                            "600 10px 'Segoe UI'",
                            root.textMain,
                            alpha
                        )

                        var rain=has && data.rain!==null && data.rain!==undefined
                            ? data.rain+"%"
                            : "—"
                        txt(
                            c,
                            rain,
                            x+cellW/2,
                            72,
                            "7px 'Segoe UI'",
                            root.textDim,
                            alpha*.72
                        )
                    }

                    if(!hasAny){
                        txt(
                            c,
                            "PRÉVISIONS EN ATTENTE",
                            width/2,
                            height/2,
                            "600 8px 'Segoe UI'",
                            root.textDim,
                            .46
                        )
                    }
                }

                Component.onCompleted: requestPaint()
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
            }
        }
    }

    Text {
        anchors.left:parent.left
        anchors.leftMargin:38
        anchors.bottom:parent.bottom
        anchors.bottomMargin:14
        text:"ATMOSPHERIC FIELD · VISUAL LAYER"
        color:root.textDim
        opacity:.34
        font.pixelSize:7
        font.letterSpacing:1.2
    }

    Text {
        anchors.right:parent.right
        anchors.rightMargin:28
        anchors.bottom:parent.bottom
        anchors.bottomMargin:14
        text:weatherBridge.updatedAt
              ? "DATA · OPEN-METEO · NATURAL EARTH LOCAL · "+weatherBridge.updatedAt
              : "DATA · OPEN-METEO · NATURAL EARTH · TERRAIN TILES"
        color:root.textDim
        opacity:.34
        font.pixelSize:7
        font.letterSpacing:1.2
    }

    Rectangle {
        z:120
        visible:weatherBridge.error.length>0
        anchors.horizontalCenter:parent.horizontalCenter
        anchors.top:header.bottom
        anchors.topMargin:8
        width:Math.min(520,parent.width-80)
        height:38
        radius:10
        color:root.lightMode?"#FFF2F2":"#2A1518"
        border.width:1
        border.color:root.lightMode?"#E6A6A6":"#77333A"
        Text { anchors.centerIn:parent; text:weatherBridge.error; color:root.lightMode?"#8B3535":"#FFA0A7"; font.pixelSize:9 }
    }
}
