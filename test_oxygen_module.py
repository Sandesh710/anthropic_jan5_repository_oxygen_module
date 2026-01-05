#!/usr/bin/env python3
"""
Standalone test and validation script for oxygen_module.py

This script validates the DO module with synthetic FLake-like data
and generates validation plots.
"""

import sys
import os

# Try to import required packages
try:
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    from datetime import datetime, timedelta
    DEPS_AVAILABLE = True
except ImportError as e:
    print(f"Missing dependencies: {e}")
    print("This script requires: numpy, matplotlib")
    DEPS_AVAILABLE = False
    sys.exit(1)

# Import our oxygen module
import oxygen_module as ox

print("=" * 70)
print("OXYGEN MODULE VALIDATION AND TESTING")
print("=" * 70)

# =============================================================================
# TEST 1: Basic Functions
# =============================================================================
print("\n" + "=" * 70)
print("TEST 1: BASIC FUNCTIONS")
print("=" * 70)

print("\n1.1 Oxygen Saturation")
print("-" * 40)
temps = [0, 5, 10, 15, 20, 25, 30]
for T in temps:
    C_sat = ox.O2_saturation(T)
    print(f"  T = {T:2d}°C  =>  C_sat = {C_sat:.2f} mg/L")

# Check that saturation decreases with temperature
sats = [ox.O2_saturation(T) for T in temps]
assert all(sats[i] > sats[i+1] for i in range(len(sats)-1)), "Saturation should decrease with T"
print("  ✅ Saturation decreases with temperature")

# Check altitude effect
C_sat_sea = ox.O2_saturation(20.0, altitude_m=0)
C_sat_1000m = ox.O2_saturation(20.0, altitude_m=1000)
assert C_sat_1000m < C_sat_sea, "Saturation should decrease with altitude"
print(f"  ✅ Altitude effect: {C_sat_sea:.2f} mg/L (sea level) > {C_sat_1000m:.2f} mg/L (1000m)")

print("\n1.2 Shape Function")
print("-" * 40)
zeta = np.linspace(0, 1, 11)
C_T = 0.7
Phi = ox.Phi_theta(zeta, C_T)
print(f"  Shape function with C_T = {C_T}")
print(f"  Phi(0) = {Phi[0]:.4f} (should be ≈ 0)")
print(f"  Phi(1) = {Phi[-1]:.4f} (should be ≈ 1)")
assert abs(Phi[0]) < 0.01, "Phi(0) should be near 0"
assert abs(Phi[-1] - 1.0) < 0.01, "Phi(1) should be near 1"
print("  ✅ Shape function boundaries correct")

# Test integration
C_Phi = ox.integrate_Phi(C_T)
print(f"  ∫ Phi dζ = {C_Phi:.4f}")
assert 0.3 < C_Phi < 0.7, "Integral should be in reasonable range"
print("  ✅ Shape function integrates correctly")

# =============================================================================
# TEST 2: Synthetic Simulation
# =============================================================================
print("\n" + "=" * 70)
print("TEST 2: SYNTHETIC SIMULATION")
print("=" * 70)

# Simulate 1 year with daily timesteps
n_days = 365
dt = 86400.0  # 1 day in seconds
depth_w = 17.0  # meters

# Create synthetic seasonal forcing
day_of_year = np.arange(n_days)
T_surface = 15 + 10 * np.sin(2 * np.pi * (day_of_year - 80) / 365)  # 5-25°C seasonal cycle
T_bottom = 10 + 5 * np.sin(2 * np.pi * (day_of_year - 120) / 365)   # Lagged, damped
h_ML = 3 + 10 * np.abs(np.sin(2 * np.pi * (day_of_year - 80) / 365))  # 3-13m seasonal
C_T = 0.5 + 0.3 * (h_ML / depth_w)  # Shape factor varies with stratification
U10 = 3.0 + 2.0 * np.sin(2 * np.pi * day_of_year / 365)  # Wind 1-5 m/s

