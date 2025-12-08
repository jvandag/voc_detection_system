

class EnvironmentalChamber:
    def __init__(
        self, 
        name: str, 
        group: str,
        chamber_slot: int, # where on the test bench the chamber is physically located
        allow_multi_valves: bool = False,
    ):  
        self.name = name
        self.group = group
        self.chamber_slot = chamber_slot
        
        # When true allows multiple valves connected to the same chamber to be opened at once
        # Ex: gas valve and vacuum or ambient release valve
        self.allow_multi_valves = allow_multi_valves
        self.status = "NORMAL"
        
