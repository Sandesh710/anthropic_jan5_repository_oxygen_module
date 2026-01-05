"""
Minimal Dissolved Oxygen Module for FLake
==========================================

This module implements a two-layer dissolved oxygen (DO) model that couples
with FLake temperature and mixing outputs. It includes:

- Two prognostic states: Cs (mixed-layer DO), Cb (bottom/deep DO)
- Self-similar profile reconstruction using FLake's temperature shape function
- Physical processes:
  * Air-water reaeration (suppressed under ice)
  * Interlayer exchange (entrainment + diffusive)
  * Sediment oxygen demand (temperature-dependent)
  * Water-column respiration (bulk, temperature-dependent)

Author: Claude Code
Date: 2026-01-05
"""

import numpy as np
from typing import Dict, Tuple, Optional


# =============================================================================
# OXYGEN SATURATION
# =============================================================================

def O2_saturation(T_celsius: float, altitude_m: float = 0.0) -> float:
    """
    Calculate dissolved oxygen saturation concentration in freshwater.

    Uses the empirical formula from Benson & Krause (1984) as cited in
    ASCE (1992) and widely used in water quality modeling.

    Parameters
    ----------
    T_celsius : float
        Water temperature in degrees Celsius
    altitude_m : float, optional
        Altitude above sea level in meters (default: 0.0 = sea level)

    Returns
    -------
    float
        DO saturation concentration in mg/L

    References
    ----------
    Benson, B.B., and Krause, D. (1984). The concentration and isotopic
    fractionation of oxygen dissolved in freshwater and seawater in
    equilibrium with the atmosphere. Limnology and Oceanography, 29(3), 620-632.
    """
    # Absolute temperature in Kelvin
    T_K = T_celsius + 273.15

    # Scaled temperature
    T_s = np.log((298.15 - T_celsius) / T_K)

    # Natural logarithm of O2 solubility (at sea level, freshwater)
    # Coefficients from Benson & Krause (1984)
    ln_C = (-139.34411 +
            1.575701e5 / T_K -
            6.642308e7 / T_K**2 +
            1.2438e10 / T_K**3 -
            8.621949e11 / T_K**4)

    # Convert from mL/L to mg/L (multiply by density of O2)
    # O2 density at STP: 1.429 mg/mL
    C_sat_sealevel = np.exp(ln_C) * 1.429

    # Altitude correction (pressure decreases with altitude)
    # Approximate barometric pressure formula
    P_ratio = np.exp(-altitude_m / 8200.0)  # 8200m = scale height
    C_sat = C_sat_sealevel * P_ratio

    return C_sat


# =============================================================================
# SHAPE FUNCTION (PHI) - Reuse FLake's temperature profile shape
# =============================================================================

def Phi_theta(zeta: np.ndarray, C_T: float) -> np.ndarray:
    """
    FLake's self-similar temperature profile shape function.

    This is the same shape function used in FLake for temperature.
    It represents the normalized deviation from the mixed-layer value
    across the thermocline.

    Parameters
    ----------
    zeta : np.ndarray
        Normalized depth coordinate: zeta = (z - h) / (D - h)
        where z is depth, h is mixed-layer depth, D is total depth
        zeta ranges from 0 (at h) to 1 (at bottom)
    C_T : float
        Shape factor (typically 0.5 to 0.8)

    Returns
    -------
    np.ndarray
        Shape function values Phi(zeta) in range [0, 1]
    """
    # FLake polynomial shape function
    # Phi(0) = 0 at thermocline top
    # Phi(1) = 1 at bottom
    Phi = zeta**2 * (1.5 - 0.5 * zeta) * (1.0 + C_T * (1.0 - zeta))
    return Phi


def integrate_Phi(C_T: float, n_points: int = 50) -> float:
    """
    Numerically integrate the shape function over [0,1].

    Returns C_Phi = ∫₀¹ Phi(ζ) dζ

    Parameters
    ----------
    C_T : float
        Shape factor
    n_points : int
        Number of quadrature points

    Returns
    -------
    float
        Integral value
    """
    zeta = np.linspace(0, 1, n_points)
    Phi_vals = Phi_theta(zeta, C_T)
    C_Phi = np.trapz(Phi_vals, zeta)
    return C_Phi