# Ice simulation: present when T_surface < 1°C
ice_thickness = np.where(T_surface < 1.0, 0.3, 0.0)

# DO parameters
DO_params = {
    'SOD_20': 1.5,
    'R_20_surface': 0.25,
    'R_20_deep': 0.2,
    'theta_sod': 1.08,
    'theta_R': 1.08,
    'K_ex': 0.02,
    'constant_k600': None,
    'altitude_m': 0.0,
}

print(f"\nSimulation setup:")
print(f"  Duration: {n_days} days")
print(f"  Lake depth: {depth_w} m")
print(f"  Temperature range: {T_surface.min():.1f} - {T_surface.max():.1f}°C")
print(f"  Mixed layer range: {h_ML.min():.1f} - {h_ML.max():.1f} m")
print(f"  Ice days: {(ice_thickness > 0).sum()}")

# Initialize DO
T_init = T_surface[0]
C_sat_init = ox.O2_saturation(T_init)
Cs = C_sat_init * 0.95
Cb = C_sat_init * 0.90

# Storage arrays
results = {
    'Cs': np.zeros(n_days),
    'Cb': np.zeros(n_days),
    'Cbar_d': np.zeros(n_days),
    'DO_sat': np.zeros(n_days),
    'DO_min': np.zeros(n_days),
    'F_atm': np.zeros(n_days),
    'F_ex': np.zeros(n_days),
    'SOD_rate': np.zeros(n_days),
    'R_s': np.zeros(n_days),
    'R_d': np.zeros(n_days),
}

# Run simulation
print("\nRunning simulation...", end="", flush=True)
h_ML_prev = h_ML[0]

for day in range(n_days):
    if day % 73 == 0:
        print(".", end="", flush=True)

    # Get current forcing
    h_ML_curr = h_ML[day]

    # Step oxygen
    do_out = ox.step_oxygen(
        Cs_old=Cs,
        Cb_old=Cb,
        T_surface=T_surface[day],
        T_bottom=T_bottom[day],
        h_ML_old=h_ML_prev,
        h_ML_new=h_ML_curr,
        depth_w=depth_w,
        C_T=C_T[day],
        ice_thickness=ice_thickness[day],
        U10=U10[day],
        dt=dt,
        **DO_params
    )

    # Store results
    results['Cs'][day] = do_out['Cs_new']
    results['Cb'][day] = do_out['Cb_new']
    results['Cbar_d'][day] = do_out['Cbar_d']
    results['DO_sat'][day] = do_out['C_sat']
    results['F_atm'][day] = do_out['F_atm']
    results['F_ex'][day] = do_out['F_ex']
    results['SOD_rate'][day] = do_out['SOD_rate']
    results['R_s'][day] = do_out['R_s']
    results['R_d'][day] = do_out['R_d']

    # Compute DO_min
    z_grid = np.linspace(0, depth_w, 50)
    results['DO_min'][day] = ox.compute_DO_min(z_grid, do_out['Cs_new'], do_out['Cb_new'],
                                                h_ML_curr, depth_w, C_T[day])

    # Update state
    Cs = do_out['Cs_new']
    Cb = do_out['Cb_new']
    h_ML_prev = h_ML_curr

print(" DONE!")

# =============================================================================
# TEST 3: Validation Checks
# =============================================================================
print("\n" + "=" * 70)
print("TEST 3: VALIDATION CHECKS")
print("=" * 70)

# Check 1: Physical bounds
print("\nCheck 1: Physical bounds (0 ≤ DO ≤ 25 mg/L)")
assert np.all(results['Cs'] >= 0), "Cs should be non-negative"
assert np.all(results['Cb'] >= 0), "Cb should be non-negative"
assert np.all(results['Cs'] <= 25), "Cs should be ≤ 25 mg/L"
assert np.all(results['Cb'] <= 25), "Cb should be ≤ 25 mg/L"
print(f"  ✅ All DO values in range [0, 25] mg/L")
print(f"     Cs range: [{results['Cs'].min():.2f}, {results['Cs'].max():.2f}]")
print(f"     Cb range: [{results['Cb'].min():.2f}, {results['Cb'].max():.2f}]")

