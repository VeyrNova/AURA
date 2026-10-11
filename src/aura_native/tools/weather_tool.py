from __future__ import annotations
from datetime import date, timedelta
from aura_native.weather.provider import WeatherProviderError

class WeatherTool:
    name="weather.get_forecast"
    def __init__(self, service): self.service=service
    def execute(self, payload):
        location=str((payload or {}).get("location") or "").strip(); target=str((payload or {}).get("date") or "").strip()
        if not location: return {"ok":False,"error":{"code":"weather_location_not_found","message":"A city is required"}}
        try:
            report=self.service.get_forecast(location, 7 if target else 2); day=next((row for row in report.daily if row.date == target), report.daily[0] if report.daily else None)
            data=report.as_payload(); data["requested_date"]=target or None; data["selected_day"]=None if day is None else day.__dict__.copy(); return {"ok":True,"tool":self.name,"data":data}
        except WeatherProviderError as exc: return {"ok":False,"tool":self.name,"error":{"code":exc.code,"message":exc.message}}

    @staticmethod
    def tomorrow(): return (date.today()+timedelta(days=1)).isoformat()