def compute_entrained_concentration(Cs: float, Cb: float, C_T: float,
                                   eps_ent: float = 0.1,
                                   n_points: int = 20) -> float:
    """
    Compute the average DO concentration in the thin layer being entrained
    from the deep zone into the mixed layer.

    C_ent = (1/eps_ent) * ∫₀^{eps_ent} [Cs - (Cs-Cb)*Phi(ζ)] dζ

    Parameters
    ----------
    Cs : float
        Mixed-layer DO concentration (mg/L)
    Cb : float
        Bottom/deep DO concentration (mg/L)
    C_T : float
        Shape factor
    eps_ent : float
        Thickness of entrained layer as fraction of thermocline (default: 0.1)
    n_points : int
        Number of quadrature points

    Returns
    -------
    float
        Entrained concentration (mg/L)
    """
    zeta = np.linspace(0, eps_ent, n_points)
    Phi_vals = Phi_theta(zeta, C_T)
    C_profile = Cs - (Cs - Cb) * Phi_vals
    C_ent = np.trapz(C_profile, zeta) / eps_ent
    return C_ent


# =============================================================================
# REAERATION (AIR-WATER GAS EXCHANGE)
# =============================================================================

def gas_transfer_velocity(U10: Optional[float] = None,
                          T_celsius: float = 20.0,
                          constant_k600: Optional[float] = None) -> float:
    """
    Calculate gas transfer velocity (piston velocity) for oxygen.

    If wind speed U10 is provided, uses an empirical wind-based formula.
    Otherwise, uses a constant k600 value.

    Parameters
    ----------
    U10 : float, optional
        Wind speed at 10m height (m/s)
    T_celsius : float
        Water temperature (°C) for Schmidt number correction
    constant_k600 : float, optional
        Constant k600 value (m/day) if wind is not available

    Returns
    -------
    float
        Gas transfer velocity k_g in m/day

    References
    ----------
    Cole & Caraco (1998) for wind-based formula.
    Wanninkhof (1992) for Schmidt number correction.
    """
    # Schmidt number for O2 (temperature-dependent)
    # From Wanninkhof (1992)
    Sc = 1800.6 - 120.1*T_celsius + 3.7818*T_celsius**2 - 0.047608*T_celsius**3

    # Reference Schmidt number (for CO2 at 20°C, commonly 600)
    Sc_ref = 600.0

    if U10 is not None:
        # Cole & Caraco (1998) formula for lakes
        # k600 = 2.07 + 0.215 * U10^1.7  (cm/h)
        k600_cm_h = 2.07 + 0.215 * U10**1.7

        # Convert to m/day
        k600 = k600_cm_h * 0.01 * 24.0  # cm/h -> m/day
    else:
        # Use constant value (default: moderate exchange)
        if constant_k600 is None:
            constant_k600 = 0.5  # m/day (moderate exchange)
        k600 = constant_k600

    # Correct for O2 Schmidt number
    k_O2 = k600 * (Sc / Sc_ref)**(-0.5)

    return k_O2


def compute_reaeration(Cs: float, T_celsius: float, h_ML: float,
                      ice_present: bool = False,
                      U10: Optional[float] = None,
                      constant_k600: Optional[float] = None,
                      altitude_m: float = 0.0) -> float:
    """
    Compute reaeration flux (air-water oxygen exchange).

    F_atm = k_g * (C_sat - Cs) / h_ML

    Returns the rate of change in mg/L/day for the mixed layer.

    Parameters
    ----------
    Cs : float
        Mixed-layer DO concentration (mg/L)
    T_celsius : float
        Surface water temperature (°C)
    h_ML : float
        Mixed-layer depth (m)
    ice_present : bool
        True if ice cover exists (suppresses reaeration)
    U10 : float, optional
        Wind speed at 10m (m/s)
    constant_k600 : float, optional
        Constant gas transfer velocity (m/day)
    altitude_m : float
        Altitude (m) for saturation correction

    Returns
    -------
    float
        Reaeration rate in mg/L/day
    """
    if ice_present or h_ML < 0.01:
        return 0.0

    C_sat = O2_saturation(T_celsius, altitude_m)
    k_g = gas_transfer_velocity(U10, T_celsius, constant_k600)

    # F_atm in mg/L/day
    F_atm = k_g * (C_sat - Cs) / h_ML

    return F_atm