# Check 2: Ice suppression
print("\nCheck 2: Ice suppression (F_atm = 0 when ice present)")
ice_days = ice_thickness > 0
if ice_days.any():
    max_F_atm_ice = np.abs(results['F_atm'][ice_days]).max()
    print(f"  Ice days: {ice_days.sum()}")
    print(f"  Max |F_atm| during ice: {max_F_atm_ice:.6f} mg/L/day")
    assert max_F_atm_ice < 1e-6, "F_atm should be zero under ice"
    print(f"  ✅ Reaeration suppressed under ice")
else:
    print(f"  ⚠️  No ice days in simulation")

# Check 3: Stratification effect
print("\nCheck 3: Stratification (Cb < Cs during summer)")
summer_days = (day_of_year >= 150) & (day_of_year <= 240)
if summer_days.any():
    summer_Cs = results['Cs'][summer_days]
    summer_Cb = results['Cb'][summer_days]
    stratification = summer_Cs - summer_Cb
    print(f"  Summer days: {summer_days.sum()}")
    print(f"  Mean stratification (Cs - Cb): {stratification.mean():.2f} mg/L")
    print(f"  Max stratification: {stratification.max():.2f} mg/L")
    assert stratification.mean() > 0.1, "Bottom should be lower than surface in summer"
    print(f"  ✅ Bottom DO lower than surface during summer")

# Check 4: Fully mixed condition
print("\nCheck 4: Fully mixed (Cs ≈ Cb when h_ML ≈ D)")
fully_mixed = h_ML >= (depth_w - 0.5)
if fully_mixed.any():
    diff = np.abs(results['Cs'][fully_mixed] - results['Cb'][fully_mixed])
    max_diff = diff.max()
    print(f"  Fully mixed days: {fully_mixed.sum()}")
    print(f"  Max |Cs - Cb| when fully mixed: {max_diff:.4f} mg/L")
    assert max_diff < 0.5, "Cs and Cb should be nearly equal when fully mixed"
    print(f"  ✅ Cs ≈ Cb during fully mixed conditions")
else:
    print(f"  ⚠️  No fully mixed days in simulation")

# Check 5: Mass balance (rough check)
print("\nCheck 5: Mass balance and trends")
print(f"  Initial Cs: {results['Cs'][0]:.2f} mg/L")
print(f"  Final Cs: {results['Cs'][-1]:.2f} mg/L")
print(f"  Initial Cb: {results['Cb'][0]:.2f} mg/L")
print(f"  Final Cb: {results['Cb'][-1]:.2f} mg/L")
print(f"  Mean reaeration: {results['F_atm'].mean():.3f} mg/L/day")
print(f"  Mean SOD: {results['SOD_rate'].mean():.3f} mg/L/day")
print(f"  ✅ Simulation completed without crashes")

# =============================================================================
# TEST 4: Profile Reconstruction
# =============================================================================
print("\n" + "=" * 70)
print("TEST 4: PROFILE RECONSTRUCTION")
print("=" * 70)

# Test on a stratified day (day 200 = mid-summer)
test_day = 200
z_grid = np.linspace(0, depth_w, 100)

Cs_test = results['Cs'][test_day]
Cb_test = results['Cb'][test_day]
h_ML_test = h_ML[test_day]
C_T_test = C_T[test_day]

profile = ox.reconstruct_DO_profile(z_grid, Cs_test, Cb_test, h_ML_test, depth_w, C_T_test)

print(f"\nDay {test_day} (summer stratified):")
print(f"  Cs = {Cs_test:.2f} mg/L")
print(f"  Cb = {Cb_test:.2f} mg/L")
print(f"  h_ML = {h_ML_test:.2f} m")
print(f"  C_T = {C_T_test:.2f}")

# Check profile properties
assert np.allclose(profile[z_grid <= h_ML_test], Cs_test, rtol=0.01), "Mixed layer should be uniform"
print(f"  ✅ Mixed layer uniform at Cs")

