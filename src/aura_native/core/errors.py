from dataclasses import dataclass
class BusClosedError(RuntimeError): pass
class BusCapacityError(RuntimeError): pass
@dataclass(frozen=True)
class DeliveryFailure:
    event_name:str; subscriber_id:int; error_type:str; message:str