# =============================================================================
# SEDIMENT OXYGEN DEMAND (SOD)
# =============================================================================

def sediment_oxygen_demand(T_bottom_celsius: float,
                          SOD_20: float = 1.0,
                          theta_sod: float = 1.08) -> float:
    """
    Temperature-dependent sediment oxygen demand.

    SOD(T) = SOD_20 * theta_sod^(T - 20)

    Parameters
    ----------
    T_bottom_celsius : float
        Bottom water temperature (°C)
    SOD_20 : float
        SOD at 20°C in g-O2/m²/day (default: 1.0)
    theta_sod : float
        Temperature coefficient (default: 1.08)

    Returns
    -------
    float
        SOD in g-O2/m²/day
    """
    SOD = SOD_20 * theta_sod**(T_bottom_celsius - 20.0)
    return SOD


def compute_SOD_sink(T_bottom_celsius: float, depth_w: float, h_ML: float,
                    SOD_20: float = 1.0, theta_sod: float = 1.08) -> float:
    """
    Compute SOD sink rate for the deep layer.

    Returns the rate of change in mg/L/day.

    Parameters
    ----------
    T_bottom_celsius : float
        Bottom temperature (°C)
    depth_w : float
        Total lake depth (m)
    h_ML : float
        Mixed-layer depth (m)
    SOD_20 : float
        SOD at 20°C (g-O2/m²/day)
    theta_sod : float
        Temperature coefficient

    Returns
    -------
    float
        SOD sink rate in mg/L/day for deep layer
    """
    h_deep = max(depth_w - h_ML, 0.1)  # Avoid division by zero

    # SOD in g/m²/day
    SOD_flux = sediment_oxygen_demand(T_bottom_celsius, SOD_20, theta_sod)

    # Convert to mg/L/day:
    # g/m²/day / m = g/m³/day = 1000 mg/L/day
    SOD_sink = (SOD_flux * 1000.0) / h_deep

    return SOD_sink


# =============================================================================
# WATER-COLUMN RESPIRATION
# =============================================================================

def water_column_respiration(T_celsius: float,
                            R_20: float = 0.1,
                            theta_R: float = 1.08) -> float:
    """
    Temperature-dependent water column respiration rate.

    R(T) = R_20 * theta_R^(T - 20)

    Parameters
    ----------
    T_celsius : float
        Water temperature (°C)
    R_20 : float
        Respiration rate at 20°C (mg/L/day)
    theta_R : float
        Temperature coefficient (default: 1.08)

    Returns
    -------
    float
        Respiration rate in mg/L/day
    """
    R = R_20 * theta_R**(T_celsius - 20.0)
    return R


# =============================================================================
# INTERLAYER EXCHANGE
# =============================================================================

def compute_interlayer_exchange(
        Cs: float, Cb: float, C_T: float,
        h_ML_old: float, h_ML_new: float, dt: float,
        depth_w: float,
        K_ex: float = 0.01,
        eps_ent: float = 0.1) -> Tuple[float, float, str]:
    """
    Compute interlayer oxygen exchange flux.

    Two cases:
    - dhdt > 0 (deepening): entrainment flux based on thin layer averaging
    - dhdt <= 0 (stratified): diffusive exchange

    Parameters
    ----------
    Cs : float
        Mixed-layer DO (mg/L)
    Cb : float
        Bottom DO (mg/L)
    C_T : float
        Shape factor
    h_ML_old : float
        Previous mixed-layer depth (m)
    h_ML_new : float
        New mixed-layer depth (m)
    dt : float
        Time step (seconds)
    depth_w : float
        Total depth (m)
    K_ex : float
        Diffusive exchange coefficient (m/day) for stratified case
    eps_ent : float
        Entrainment layer thickness fraction

    Returns
    -------
    F_ex : float
        Exchange flux to mixed layer (mg/L/day)
    Cbar_d : float
        Mean deep layer concentration (mg/L)
    mode : str
        Exchange mode ('entrainment' or 'diffusive')
    """
    dhdt = (h_ML_new - h_ML_old) / dt  # m/s
    dhdt_per_day = dhdt * 86400.0  # m/day

    # Compute mean deep layer concentration
    C_Phi = integrate_Phi(C_T)
    Cbar_d = Cs - (Cs - Cb) * C_Phi

    if dhdt_per_day > 1e-6:  # Entrainment (deepening)
        # Compute entrained concentration
        C_ent = compute_entrained_concentration(Cs, Cb, C_T, eps_ent)

        # Entrainment flux: dhdt * (Cs - C_ent)
        # Positive dhdt brings water from deep to mixed layer
        h_ML_avg = 0.5 * (h_ML_old + h_ML_new)
        h_ML_avg = max(h_ML_avg, 0.1)

        F_ex = dhdt_per_day * (Cs - C_ent) / h_ML_avg
        mode = 'entrainment'

    else:  # Diffusive exchange (stratified or shoaling)
        # F_ex = K_ex * (Cs - Cbar_d) / h_ML
        h_ML_avg = 0.5 * (h_ML_old + h_ML_new)
        h_ML_avg = max(h_ML_avg, 0.1)

        F_ex = K_ex * (Cs - Cbar_d) / h_ML_avg
        mode = 'diffusive'

    return F_ex, Cbar_d, mode