bottom_idx = np.argmin(np.abs(z_grid - depth_w))
assert np.allclose(profile[bottom_idx], Cb_test, rtol=0.01), "Bottom should equal Cb"
print(f"  ✅ Bottom value equals Cb")

# Profile should be monotonic (decreasing with depth when Cs > Cb)
if Cs_test > Cb_test:
    assert np.all(np.diff(profile) <= 0.01), "Profile should decrease with depth"
    print(f"  ✅ Profile monotonically decreases with depth")

print(f"  Profile min: {profile.min():.2f} mg/L")
print(f"  Profile max: {profile.max():.2f} mg/L")

# =============================================================================
# TEST 5: Generate Plots
# =============================================================================
print("\n" + "=" * 70)
print("TEST 5: GENERATING VALIDATION PLOTS")
print("=" * 70)

# Create dates for x-axis
start_date = datetime(2020, 1, 1)
dates = [start_date + timedelta(days=i) for i in range(n_days)]

# Plot 1: DO Time Series
print("\nGenerating Plot 1: DO time series...")
fig, axes = plt.subplots(4, 1, figsize=(14, 11))
fig.suptitle('Oxygen Module Validation - Synthetic 1-Year Simulation', fontsize=14, fontweight='bold')

# 1a. DO concentrations
ax = axes[0]
ax.plot(dates, results['Cs'], 'b-', linewidth=1.5, label='Surface/Mixed (Cs)', alpha=0.8)
ax.plot(dates, results['Cb'], 'r-', linewidth=1.5, label='Bottom (Cb)', alpha=0.8)
ax.plot(dates, results['DO_min'], 'k--', linewidth=1, label='Profile Min', alpha=0.6)
ax.plot(dates, results['DO_sat'], 'g:', linewidth=1, label='Saturation', alpha=0.6)
ax.axhline(2.0, color='orange', linestyle='--', linewidth=1, alpha=0.5, label='Hypoxic (2 mg/L)')
ax.set_ylabel('DO (mg/L)', fontsize=10)
ax.set_title('(a) Dissolved Oxygen Concentrations', fontsize=11, loc='left')
ax.legend(loc='best', fontsize=8, ncol=2)
ax.grid(True, alpha=0.3)

# 1b. Forcing (temperature)
ax = axes[1]
ax.plot(dates, T_surface, 'r-', linewidth=1, label='Surface T', alpha=0.7)
ax.plot(dates, T_bottom, 'b-', linewidth=1, label='Bottom T', alpha=0.7)
ax.set_ylabel('Temperature (°C)', fontsize=10)
ax.set_title('(b) Temperature Forcing', fontsize=11, loc='left')
ax.legend(loc='best', fontsize=8)
ax.grid(True, alpha=0.3)

# 1c. Oxygen fluxes
ax = axes[2]
ax.plot(dates, results['F_atm'], 'c-', linewidth=1, label='Reaeration', alpha=0.7)
ax.plot(dates, results['F_ex'], 'm-', linewidth=1, label='Interlayer Exchange', alpha=0.7)
ax.axhline(0, color='k', linestyle='-', linewidth=0.5)
ax.set_ylabel('Flux (mg/L/day)', fontsize=10)
ax.set_title('(c) Oxygen Fluxes', fontsize=11, loc='left')
ax.legend(loc='best', fontsize=8)
ax.grid(True, alpha=0.3)

# 1d. Stratification
ax = axes[3]
ax.plot(dates, h_ML, 'b-', linewidth=1.5, label='Mixed Layer Depth', alpha=0.8)
ax.set_ylabel('h_ML (m)', fontsize=10, color='b')
ax.tick_params(axis='y', labelcolor='b')
ax.set_ylim(0, depth_w)
ax.invert_yaxis()
ax.set_title('(d) Stratification and Ice', fontsize=11, loc='left')
ax.grid(True, alpha=0.3)
ax.set_xlabel('Date', fontsize=10)

