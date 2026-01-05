# Dissolved Oxygen (DO) Module for FLake

## Overview

This implementation extends the FLake lake temperature model with a minimal but realistic dissolved oxygen (DO) module. The DO module simulates oxygen dynamics using FLake's temperature and mixing outputs.

## Files Added/Modified

### New Files
- **`oxygen_module.py`**: Standalone Python module containing all DO calculation functions

### Modified Files
- **`FLAKE_SOUTHCENTERLAKE (2).ipynb`**: Extended with DO integration
  - Cell 25: Oxygen module import
  - Cell 26: Main simulation (modified to include DO initialization, stepping, and output)
  - Cell 28: New DO diagnostic plots and validation

## DO Model Description

### Two-State Model
The DO module uses two prognostic variables:
- **Cs(t)**: Mixed-layer DO concentration (mg/L)
- **Cb(t)**: Bottom/deep representative DO concentration (mg/L)

### Self-Similar Profile Reconstruction
The full DO profile C(z,t) is reconstructed using the same self-similar shape function as FLake's temperature profile:

```
C(z) = Cs                          for 0 ≤ z ≤ h
C(z) = Cs - (Cs-Cb)*Φ(ζ)          for h < z ≤ D
```

where:
- z = depth from surface (m)
- h = mixed-layer depth (m)
- D = total lake depth (m)
- ζ = (z - h)/(D - h) = normalized thermocline coordinate
- Φ(ζ) = FLake's shape function with parameter C_T

### Physical Processes

1. **Air-Water Reaeration** (`F_atm`)
   - Wind-based gas transfer using Cole & Caraco (1998) formula
   - Temperature-corrected Schmidt number (Wanninkhof 1992)
   - Suppressed when ice cover is present

2. **Interlayer Exchange** (`F_ex`)
   - **Entrainment mode** (h deepening): Entrains water from thermocline
   - **Diffusive mode** (stratified): Turbulent diffusion across h
   - Uses thin-layer averaging for entrained concentration

3. **Sediment Oxygen Demand** (`SOD`)
   - Temperature-dependent: SOD(T) = SOD_20 × θ^(T-20)
   - Applied to bottom/deep layer only
   - Default: SOD_20 = 1.0 g-O2/m²/day, θ = 1.08

4. **Water-Column Respiration** (`R_s`, `R_d`)
   - Separate surface and deep rates
   - Temperature-dependent: R(T) = R_20 × θ^(T-20)
   - Default: R_20 = 0.2 mg/L/day (surface), 0.15 mg/L/day (deep)

### Update Equations

**Mixed layer:**
```
dCs/dt = F_atm - F_ex/h - R_s
```

**Deep layer:**
Solved via constraint from self-similar mean:
```
C̄_deep = Cs - (Cs - Cb) × C_Φ
```
where C_Φ = ∫₀¹ Φ(ζ) dζ

**Fully mixed condition:**
When h ≥ D - ε: Cs = Cb (uniform profile)

## Configurable Parameters

Located in the main simulation cell (Cell 26), the `DO_params` dictionary:

```python
DO_params = {
    'SOD_20': 1.0,           # Sediment oxygen demand at 20°C (g-O2/m²/day)
    'R_20_surface': 0.2,     # Surface respiration at 20°C (mg/L/day)
    'R_20_deep': 0.15,       # Deep respiration at 20°C (mg/L/day)
    'theta_sod': 1.08,       # Temperature coefficient for SOD
    'theta_R': 1.08,         # Temperature coefficient for respiration
    'K_ex': 0.01,            # Diffusive exchange coefficient (m/day)
    'constant_k600': None,   # Constant k600 (m/day), None = wind-based
    'altitude_m': 0.0,       # Lake altitude (m above sea level)
}
```

### Tuning Guidelines

- **Oligotrophic lakes**: Lower SOD_20 (0.2-0.5), lower R_20 (0.05-0.1)
- **Eutrophic lakes**: Higher SOD_20 (1.5-3.0), higher R_20 (0.3-0.8)
- **Shallow lakes**: Increase K_ex (0.05-0.1) for stronger mixing
- **High-altitude lakes**: Set altitude_m for pressure correction

## Output Columns Added

The following columns are added to the output Excel file:

| Column | Description | Units |
|--------|-------------|-------|
| `Cs` | Mixed-layer DO concentration | mg/L |
| `Cb` | Bottom DO concentration | mg/L |
| `Cbar_d` | Mean deep-layer DO | mg/L |
| `DO_sat` | O2 saturation concentration | mg/L |
| `DO_min` | Minimum DO in profile | mg/L |
| `F_atm` | Reaeration flux | mg/L/day |
| `F_ex` | Interlayer exchange flux | mg/L/day |
| `SOD_rate` | Sediment oxygen demand rate | mg/L/day |
| `R_s` | Surface respiration rate | mg/L/day |
| `R_d` | Deep respiration rate | mg/L/day |

