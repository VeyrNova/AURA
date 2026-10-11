from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtCore import QUrl, QUrlQuery
from PySide6.QtGui import QDesktopServices
from threading import Thread
import math
from .routing import RoutePlace, RoutingError
from aura_native.location import CurrentLocationService
class NativeMapsBridge(QObject):
    placesChanged = Signal(); selectedChanged = Signal(); loadingChanged = Signal(); errorChanged = Signal(); routeChanged = Signal()
    _resultsReady = Signal(object, str, int)
    _locationReady = Signal(str, object, str, int)
    _routeResultReady = Signal(object, str, int)
    def __init__(self, service, parent=None, location_service=None):
        super().__init__(parent); self.service=service; self.location_service=location_service or CurrentLocationService(parent=self); self._current_location=None; self._places=[]; self._selected=None; self._loading=False; self._error=''; self._geometry=service.local_geometry(); self._world_geometry=service.local_geometry('world'); self._generation=0; self._resultsReady.connect(self._apply_results)
        self._route=None; self._origin=None; self._destination=None; self._candidates={'origin': [], 'destination': []}; self._routing_state='idle'; self._routing_error=''; self._route_generation=0; self._location_generation={'origin':0,'destination':0}; self._locationReady.connect(self._apply_location); self._routeResultReady.connect(self._apply_route)
    @Property('QVariantMap', constant=True)
    def geometry(self): return dict(self._geometry)
    @Property('QVariantMap', constant=True)
    def worldGeometry(self): return dict(self._world_geometry)
    @Property(bool, constant=True)
    def mapBaseReady(self): return bool(self._geometry.get('land_polygons') and self._geometry.get('coastlines'))
    @Property('QVariantMap', notify=routeChanged)
    def origin(self): return dict(self._origin or {})
    @Property('QVariantMap', notify=routeChanged)
    def destination(self): return dict(self._destination or {})
    @Property(str, notify=routeChanged)
    def currentLocationState(self): return self.location_service.state if self.location_service else 'unavailable'
    @Property(bool, notify=routeChanged)
    def currentLocationReady(self): return bool(self._current_location)
    @Property(str, notify=routeChanged)
    def currentLocationLabel(self):
        return {'requesting':'Localisation en cours…','ready':'Ma position','permission_denied':'Localisation Windows non autorisée','permission_required':'Autorisation de localisation nécessaire','unavailable':'Localisation Windows indisponible','timeout':'Localisation indisponible'}.get(self.currentLocationState, '')
    @Property('QVariantList', notify=routeChanged)
    def originCandidates(self): return list(self._candidates['origin'])
    @Property('QVariantList', notify=routeChanged)
    def destinationCandidates(self): return list(self._candidates['destination'])
    @Property('QVariantList', notify=routeChanged)
    def routeGeometry(self): return [list(point) for point in self._route.geometry] if self._route else []
    @Property(int, notify=routeChanged)
    def routePointCount(self): return len(self._route.geometry) if self._route else 0
    @Property(bool, notify=routeChanged)
    def routeReady(self): return self.routePointCount >= 2
    @Property(float, notify=routeChanged)
    def routeDistance(self): return self._route.distance_m if self._route else 0.0
    @Property(float, notify=routeChanged)
    def routeDuration(self): return self._route.duration_s if self._route else 0.0
    @Property(str, notify=routeChanged)
    def routeDistanceLabel(self): return f'{self.routeDistance/1000:.1f} km' if self._route else ''
    @Property(str, notify=routeChanged)
    def routeDurationLabel(self):
        if not self._route: return ''
        minutes=round(self.routeDuration/60)
        return f'{minutes//60} h {minutes%60:02d}' if minutes>=60 else f'{minutes} min'
    @Property('QVariantList', notify=routeChanged)
    def routeInstructions(self): return list(self._route.instructions) if self._route else []
    @Property(str, notify=routeChanged)
    def routingState(self): return self._routing_state
    @Property(str, notify=routeChanged)
    def routingError(self): return self._routing_error
    @Property(str, notify=routeChanged)
    def routingErrorLabel(self):
        return {'origin_missing':'Choisissez un départ.', 'destination_missing':'Choisissez une destination.',
                'same_origin_destination':'Le départ et la destination sont identiques.',
                'location_not_found':'Aucun lieu trouvé.', 'geocode_unavailable':'Recherche de lieu indisponible.',
                'no_route':'Aucun itinéraire trouvé.', 'provider_unavailable':'Service d’itinéraire indisponible.',
                'network_error':'Connexion au service d’itinéraire impossible.', 'rate_limited':'Service temporairement limité.',
                'invalid_result':'Réponse d’itinéraire invalide.'}.get(self._routing_error, self._routing_error)
    @Property(float, notify=routeChanged)
    def routeCenterLatitude(self): return self._route_viewport()[0]
    @Property(float, notify=routeChanged)
    def routeCenterLongitude(self): return self._route_viewport()[1]
    @Property(float, notify=routeChanged)
    def routeSpanKm(self): return self._route_viewport()[2]

    def _route_viewport(self):
        if not self._route: return (43.7, 7.25, 600.0)
        points=self._route.geometry
        lons=[point[0] for point in points]; lats=[max(-85,min(85,point[1])) for point in points]
        xs=[(lon+180)/360 for lon in lons]
        ys=[(1-math.log(math.tan(math.pi/4+math.radians(lat)/2))/math.pi)/2 for lat in lats]
        center_x=(min(xs)+max(xs))/2; center_y=(min(ys)+max(ys))/2
        center_lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*center_y))))
        world_width=max((max(xs)-min(xs))/.72,(max(ys)-min(ys))*1.6/.72,0.001)
        span=max(80.0,world_width*40075.016686*max(.1,abs(math.cos(math.radians(center_lat)))))
        return (center_lat,center_x*360-180,span)
    @Property('QVariantList', notify=placesChanged)
    def places(self): return list(self._places)
    @Property('QVariantMap', notify=selectedChanged)
    def selectedPlace(self): return dict(self._selected or {})
    @Property(bool, notify=loadingChanged)
    def loading(self): return self._loading
    @Property(str, notify=errorChanged)
    def error(self): return self._error
    @Slot(str)
    def search(self, query):
        self._loading=True; self.loadingChanged.emit(); self._error=''; self.errorChanged.emit(); self._generation+=1; generation=self._generation
        def worker():
            try:
                values=self.service.search(query)
                rows=[{'name':x.name, 'latitude':float(x.latitude), 'longitude':float(x.longitude), 'country':x.country} for x in values]
                error=''
            except Exception as exc: rows=[]; error=getattr(exc,'code','maps_search_error')
            self._resultsReady.emit(rows,error,generation)
        Thread(target=worker, daemon=True, name='AuraNativeMapsGeocode').start()
    @Slot(object,str,int)
    def _apply_results(self, rows, error, generation):
        if generation != self._generation: return
        self._places=list(rows); self._error=error; self._loading=False
        self.placesChanged.emit(); self.errorChanged.emit(); self.loadingChanged.emit()
    @Slot(int)
    def select(self, index):
        if 0 <= int(index) < len(self._places):
            self.clearRoute(); self._selected=self._places[int(index)]; self.selectedChanged.emit()

    def _search_location(self, kind, query):
        if kind not in self._candidates: return
        self._location_generation[kind]+=1; generation=self._location_generation[kind]
        self._routing_state='searching_'+kind; self._routing_error=''; self._candidates[kind]=[]; self.routeChanged.emit()
        def worker():
            try:
                places=[{'label':x.name + (f', {x.country}' if x.country else ''),'latitude':float(x.latitude),'longitude':float(x.longitude)} for x in self.service.search(query)]
                error='' if places else 'location_not_found'
            except Exception: places=[]; error='geocode_unavailable'
            self._locationReady.emit(kind,places,error,generation)
        Thread(target=worker,daemon=True,name='AuraNativeRouteGeocode').start()

    @Slot(str)
    def searchOrigin(self, query): self._search_location('origin',query)
    @Slot(str)
    def searchDestination(self, query): self._search_location('destination',query)
    @Slot(str,object,str,int)
    def _apply_location(self, kind, rows, error, generation):
        if generation != self._location_generation[kind]: return
        self._candidates[kind]=list(rows); self._routing_error=error; self._routing_state='idle' if not error else 'error'; self.routeChanged.emit()
    @Slot(int)
    def selectOrigin(self, index): self._select_endpoint('origin', index)
    @Slot(int)
    def selectDestination(self, index): self._select_endpoint('destination', index)
    def _select_endpoint(self, kind, index):
        candidates=self._candidates[kind]
        if not 0 <= int(index) < len(candidates): return
        self._route_generation+=1; self._route=None; self._routing_error=''; self._routing_state='idle'
        if kind=='origin': self._origin=dict(candidates[int(index)])
        else: self._destination=dict(candidates[int(index)])
        self._candidates[kind]=[]; self.routeChanged.emit()
    @Slot()
    def requestCurrentLocation(self):
        if not self.location_service:
            self.routeChanged.emit(); return
        try:
            self.location_service.locationChanged.connect(self._apply_current_location)
            self.location_service.stateChanged.connect(self.routeChanged)
        except (RuntimeError, TypeError): pass
        self.location_service.request(); self.routeChanged.emit()
    def _apply_current_location(self):
        self._current_location=self.location_service.location
        if self._current_location:
            self._origin={'label':'Ma position','latitude':self._current_location.latitude,'longitude':self._current_location.longitude}
        self.routeChanged.emit()
    @Slot()
    def calculateRoute(self):
        if not self._origin or not self._destination:
            self._routing_error='origin_missing' if not self._origin else 'destination_missing'; self._routing_state='error'; self.routeChanged.emit(); return
        origin=RoutePlace(self._origin['label'],self._origin['latitude'],self._origin['longitude'])
        destination=RoutePlace(self._destination['label'],self._destination['latitude'],self._destination['longitude'])
        self._route_generation+=1; generation=self._route_generation; self._route=None; self._routing_error=''; self._routing_state='routing'; self.routeChanged.emit()
        def worker():
            try: result=self.service.calculate_route(origin,destination); error=''
            except RoutingError as exc: result=None; error=exc.code
            except Exception: result=None; error='provider_unavailable'
            self._routeResultReady.emit(result,error,generation)
        Thread(target=worker,daemon=True,name='AuraNativeOSRMRoute').start()
    @Slot(object,str,int)
    def _apply_route(self, result, error, generation):
        if generation != self._route_generation: return
        self._route=result; self._routing_error=error; self._routing_state='ready' if result else 'error'; self.routeChanged.emit()
    @Slot()
    def clearRoute(self):
        self._route_generation+=1; self._route=None; self._routing_state='idle'; self._routing_error=''; self._origin=None; self._destination=None; self._candidates={'origin': [],'destination': []}; self.routeChanged.emit()
    @Slot(result=bool)
    def openMapFix(self): return bool(QDesktopServices.openUrl(QUrl('https://www.openstreetmap.org/fixthemap')))
    @Slot(result=bool)
    def openGoogleMaps(self):
        if not self._origin or not self._destination: return False
        query = QUrlQuery()
        query.addQueryItem('api', '1')
        query.addQueryItem('origin', f"{self._origin['latitude']},{self._origin['longitude']}")
        query.addQueryItem('destination', f"{self._destination['latitude']},{self._destination['longitude']}")
        query.addQueryItem('travelmode', 'driving')
        query.addQueryItem('dir_action', 'navigate')
        url = QUrl('https://www.google.com/maps/dir/')
        url.setQuery(query)
        return bool(QDesktopServices.openUrl(url))