# =============================================================================
# DO PROFILE RECONSTRUCTION
# =============================================================================

def reconstruct_DO_profile(z_grid: np.ndarray, Cs: float, Cb: float,
                           h_ML: float, depth_w: float, C_T: float,
                           eps_mixed: float = 0.01) -> np.ndarray:
    """
    Reconstruct full DO profile C(z) using self-similar shape.

    C(z) = Cs                               for 0 <= z <= h
    C(z) = Cs - (Cs-Cb)*Phi(zeta)          for h < z <= D

    If h >= D - eps: fully mixed, C(z) = Cs everywhere.

    Parameters
    ----------
    z_grid : np.ndarray
        Depth grid (m) from surface (0) to bottom (depth_w)
    Cs : float
        Mixed-layer DO (mg/L)
    Cb : float
        Bottom DO (mg/L)
    h_ML : float
        Mixed-layer depth (m)
    depth_w : float
        Total depth (m)
    C_T : float
        Shape factor
    eps_mixed : float
        Tolerance for fully mixed condition (m)

    Returns
    -------
    np.ndarray
        DO concentration profile (mg/L) at each z
    """
    C_profile = np.zeros_like(z_grid)

    # Fully mixed case
    if h_ML >= depth_w - eps_mixed:
        C_profile[:] = Cs
        return C_profile

    # Stratified case
    for i, z in enumerate(z_grid):
        if z <= h_ML:
            C_profile[i] = Cs
        else:
            zeta = (z - h_ML) / (depth_w - h_ML)
            zeta = np.clip(zeta, 0.0, 1.0)
            Phi = Phi_theta(np.array([zeta]), C_T)[0]
            C_profile[i] = Cs - (Cs - Cb) * Phi

    return C_profile


# =============================================================================
# MAIN DO STEPPING FUNCTION
# =============================================================================