## Diagnostic Plots

Cell 28 generates comprehensive DO diagnostics:

1. **Time Series Plots**:
   - (a) DO concentrations (Cs, Cb, DO_min, saturation)
   - (b) Oxygen fluxes (reaeration, interlayer exchange)
   - (c) Oxygen sinks (SOD, respiration)
   - (d) Stratification context (h_ML, ice cover)

2. **Profile Plots**:
   - Selected seasonal snapshots (summer, winter, fall, spring)
   - Reconstructed C(z) profiles
   - Hypoxic threshold (2 mg/L) reference line

3. **Validation Checks**:
   - ✅ Fully mixed condition: Cs ≈ Cb when h ≈ D
   - ✅ Ice suppression: F_atm ≈ 0 when H_ice > 0
   - ✅ Stratification: Cb declines faster than Cs in summer
   - ✅ Physical bounds: 0 ≤ DO ≤ 25 mg/L

## Usage

### Running the Notebook

1. Ensure dependencies are installed:
   ```bash
   pip install numpy pandas matplotlib openpyxl f90nml
   ```

2. Run all cells in order (Cells 0-28)

3. The simulation will:
   - Load FLake configuration from `South_Center_Lake.nml`
   - Load forcing from `South_Center_2017-2020.xlsx`
   - Run FLake temperature model
   - Run DO module coupled to FLake
   - Generate output Excel file with DO columns
   - Create diagnostic plots

### Modifying DO Parameters

Edit `DO_params` dictionary in Cell 26 before running the simulation:

```python
DO_params = {
    'SOD_20': 2.0,        # Example: increase for eutrophic lake
    'R_20_surface': 0.4,  # Example: increase for high productivity
    # ... other parameters
}
```

### Accessing DO Functions Programmatically

```python
import oxygen_module as ox

# Calculate saturation
C_sat = ox.O2_saturation(T_celsius=20.0, altitude_m=0.0)

# Step oxygen forward one timestep
result = ox.step_oxygen(
    Cs_old=8.0, Cb_old=4.0,
    T_surface=20.0, T_bottom=10.0,
    h_ML_old=5.0, h_ML_new=5.5,
    depth_w=17.0, C_T=0.7,
    ice_thickness=0.0, U10=3.0,
    dt=86400.0,
    SOD_20=1.0, R_20_surface=0.2, R_20_deep=0.15
)

# Reconstruct profile
z_grid = np.linspace(0, 17, 100)
DO_profile = ox.reconstruct_DO_profile(
    z_grid, Cs=8.0, Cb=4.0,
    h_ML=5.0, depth_w=17.0, C_T=0.7
)
```

## Technical Notes

### Numerical Methods
- **Shape function integration**: Trapezoidal rule with 50 points
- **Entrainment**: Thin-layer averaging (ε_ent = 0.1 by default)
- **Time stepping**: Explicit Euler, same dt as FLake
- **Bounds**: DO clamped to [0, 25] mg/L

### Assumptions & Limitations
1. **No vertical grid solver**: Uses self-similar profile (fast, no diffusion PDE)
2. **No photosynthesis**: Can be added via chlorophyll-based production term
3. **Constant BOD**: Could extend to prognostic BOD with decay
4. **No nitrification**: Simplified respiration only
5. **Homogeneous mixed layer**: Assumes Cs uniform in 0 ≤ z ≤ h

### Known Behavior
- Ice periods: DO declines due to respiration/SOD, no reaeration
- Deep mixing events: Cs and Cb converge rapidly
- Summer stratification: Cb can become hypoxic if SOD/R_d are high
- Wind events: Reaeration spikes in F_atm

## References

### Oxygen Saturation
- Benson, B.B., and Krause, D. (1984). The concentration and isotopic fractionation of oxygen dissolved in freshwater and seawater in equilibrium with the atmosphere. *Limnology and Oceanography*, 29(3), 620-632.

### Gas Transfer
- Cole, J.J., and Caraco, N.F. (1998). Atmospheric exchange of carbon dioxide in a low-wind oligotrophic lake measured by the addition of SF6. *Limnology and Oceanography*, 43(4), 647-656.
- Wanninkhof, R. (1992). Relationship between wind speed and gas exchange over the ocean. *Journal of Geophysical Research*, 97(C5), 7373-7382.

### FLake Model
- Mironov, D.V. (2008). Parameterization of lakes in numerical weather prediction. Description of a lake model. COSMO Technical Report No. 11.

## Version History

- **v1.0** (2026-01-05): Initial implementation
  - Two-layer DO model with self-similar profiles
  - Air-water exchange, SOD, respiration, interlayer exchange
  - Integrated with FLake notebook
  - Diagnostic plots and validation checks

## Contact

For questions or issues with the DO module implementation, please refer to the oxygen_module.py source code documentation.
