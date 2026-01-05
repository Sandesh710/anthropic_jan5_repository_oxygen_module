#!/usr/bin/env python3
"""
Run FLake simulation with DO module using actual South Center Lake data.
This script extracts code from the notebook and runs it directly.
"""

import sys
import json

print("=" * 70)
print("RUNNING FLAKE WITH DO MODULE - SOUTH CENTER LAKE")
print("=" * 70)

# Try importing required packages
print("\n1. Checking dependencies...")
missing = []

try:
    import numpy as np
    print("   ✓ numpy")
except ImportError:
    missing.append("numpy")
    print("   ✗ numpy - MISSING")

try:
    import pandas as pd
    print("   ✓ pandas")
except ImportError:
    missing.append("pandas")
    print("   ✗ pandas - MISSING")

try:
    import matplotlib.pyplot as plt
    print("   ✓ matplotlib")
except ImportError:
    missing.append("matplotlib")
    print("   ✗ matplotlib - MISSING")

try:
    import f90nml
    print("   ✓ f90nml")
except ImportError:
    missing.append("f90nml")
    print("   ✗ f90nml - MISSING")

if missing:
    print(f"\n❌ ERROR: Missing required packages: {', '.join(missing)}")
    print("\nPlease install with:")
    print(f"  pip install {' '.join(missing)}")
    print("\nOR using apt (on Ubuntu/Debian):")
    for pkg in missing:
        if pkg == "f90nml":
            print(f"  pip install f90nml")
        else:
            print(f"  sudo apt-get install python3-{pkg}")
    sys.exit(1)

print("\n✅ All dependencies available!")

# Import oxygen module
print("\n2. Importing oxygen module...")
try:
    import oxygen_module as ox
    print("   ✓ oxygen_module.py")
except ImportError as e:
    print(f"   ✗ ERROR: Could not import oxygen_module: {e}")
    sys.exit(1)

# Load and execute notebook cells
print("\n3. Loading notebook...")
with open('FLAKE_SOUTHCENTERLAKE (2).ipynb', 'r') as f:
    notebook = json.load(f)

print(f"   Found {len(notebook['cells'])} cells")

# Execute cells 0-26 (up to and including main simulation)
print("\n4. Executing FLake + DO simulation...")
print("   This may take 5-30 seconds depending on your system...")

# Create a namespace for execution
exec_globals = {}

# Execute cells in order
for i in range(27):  # Cells 0-26
    cell = notebook['cells'][i]
    if cell['cell_type'] == 'code':
        source_code = ''.join(cell['source'])
        if source_code.strip():  # Skip empty cells
            try:
                exec(source_code, exec_globals)
            except Exception as e:
                print(f"\n❌ Error in cell {i}:")
                print(f"   {type(e).__name__}: {e}")
                # Continue anyway for some errors
                if i > 23:  # Critical cells
                    raise

print("\n✅ Simulation complete!")

# Extract results from namespace
test_file_df = exec_globals.get('test_file_df')
output_filename = exec_globals.get('output_filename', 'output.xlsx')

if test_file_df is None:
    print("\n❌ ERROR: Could not find output DataFrame")
    sys.exit(1)

print(f"\n5. Results summary:")
print(f"   Timesteps: {len(test_file_df)}")
print(f"   Columns: {len(test_file_df.columns)}")
print(f"   Output file: {output_filename}")

# Check for DO columns
do_columns = ['Cs', 'Cb', 'DO_sat', 'DO_min', 'F_atm', 'F_ex', 'SOD_rate', 'R_s', 'R_d']
has_do = all(col in test_file_df.columns for col in do_columns)

if has_do:
    print("\n   ✅ DO columns found in output!")
    print("\n   DO Statistics:")
    print(f"      Cs (surface):  {test_file_df['Cs'].min():.2f} - {test_file_df['Cs'].max():.2f} mg/L")
    print(f"      Cb (bottom):   {test_file_df['Cb'].min():.2f} - {test_file_df['Cb'].max():.2f} mg/L")
    print(f"      DO_min:        {test_file_df['DO_min'].min():.2f} - {test_file_df['DO_min'].max():.2f} mg/L")

    hypoxic_days = (test_file_df['DO_min'] < 2.0).sum()
    print(f"      Hypoxic days (DO<2): {hypoxic_days} ({100*hypoxic_days/len(test_file_df):.1f}%)")
else:
    print("\n   ⚠️  Warning: DO columns not found in output")

# Save to pickle for plotting script
print("\n6. Saving results for plotting...")
test_file_df.to_pickle('simulation_results.pkl')
print("   ✓ Saved to simulation_results.pkl")

print("\n" + "=" * 70)
print("SUCCESS! Simulation complete.")
print("=" * 70)
print(f"\nOutput saved to: {output_filename}")
print("Next: Run plotting script to generate figures")
print("  python3 create_plots_from_data.py")
print("=" * 70)
