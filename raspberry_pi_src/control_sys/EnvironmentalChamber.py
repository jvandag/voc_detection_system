

class EnvironmentalChamber:
    def __init__(
        self, 
        name: str, 
        group: str,
        slot: int, # where on the test bench the chamber is physically located
        gas_valve_channel: int,
        vac_valve_channel: int,
        allow_multi_valves: bool = False,
    ):  
        self.name = name
        self.group = group
        self.chamber_slot = slot
        self.gas_valve_pin = gas_valve_channel
        self.vac_valve_pin = vac_valve_channel
        
        # When true allows multiple valves connected to the same chamber to be opened at once
        # Ex: gas valve and vacuum or ambient release valve
        self.allow_multi_valves = allow_multi_valves
        self.status = "NORMAL"
        
