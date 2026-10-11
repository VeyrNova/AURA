import json
import threading
from PySide6.QtCore import QObject, Property, Signal, Slot
from aura_native.weather.models import WeatherLocation

class NativeWeatherBridge(QObject):
    weatherChanged = Signal()
    _completed = Signal(object, str, int)
    _cityResultsReady = Signal(object, str)
    def __init__(self, service, parent=None, default_location='Nice', map_service=None):
        super().__init__(parent); self._service=service; self._location=default_location; self._selected_location=None; self._report=None; self._loading=False; self._city_loading=False; self._error=''; self._generation=0; self._city_results=[]; self._map_service=map_service; self._completed.connect(self._apply_result); self._cityResultsReady.connect(self._apply_city_results)
    @Property('QVariantMap', constant=True)
    def regionalGeometry(self): return self._map_service.local_geometry('regional') if self._map_service else {}
    @Property('QVariantMap', constant=True)
    def worldGeometry(self): return self._map_service.local_geometry('world') if self._map_service else {}
    @Property(bool, notify=weatherChanged)
    def loading(self): return self._loading
    @Property(str, notify=weatherChanged)
    def error(self): return self._error
    @Property(str, notify=weatherChanged)
    def lastQuery(self): return self._location
    @Property('QVariantList', notify=weatherChanged)
    def cityResults(self): return list(self._city_results)
    @Property(bool, notify=weatherChanged)
    def citySearchLoading(self): return self._city_loading
    @Property(str, notify=weatherChanged)
    def updatedAt(self): return self._report.current.observed_at or '' if self._report and self._report.current else ''
    @Property(float, notify=weatherChanged)
    def precipitation(self): return 0.0
    @Property(str, notify=weatherChanged)
    def locationName(self): return self._report.location.name if self._report else ''
    @Property(str, notify=weatherChanged)
    def locationDetail(self): return self._report.location.country if self._report else ''
    @Property(float, notify=weatherChanged)
    def latitude(self): return self._report.location.latitude if self._report else 0.0
    @Property(float, notify=weatherChanged)
    def longitude(self): return self._report.location.longitude if self._report else 0.0
    @Property(float, notify=weatherChanged)
    def temperature(self): return self._report.current.temperature_c if self._report and self._report.current else 0.0
    @Property(float, notify=weatherChanged)
    def feelsLike(self): return self._report.current.apparent_temperature_c if self._report and self._report.current and self._report.current.apparent_temperature_c is not None else 0.0
    @Property(int, notify=weatherChanged)
    def humidity(self): return self._report.current.humidity_percent if self._report and self._report.current and self._report.current.humidity_percent is not None else 0
    @Property(float, notify=weatherChanged)
    def windSpeed(self): return self._report.current.wind_speed_kmh if self._report and self._report.current and self._report.current.wind_speed_kmh is not None else 0.0
    @Property(float, notify=weatherChanged)
    def windDegrees(self): return 0.0
    @Property(str, notify=weatherChanged)
    def windDirection(self): return '—'
    @Property(str, notify=weatherChanged)
    def weatherLabel(self): return self._report.current.condition if self._report and self._report.current else '—'
    @Property(str, notify=weatherChanged)
    def weatherIcon(self): return '☁'
    @Property(str, notify=weatherChanged)
    def forecastJson(self):
        return json.dumps([{'day':d.date,'date':d.date,'label':d.condition,'icon':'☁','max':d.max_temperature_c,'min':d.min_temperature_c,'rain':d.precipitation_probability_percent} for d in (self._report.daily if self._report else ())])
    @Property(str, notify=weatherChanged)
    def windFieldJson(self): return '{}'
    @Property(str, notify=weatherChanged)
    def terrainJson(self): return '{}'
    @Slot()
    def ensureLoaded(self):
        if self._report is None: self.refresh()
    @Slot()
    def refresh(self): self.searchCity(self._location)
    @Slot(str)
    def searchCity(self, location):
        self._location=str(location or self._location); self._loading=True; self._error=''; self._generation+=1; generation=self._generation; self.weatherChanged.emit()
        def worker():
            try: report=self._service.get_forecast(self._selected_location or self._location, 2); error=''
            except Exception as exc: report=None; error=getattr(exc,'code','weather_error')
            self._completed.emit(report,error,generation)
        threading.Thread(target=worker,daemon=True,name='AuraNativeWeather').start()
    @Slot(str)
    def searchLocations(self, query):
        self._city_loading=True; self._error=''; self._city_results=[]; self.weatherChanged.emit()
        def worker():
            try:
                values=self._service.search_locations(query)
                rows=[{'name':x.name,'country':x.country,'latitude':x.latitude,'longitude':x.longitude,'timezone':x.timezone} for x in values]
                error=''
            except Exception as exc: rows=[]; error=getattr(exc,'code','weather_error')
            self._cityResultsReady.emit(rows,error)
        threading.Thread(target=worker,daemon=True,name='AuraNativeWeatherGeocode').start()
    @Slot(object,str)
    def _apply_city_results(self, rows, error):
        self._city_results=list(rows or []); self._error=error; self._city_loading=False; self.weatherChanged.emit()
    @Slot('QVariantMap')
    def selectCity(self, city):
        self._city_results=[]; self._selected_location=WeatherLocation(str(city.get('name') or self._location),str(city.get('country') or ''),float(city.get('latitude')),float(city.get('longitude')),str(city.get('timezone') or 'UTC')); self.searchCity(self._selected_location.name)
    @Slot(object,str,int)
    def _apply_result(self,report,error,generation):
        if generation != self._generation: return
        if report is not None: self._report=report
        self._error=error; self._loading=False; self.weatherChanged.emit()