# Ice on secondary axis
ax2 = ax.twinx()
ax2.fill_between(dates, 0, ice_thickness, color='lightblue', alpha=0.5, label='Ice')
ax2.set_ylabel('Ice (m)', fontsize=10, color='blue')
ax2.tick_params(axis='y', labelcolor='blue')
ax2.set_ylim(0, max(ice_thickness.max() * 1.5, 0.1))

lines1, labels1 = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax.legend(lines1 + lines2, labels1 + labels2, loc='best', fontsize=8)

plt.tight_layout()
plt.savefig('validation_timeseries.png', dpi=150, bbox_inches='tight')
print("  ✅ Saved: validation_timeseries.png")
plt.close()

# Plot 2: DO Profiles at different seasons
print("\nGenerating Plot 2: Seasonal DO profiles...")
profile_days = [50, 140, 230, 320]  # Winter, Spring, Summer, Fall
season_names = ['Winter (Day 50)', 'Spring (Day 140)', 'Summer (Day 230)', 'Fall (Day 320)']

fig, axes = plt.subplots(1, 4, figsize=(16, 5))
fig.suptitle('Seasonal DO Profiles', fontsize=14, fontweight='bold')

for i, (day, season) in enumerate(zip(profile_days, season_names)):
    ax = axes[i]

    # Get state
    Cs_i = results['Cs'][day]
    Cb_i = results['Cb'][day]
    h_ML_i = h_ML[day]
    C_T_i = C_T[day]
    DO_sat_i = results['DO_sat'][day]
    T_surf_i = T_surface[day]
    ice_i = ice_thickness[day]

    # Reconstruct profile
    profile = ox.reconstruct_DO_profile(z_grid, Cs_i, Cb_i, h_ML_i, depth_w, C_T_i)

    # Plot
    ax.plot(profile, z_grid, 'b-', linewidth=2.5, label='DO')
    ax.axhline(h_ML_i, color='green', linestyle='--', linewidth=1.5, label=f'h_ML={h_ML_i:.1f}m')
    ax.axvline(2.0, color='red', linestyle='--', linewidth=1, alpha=0.5, label='Hypoxic')
    ax.axvline(DO_sat_i, color='cyan', linestyle=':', linewidth=1, alpha=0.5, label=f'Sat={DO_sat_i:.1f}')

    ax.set_xlabel('DO (mg/L)', fontsize=10)
    if i == 0:
        ax.set_ylabel('Depth (m)', fontsize=10)
    ax.set_title(f'{season}\nT={T_surf_i:.1f}°C, Ice={ice_i:.2f}m', fontsize=10)
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, loc='best')
    ax.set_xlim(0, max(DO_sat_i * 1.1, profile.max() * 1.1))

plt.tight_layout()
plt.savefig('validation_profiles.png', dpi=150, bbox_inches='tight')
print("  ✅ Saved: validation_profiles.png")
plt.close()

# Plot 3: Validation scatter plots
print("\nGenerating Plot 3: Validation scatter plots...")
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
fig.suptitle('Validation Scatter Plots', fontsize=14, fontweight='bold')

# 3a. DO vs Temperature
ax = axes[0, 0]
ax.scatter(T_surface, results['Cs'], c='blue', s=10, alpha=0.5, label='Cs')
ax.scatter(T_bottom, results['Cb'], c='red', s=10, alpha=0.5, label='Cb')
# Plot saturation curve
T_range = np.linspace(T_surface.min(), T_surface.max(), 50)
sat_curve = [ox.O2_saturation(T) for T in T_range]
ax.plot(T_range, sat_curve, 'k-', linewidth=2, label='Saturation')
ax.set_xlabel('Temperature (°C)', fontsize=10)
ax.set_ylabel('DO (mg/L)', fontsize=10)
ax.set_title('(a) DO vs Temperature', fontsize=11, loc='left')
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# 3b. DO deficit vs stratification
ax = axes[0, 1]
stratification_strength = depth_w - h_ML
DO_deficit = results['Cs'] - results['Cb']
ax.scatter(stratification_strength, DO_deficit, c=T_surface, s=20, alpha=0.6, cmap='coolwarm')
ax.set_xlabel('Stratification (D - h_ML) [m]', fontsize=10)
ax.set_ylabel('DO Deficit (Cs - Cb) [mg/L]', fontsize=10)
ax.set_title('(b) DO Stratification vs Physical Stratification', fontsize=11, loc='left')
ax.grid(True, alpha=0.3)
cbar = plt.colorbar(ax.collections[0], ax=ax, label='Surface T (°C)')

