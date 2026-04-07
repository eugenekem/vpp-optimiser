class Battery:
    """
    Represents a single battery asset in the VPP portfolio.
    Handles state of charge, charge/discharge logic, and constraints.
    """

    def __init__(self, name, mw, duration_hours, region, dno,
                 solar_mw=0, efficiency=0.90, soc_min=0.10, soc_max=0.90):
        
        self.name = name
        self.mw = mw                          # Max charge/discharge power (MW)
        self.duration_hours = duration_hours  # Battery duration (hours)
        self.capacity_mwh = mw * duration_hours  # Total energy capacity (MWh)
        self.region = region
        self.dno = dno
        self.solar_mw = solar_mw              # Co-located solar capacity (MW), 0 if standalone
        self.efficiency = efficiency          # Round-trip efficiency
        self.soc_min = soc_min                # Minimum SOC (10%)
        self.soc_max = soc_max                # Maximum SOC (90%)

        # Usable energy capacity accounting for SOC limits
        self.usable_mwh = self.capacity_mwh * (soc_max - soc_min)

        # Initialise SOC at 50%
        self.soc = 0.50
        self.energy_mwh = self.soc * self.capacity_mwh

    def charge(self, power_mw, duration_hours=0.5):
        """Charge the battery for a given power and duration (default 30 min settlement period)."""
        if power_mw <= 0:
            raise ValueError("Charge power must be positive")
        if power_mw > self.mw:
            raise ValueError(f"Charge power {power_mw} MW exceeds max {self.mw} MW")

        energy_in = power_mw * duration_hours * self.efficiency
        new_energy = self.energy_mwh + energy_in
        new_soc = new_energy / self.capacity_mwh

        if new_soc > self.soc_max:
            print(f"  [{self.name}] Charge limited by SOC max ({self.soc_max*100:.0f}%)")
            self.energy_mwh = self.soc_max * self.capacity_mwh
            self.soc = self.soc_max
        else:
            self.energy_mwh = new_energy
            self.soc = new_soc

    def discharge(self, power_mw, duration_hours=0.5):
        """Discharge the battery for a given power and duration (default 30 min settlement period)."""
        if power_mw <= 0:
            raise ValueError("Discharge power must be positive")
        if power_mw > self.mw:
            raise ValueError(f"Discharge power {power_mw} MW exceeds max {self.mw} MW")

        energy_out = power_mw * duration_hours / self.efficiency
        new_energy = self.energy_mwh - energy_out
        new_soc = new_energy / self.capacity_mwh

        if new_soc < self.soc_min:
            print(f"  [{self.name}] Discharge limited by SOC min ({self.soc_min*100:.0f}%)")
            self.energy_mwh = self.soc_min * self.capacity_mwh
            self.soc = self.soc_min
        else:
            self.energy_mwh = new_energy
            self.soc = new_soc

    def available_charge_mw(self):
        """How much charge power is available given current SOC."""
        headroom_mwh = (self.soc_max - self.soc) * self.capacity_mwh
        return min(self.mw, headroom_mwh / (0.5 * self.efficiency))

    def available_discharge_mw(self):
        """How much discharge power is available given current SOC."""
        available_mwh = (self.soc - self.soc_min) * self.capacity_mwh
        return min(self.mw, available_mwh * self.efficiency / 0.5)

    def status(self):
        """Print current asset status."""
        print(f"\n{self.name} | {self.region} | {self.mw} MW / {self.capacity_mwh} MWh")
        print(f"  SOC: {self.soc*100:.1f}% | Energy: {self.energy_mwh:.1f} MWh")
        print(f"  Available charge: {self.available_charge_mw():.1f} MW")
        print(f"  Available discharge: {self.available_discharge_mw():.1f} MW")
        if self.solar_mw > 0:
            print(f"  Co-located solar: {self.solar_mw} MW")


# --- Instantiate the 5 asset portfolio ---

assets = [
    Battery("Battery_1", mw=10,  duration_hours=2, region="North Scotland", dno="SSEN Transmission"),
    Battery("Battery_2", mw=25,  duration_hours=4, region="North England",  dno="Northern Powergrid"),
    Battery("Battery_3", mw=50,  duration_hours=4, region="South England",  dno="National Grid NGET"),
    Battery("Battery_4", mw=20,  duration_hours=4, region="South Scotland", dno="SP Transmission",  solar_mw=15),
    Battery("Battery_5", mw=40,  duration_hours=4, region="South England",  dno="National Grid NGET", solar_mw=30),
]


# --- Quick test ---
if __name__ == "__main__":
    print("=== VPP Asset Portfolio ===")
    for asset in assets:
        asset.status()

    print("\n--- Testing Battery_3 charge/discharge ---")
    b3 = assets[2]
    print(f"Initial SOC: {b3.soc*100:.1f}%")
    b3.charge(50)
    print(f"After charging 50 MW for 30 min: SOC = {b3.soc*100:.1f}%")
    b3.discharge(50)
    print(f"After discharging 50 MW for 30 min: SOC = {b3.soc*100:.1f}%")