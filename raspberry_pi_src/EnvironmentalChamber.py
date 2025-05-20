

class EnvironmentalChamber:
    def __init__(
        self, 
        name: str, 
        gas_valve_pin: int,
        vac_valve_pin: int,
        allow_multi_valves: bool = False,
        chamberPurgeFunc=None,
    ):
        
        self.name = name
        self.gas_valve_pin = gas_valve_pin
        self.vac_valve_pin = vac_valve_pin
        
        # When true allows multiple valves connected to the same chamber to be opened at once
        # Ex: gas valve and vacuum or ambient release valve
        self.allow_multi_valves = allow_multi_valves
        self.status = "NORMAL"
        