def step_oxygen(
        # Current DO state
        Cs_old: float,
        Cb_old: float,
        # FLake outputs
        T_surface: float,  # °C
        T_bottom: float,   # °C
        h_ML_old: float,   # m
        h_ML_new: float,   # m
        depth_w: float,    # m
        C_T: float,        # shape factor
        ice_thickness: float = 0.0,  # m
        U10: Optional[float] = None,  # m/s
        # Time step
        dt: float = 86400.0,  # seconds
        # DO parameters
        SOD_20: float = 1.0,          # g-O2/m²/day
        R_20_surface: float = 0.1,    # mg/L/day
        R_20_deep: float = 0.1,       # mg/L/day
        theta_sod: float = 1.08,
        theta_R: float = 1.08,
        K_ex: float = 0.01,           # m/day
        constant_k600: Optional[float] = None,
        altitude_m: float = 0.0,
        eps_ent: float = 0.1,
        # Bounds
        C_min: float = 0.0,
        C_max: float = 25.0
    ) -> Dict[str, float]:
    """
    Advance dissolved oxygen state one time step forward.

    Solves:
        dCs/dt = F_atm/h - F_ex/h - R_s
        dCb/dt = F_ex/(D-h) - SOD/(D-h) - R_d

    with constraints from self-similar profile structure.

    Parameters
    ----------
    Cs_old, Cb_old : float
        Current DO concentrations (mg/L)
    T_surface, T_bottom : float
        Surface and bottom temperatures (°C)
    h_ML_old, h_ML_new : float
        Mixed-layer depth before and after FLake step (m)
    depth_w : float
        Total lake depth (m)
    C_T : float
        FLake shape factor
    ice_thickness : float
        Ice thickness (m), >0 suppresses reaeration
    U10 : float, optional
        Wind speed at 10m (m/s)
    dt : float
        Time step (seconds)
    SOD_20, R_20_surface, R_20_deep : float
        Oxygen sink parameters
    theta_sod, theta_R : float
        Temperature coefficients
    K_ex : float
        Diffusive exchange coefficient (m/day)
    constant_k600 : float, optional
        Constant gas transfer velocity if wind unavailable
    altitude_m : float
        Altitude for saturation calculation
    eps_ent : float
        Entrainment layer thickness fraction
    C_min, C_max : float
        Bounds for DO concentrations

    Returns
    -------
    dict
        Updated DO state and diagnostic variables:
        - Cs_new, Cb_new: new concentrations
        - Cbar_d: mean deep concentration
        - C_sat: saturation concentration
        - F_atm, F_ex: fluxes (mg/L/day)
        - SOD_rate, R_s, R_d: sink rates (mg/L/day)
        - exchange_mode: 'entrainment' or 'diffusive'
    """
    dt_days = dt / 86400.0

    # Check for fully mixed condition
    eps_mixed = 0.01
    fully_mixed = (h_ML_new >= depth_w - eps_mixed)

    if fully_mixed:
        # Enforce uniform DO
        C_uniform = 0.5 * (Cs_old + Cb_old)

        # Only reaeration and respiration (no interlayer exchange, no SOD for mixed)
        ice_present = ice_thickness > 0.001
        F_atm = compute_reaeration(C_uniform, T_surface, depth_w,
                                   ice_present, U10, constant_k600, altitude_m)
        R_avg = water_column_respiration(T_surface,
                                        0.5*(R_20_surface + R_20_deep), theta_R)

        # Update
        C_new = C_uniform + dt_days * (F_atm - R_avg)
        C_new = np.clip(C_new, C_min, C_max)

        C_sat = O2_saturation(T_surface, altitude_m)

        return {
            'Cs_new': C_new,
            'Cb_new': C_new,
            'Cbar_d': C_new,
            'C_sat': C_sat,
            'F_atm': F_atm,
            'F_ex': 0.0,
            'SOD_rate': 0.0,
            'R_s': R_avg,
            'R_d': R_avg,
            'exchange_mode': 'fully_mixed'
        }

    # Stratified case
    h_ML_avg = 0.5 * (h_ML_old + h_ML_new)
    h_ML_avg = max(h_ML_avg, 0.1)
    h_deep = depth_w - h_ML_avg
    h_deep = max(h_deep, 0.1)

    # 1. Reaeration
    ice_present = ice_thickness > 0.001
    F_atm = compute_reaeration(Cs_old, T_surface, h_ML_avg,
                              ice_present, U10, constant_k600, altitude_m)

    # 2. Interlayer exchange
    F_ex, Cbar_d, ex_mode = compute_interlayer_exchange(
        Cs_old, Cb_old, C_T, h_ML_old, h_ML_new, dt, depth_w, K_ex, eps_ent
    )

    # 3. Respiration
    R_s = water_column_respiration(T_surface, R_20_surface, theta_R)
    R_d = water_column_respiration(T_bottom, R_20_deep, theta_R)

    # 4. SOD
    SOD_rate = compute_SOD_sink(T_bottom, depth_w, h_ML_avg, SOD_20, theta_sod)

    # 5. Update equations
    # dCs/dt = F_atm - F_ex/h - R_s
    dCs_dt = F_atm - F_ex - R_s

    # dCb/dt: need to solve for Cb from mean deep layer constraint
    # Cbar_d = Cs - (Cs - Cb) * C_Phi
    # Mass balance in deep layer:
    # d(Cbar_d * h_deep)/dt = F_ex * h_ML - SOD_flux - R_d * h_deep
    # Approximate:
    C_Phi = integrate_Phi(C_T)

    # Deep layer mass rate of change (mg/L/day for whole deep layer)
    # Exchange brings F_ex from mixed layer perspective
    # Need to convert to deep layer rate:
    F_ex_deep = F_ex * h_ML_avg / h_deep

    dCbar_dt = F_ex_deep - SOD_rate - R_d

    # Update Cbar_d
    Cbar_d_new = Cbar_d + dt_days * dCbar_dt

    # Update Cs
    Cs_new = Cs_old + dt_days * dCs_dt

    # Solve for Cb from Cbar_d relationship
    # Cbar_d = Cs - (Cs - Cb) * C_Phi
    # => Cb = Cs - (Cs - Cbar_d) / C_Phi
    if C_Phi > 1e-6:
        Cb_new = Cs_new - (Cs_new - Cbar_d_new) / C_Phi
    else:
        Cb_new = Cs_new

    # Clamp to physical bounds
    Cs_new = np.clip(Cs_new, C_min, C_max)
    Cb_new = np.clip(Cb_new, C_min, C_max)

    C_sat = O2_saturation(T_surface, altitude_m)

    return {
        'Cs_new': Cs_new,
        'Cb_new': Cb_new,
        'Cbar_d': Cbar_d_new,
        'C_sat': C_sat,
        'F_atm': F_atm,
        'F_ex': F_ex,
        'SOD_rate': SOD_rate,
        'R_s': R_s,
        'R_d': R_d,
        'exchange_mode': ex_mode
    }