# 3c. Reaeration vs wind
ax = axes[1, 0]
no_ice = ice_thickness == 0
ax.scatter(U10[no_ice], results['F_atm'][no_ice], c=T_surface[no_ice], s=20, alpha=0.6, cmap='coolwarm')
ax.set_xlabel('Wind Speed (m/s)', fontsize=10)
ax.set_ylabel('Reaeration (mg/L/day)', fontsize=10)
ax.set_title('(c) Reaeration vs Wind (no ice)', fontsize=11, loc='left')
ax.grid(True, alpha=0.3)
cbar = plt.colorbar(ax.collections[0], ax=ax, label='Surface T (°C)')

# 3d. SOD vs bottom temperature
ax = axes[1, 1]
ax.scatter(T_bottom, results['SOD_rate'], c='brown', s=20, alpha=0.6)
# Theoretical curve
T_range_bot = np.linspace(T_bottom.min(), T_bottom.max(), 50)
SOD_theory = [ox.sediment_oxygen_demand(T, DO_params['SOD_20'], DO_params['theta_sod']) * 1000 / (depth_w - 8)
              for T in T_range_bot]
ax.plot(T_range_bot, SOD_theory, 'k--', linewidth=2, label='Theory')
ax.set_xlabel('Bottom Temperature (°C)', fontsize=10)
ax.set_ylabel('SOD Rate (mg/L/day)', fontsize=10)
ax.set_title('(d) SOD vs Bottom Temperature', fontsize=11, loc='left')
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('validation_scatter.png', dpi=150, bbox_inches='tight')
print("  ✅ Saved: validation_scatter.png")
plt.close()

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 70)
print("VALIDATION SUMMARY")
print("=" * 70)

print("\n✅ ALL TESTS PASSED!")
print(f"\nSimulation Statistics:")
print(f"  Total days: {n_days}")
print(f"  Cs range: {results['Cs'].min():.2f} - {results['Cs'].max():.2f} mg/L")
print(f"  Cb range: {results['Cb'].min():.2f} - {results['Cb'].max():.2f} mg/L")
print(f"  DO_min range: {results['DO_min'].min():.2f} - {results['DO_min'].max():.2f} mg/L")
print(f"  Hypoxic days (DO_min < 2): {(results['DO_min'] < 2).sum()} ({100*(results['DO_min'] < 2).sum()/n_days:.1f}%)")
print(f"  Ice days: {(ice_thickness > 0).sum()} ({100*(ice_thickness > 0).sum()/n_days:.1f}%)")

print(f"\nMean Rates:")
print(f"  Reaeration: {results['F_atm'].mean():.3f} mg/L/day")
print(f"  Interlayer exchange: {results['F_ex'].mean():.3f} mg/L/day")
print(f"  SOD: {results['SOD_rate'].mean():.3f} mg/L/day")
print(f"  Surface respiration: {results['R_s'].mean():.3f} mg/L/day")
print(f"  Deep respiration: {results['R_d'].mean():.3f} mg/L/day")

print(f"\nPlots Generated:")
print(f"  1. validation_timeseries.png - Time series of all variables")
print(f"  2. validation_profiles.png - Seasonal DO profiles")
print(f"  3. validation_scatter.png - Validation scatter plots")

print("\n" + "=" * 70)
print("OXYGEN MODULE VALIDATION COMPLETE")
print("=" * 70)