# =============================================================================
# DIAGNOSTIC FUNCTIONS
# =============================================================================

def compute_DO_min(z_grid: np.ndarray, Cs: float, Cb: float,
                   h_ML: float, depth_w: float, C_T: float) -> float:
    """
    Compute minimum DO in the water column.

    Parameters
    ----------
    z_grid : np.ndarray
        Depth grid (m)
    Cs, Cb : float
        Surface and bottom DO (mg/L)
    h_ML : float
        Mixed-layer depth (m)
    depth_w : float
        Total depth (m)
    C_T : float
        Shape factor

    Returns
    -------
    float
        Minimum DO concentration (mg/L)
    """
    profile = reconstruct_DO_profile(z_grid, Cs, Cb, h_ML, depth_w, C_T)
    return np.min(profile)


def compute_hypoxic_volume_fraction(z_grid: np.ndarray, Cs: float, Cb: float,
                                    h_ML: float, depth_w: float, C_T: float,
                                    threshold: float = 2.0) -> float:
    """
    Compute fraction of lake volume below DO threshold.

    Parameters
    ----------
    z_grid : np.ndarray
        Depth grid (m)
    Cs, Cb : float
        Surface and bottom DO (mg/L)
    h_ML : float
        Mixed-layer depth (m)
    depth_w : float
        Total depth (m)
    C_T : float
        Shape factor
    threshold : float
        Hypoxic threshold (mg/L), default 2.0

    Returns
    -------
    float
        Volume fraction below threshold (0 to 1)
    """
    profile = reconstruct_DO_profile(z_grid, Cs, Cb, h_ML, depth_w, C_T)
    hypoxic_mask = profile < threshold

    # Simple trapezoid integration
    dz = np.diff(z_grid)
    volume_hypoxic = np.sum(hypoxic_mask[:-1] * dz)
    total_volume = depth_w

    return volume_hypoxic / total_volume


if __name__ == "__main__":
    # Simple test
    print("Oxygen Module Test")
    print("=" * 70)

    # Test saturation
    for T in [0, 10, 20, 30]:
        C_sat = O2_saturation(T)
        print(f"O2 saturation at {T}°C: {C_sat:.2f} mg/L")

    print("\nTest step_oxygen:")
    result = step_oxygen(
        Cs_old=8.0, Cb_old=4.0,
        T_surface=20.0, T_bottom=10.0,
        h_ML_old=5.0, h_ML_new=5.5,
        depth_w=17.0, C_T=0.7,
        ice_thickness=0.0, U10=3.0,
        dt=86400.0
    )

    for key, val in result.items():
        print(f"  {key}: {val:.4f}")

    print("\n✅ Oxygen module loaded successfully!")
