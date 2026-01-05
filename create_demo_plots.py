#!/usr/bin/env python3
"""
Create demonstration plots using pure Python (no numpy/matplotlib needed for demo)
Generates SVG plots that can be viewed in any browser
"""

import math
import random

def generate_synthetic_data(n_days=365):
    """Generate synthetic seasonal data"""
    data = {
        'day': list(range(n_days)),
        'T_surface': [],
        'T_bottom': [],
        'h_ML': [],
        'ice': [],
        'Cs': [],
        'Cb': [],
        'DO_sat': [],
        'DO_min': [],
        'F_atm': [],
        'SOD': [],
    }

    # Simple saturation formula approximation
    def o2_sat_approx(T):
        return 14.6 - 0.18 * T

    for day in range(n_days):
        # Seasonal temperature (sine wave)
        T_surf = 15 + 10 * math.sin(2 * math.pi * (day - 80) / 365)
        T_bot = 10 + 5 * math.sin(2 * math.pi * (day - 120) / 365)

        # Mixed layer depth
        h_ml = 3 + 10 * abs(math.sin(2 * math.pi * (day - 80) / 365))

        # Ice when T_surf < 1
        ice = 0.3 if T_surf < 1 else 0.0

        # DO saturation
        sat = o2_sat_approx(T_surf)

        # Surface DO (tracks saturation with deficit)
        cs = sat - (2.0 if ice == 0 else 0.5) * math.sin(2 * math.pi * (day - 80) / 365)**2

        # Bottom DO (develops deficit in summer)
        deficit = 5.0 * max(0, math.sin(2 * math.pi * (day - 120) / 365))
        cb = cs - deficit if h_ml < 15 else cs  # stratified vs mixed

        # Profile min
        do_min = min(cs, cb)

        # Reaeration
        f_atm = 0.0 if ice > 0 else 0.2 * (sat - cs)

        # SOD
        sod = 0.02 * (1.08 ** (T_bot - 20))

        # Store
        data['T_surface'].append(T_surf)
        data['T_bottom'].append(T_bot)
        data['h_ML'].append(h_ml)
        data['ice'].append(ice)
        data['Cs'].append(max(0, cs))
        data['Cb'].append(max(0, cb))
        data['DO_sat'].append(sat)
        data['DO_min'].append(do_min)
        data['F_atm'].append(f_atm)
        data['SOD'].append(sod)

    return data

def create_svg_plot(data, filename='do_timeseries.svg'):
    """Create SVG plot of DO time series"""

    width = 1200
    height = 800
    margin = {'top': 40, 'right': 40, 'bottom': 60, 'left': 60}
    plot_width = width - margin['left'] - margin['right']
    plot_height = height - margin['top'] - margin['bottom']

    # Scale functions
    n_days = len(data['day'])
    x_scale = lambda day: margin['left'] + (day / n_days) * plot_width

    # Y scale for DO (0-15 mg/L)
    y_scale = lambda do: margin['top'] + plot_height - (do / 15.0) * plot_height

    # Start SVG
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <style>
            .axis {{ stroke: black; stroke-width: 2; }}
            .grid {{ stroke: lightgray; stroke-width: 0.5; stroke-dasharray: 2,2; }}
            .line-cs {{ stroke: blue; stroke-width: 2; fill: none; }}
            .line-cb {{ stroke: red; stroke-width: 2; fill: none; }}
            .line-sat {{ stroke: green; stroke-width: 1.5; fill: none; stroke-dasharray: 5,5; }}
            .line-min {{ stroke: black; stroke-width: 1; fill: none; stroke-dasharray: 3,3; }}
            .hypoxic {{ stroke: orange; stroke-width: 1.5; stroke-dasharray: 4,4; }}
            .label {{ font-family: Arial, sans-serif; font-size: 12px; }}
            .title {{ font-family: Arial, sans-serif; font-size: 18px; font-weight: bold; }}
            .legend {{ font-family: Arial, sans-serif; font-size: 11px; }}
        </style>
    </defs>

    <!-- Background -->
    <rect width="{width}" height="{height}" fill="white"/>

    <!-- Title -->
    <text x="{width/2}" y="25" text-anchor="middle" class="title">
        Dissolved Oxygen Time Series - Synthetic 1-Year Simulation
    </text>

    <!-- Grid lines -->
'''

    # Horizontal grid lines (DO concentrations)
    for do_val in range(0, 16, 2):
        y = y_scale(do_val)
        svg += f'    <line x1="{margin["left"]}" y1="{y}" x2="{width - margin["right"]}" y2="{y}" class="grid"/>\n'
        svg += f'    <text x="{margin["left"] - 10}" y="{y + 4}" text-anchor="end" class="label">{do_val}</text>\n'

    # Vertical grid lines (months)
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for i, month in enumerate(months):
        day = int(i * n_days / 12)
        x = x_scale(day)
        svg += f'    <line x1="{x}" y1="{margin["top"]}" x2="{x}" y2="{height - margin["bottom"]}" class="grid"/>\n'
        svg += f'    <text x="{x}" y="{height - margin["bottom"] + 20}" text-anchor="middle" class="label">{month}</text>\n'

    # Axes
    svg += f'''
    <!-- X axis -->
    <line x1="{margin['left']}" y1="{height - margin['bottom']}"
          x2="{width - margin['right']}" y2="{height - margin['bottom']}" class="axis"/>
    <text x="{width/2}" y="{height - 10}" text-anchor="middle" class="label">Month</text>

    <!-- Y axis -->
    <line x1="{margin['left']}" y1="{margin['top']}"
          x2="{margin['left']}" y2="{height - margin['bottom']}" class="axis"/>
    <text x="20" y="{height/2}" text-anchor="middle" class="label" transform="rotate(-90, 20, {height/2})">
        DO Concentration (mg/L)
    </text>

    <!-- Hypoxic threshold -->
    <line x1="{margin['left']}" y1="{y_scale(2.0)}"
          x2="{width - margin['right']}" y2="{y_scale(2.0)}" class="hypoxic"/>

'''

    # Plot lines
    def create_path(y_data, x_data=None):
        if x_data is None:
            x_data = data['day']
        points = [f"{x_scale(x)},{y_scale(y)}" for x, y in zip(x_data, y_data)]
        return "M " + " L ".join(points)

    # DO Saturation
    svg += f'    <path d="{create_path(data["DO_sat"])}" class="line-sat"/>\n'

    # Surface DO
    svg += f'    <path d="{create_path(data["Cs"])}" class="line-cs"/>\n'

    # Bottom DO
    svg += f'    <path d="{create_path(data["Cb"])}" class="line-cb"/>\n'

    # Minimum DO
    svg += f'    <path d="{create_path(data["DO_min"])}" class="line-min"/>\n'

    # Legend
    legend_x = width - 200
    legend_y = 60
    svg += f'''
    <!-- Legend -->
    <rect x="{legend_x - 10}" y="{legend_y - 15}" width="190" height="110"
          fill="white" stroke="black" stroke-width="1"/>
    <line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 30}" y2="{legend_y}" class="line-cs"/>
    <text x="{legend_x + 40}" y="{legend_y + 4}" class="legend">Surface (Cs)</text>

    <line x1="{legend_x}" y1="{legend_y + 20}" x2="{legend_x + 30}" y2="{legend_y + 20}" class="line-cb"/>
    <text x="{legend_x + 40}" y="{legend_y + 24}" class="legend">Bottom (Cb)</text>

    <line x1="{legend_x}" y1="{legend_y + 40}" x2="{legend_x + 30}" y2="{legend_y + 40}" class="line-sat"/>
    <text x="{legend_x + 40}" y="{legend_y + 44}" class="legend">Saturation</text>

    <line x1="{legend_x}" y1="{legend_y + 60}" x2="{legend_x + 30}" y2="{legend_y + 60}" class="line-min"/>
    <text x="{legend_x + 40}" y="{legend_y + 64}" class="legend">Profile Min</text>

    <line x1="{legend_x}" y1="{legend_y + 80}" x2="{legend_x + 30}" y2="{legend_y + 80}" class="hypoxic"/>
    <text x="{legend_x + 40}" y="{legend_y + 84}" class="legend">Hypoxic (2 mg/L)</text>
'''

    svg += '</svg>'

    # Write to file
    with open(filename, 'w') as f:
        f.write(svg)

    print(f"✅ Created {filename}")

def create_profile_svg(data, filename='do_profiles.svg'):
    """Create SVG plot of seasonal DO profiles"""

    width = 1400
    height = 600
    n_profiles = 4
    profile_width = 300
    spacing = 50

    # Select days for each season
    seasons = [
        (50, 'Winter (Day 50)', 'ice'),
        (140, 'Spring (Day 140)', 'mixing'),
        (230, 'Summer (Day 230)', 'stratified'),
        (320, 'Fall (Day 320)', 'turnover')
    ]

    depth_w = 17.0  # meters

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <style>
            .profile {{ stroke: blue; stroke-width: 3; fill: none; }}
            .hml {{ stroke: green; stroke-width: 2; stroke-dasharray: 5,5; }}
            .hypoxic {{ stroke: red; stroke-width: 1.5; stroke-dasharray: 4,4; }}
            .axis {{ stroke: black; stroke-width: 1.5; }}
            .grid {{ stroke: lightgray; stroke-width: 0.5; }}
            .label {{ font-family: Arial, sans-serif; font-size: 11px; }}
            .title {{ font-family: Arial, sans-serif; font-size: 14px; font-weight: bold; }}
            .main-title {{ font-family: Arial, sans-serif; font-size: 18px; font-weight: bold; }}
        </style>
    </defs>

    <rect width="{width}" height="{height}" fill="white"/>

    <text x="{width/2}" y="30" text-anchor="middle" class="main-title">
        Seasonal Dissolved Oxygen Profiles
    </text>
'''

    for i, (day, title, condition) in enumerate(seasons):
        x_offset = 50 + i * (profile_width + spacing)
        y_offset = 80
        plot_height = 450
        plot_width = 250

        # Get data for this day
        Cs = data['Cs'][day]
        Cb = data['Cb'][day]
        h_ML = data['h_ML'][day]
        sat = data['DO_sat'][day]
        T_surf = data['T_surface'][day]
        ice = data['ice'][day]

        # Create profile points
        n_points = 50
        depths = [depth_w * i / (n_points - 1) for i in range(n_points)]

        # Simple profile reconstruction
        C_T = 0.7
        profile_DO = []
        for z in depths:
            if z <= h_ML:
                profile_DO.append(Cs)
            else:
                zeta = (z - h_ML) / (depth_w - h_ML)
                # Simple shape function
                Phi = zeta**2 * (1.5 - 0.5 * zeta) * (1.0 + C_T * (1.0 - zeta))
                C = Cs - (Cs - Cb) * Phi
                profile_DO.append(C)

        # Scales
        x_scale = lambda do: x_offset + (do / 15.0) * plot_width
        y_scale = lambda z: y_offset + (z / depth_w) * plot_height

        # Draw panel
        svg += f'''
    <!-- Panel {i+1}: {title} -->
    <rect x="{x_offset - 10}" y="{y_offset - 10}" width="{plot_width + 20}" height="{plot_height + 20}"
          fill="none" stroke="black" stroke-width="1"/>

    <text x="{x_offset + plot_width/2}" y="{y_offset - 20}" text-anchor="middle" class="title">{title}</text>
    <text x="{x_offset + plot_width/2}" y="{y_offset + plot_height + 30}" text-anchor="middle" class="label">
        T={T_surf:.1f}°C, Ice={ice:.1f}m
    </text>
'''

        # Grid
        for z in range(0, 18, 3):
            y = y_scale(z)
            svg += f'    <line x1="{x_offset}" y1="{y}" x2="{x_offset + plot_width}" y2="{y}" class="grid"/>\n'
            svg += f'    <text x="{x_offset - 5}" y="{y + 4}" text-anchor="end" class="label">{z}m</text>\n'

        # DO axis labels
        for do in range(0, 16, 5):
            x = x_scale(do)
            svg += f'    <text x="{x}" y="{y_offset - 15}" text-anchor="middle" class="label">{do}</text>\n'

        # Axes
        svg += f'''
    <line x1="{x_offset}" y1="{y_offset}" x2="{x_offset}" y2="{y_offset + plot_height}" class="axis"/>
    <line x1="{x_offset}" y1="{y_offset + plot_height}" x2="{x_offset + plot_width}" y2="{y_offset + plot_height}" class="axis"/>
    <text x="{x_offset + plot_width/2}" y="{y_offset + plot_height + 50}" text-anchor="middle" class="label">DO (mg/L)</text>
'''

        # Hypoxic line
        x_hypoxic = x_scale(2.0)
        svg += f'    <line x1="{x_hypoxic}" y1="{y_offset}" x2="{x_hypoxic}" y2="{y_offset + plot_height}" class="hypoxic"/>\n'

        # Mixed layer line
        y_hml = y_scale(h_ML)
        svg += f'    <line x1="{x_offset}" y1="{y_hml}" x2="{x_offset + plot_width}" y2="{y_hml}" class="hml"/>\n'

        # DO Profile
        points = [f"{x_scale(do)},{y_scale(z)}" for do, z in zip(profile_DO, depths)]
        svg += f'    <path d="M {" L ".join(points)}" class="profile"/>\n'

        # Legend for this panel
        leg_y = y_offset + 20
        svg += f'''
    <text x="{x_offset + 10}" y="{leg_y}" class="label">h_ML={h_ML:.1f}m</text>
    <text x="{x_offset + 10}" y="{leg_y + 15}" class="label">Cs={Cs:.1f} mg/L</text>
    <text x="{x_offset + 10}" y="{leg_y + 30}" class="label">Cb={Cb:.1f} mg/L</text>
'''

    svg += '</svg>'

    with open(filename, 'w') as f:
        f.write(svg)

    print(f"✅ Created {filename}")

def create_scatter_svg(data, filename='do_scatter.svg'):
    """Create scatter plot of DO vs Temperature"""

    width = 1000
    height = 800
    margin = {'top': 60, 'right': 40, 'bottom': 80, 'left': 80}
    plot_width = width - margin['left'] - margin['right']
    plot_height = height - margin['top'] - margin['bottom']

    # Scales
    T_min, T_max = 0, 30
    DO_min, DO_max = 0, 15

    x_scale = lambda T: margin['left'] + ((T - T_min) / (T_max - T_min)) * plot_width
    y_scale = lambda DO: margin['top'] + plot_height - ((DO - DO_min) / (DO_max - DO_min)) * plot_height

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <style>
            .axis {{ stroke: black; stroke-width: 2; }}
            .grid {{ stroke: lightgray; stroke-width: 0.5; }}
            .point-cs {{ fill: blue; opacity: 0.5; }}
            .point-cb {{ fill: red; opacity: 0.5; }}
            .sat-curve {{ stroke: black; stroke-width: 2; fill: none; }}
            .label {{ font-family: Arial, sans-serif; font-size: 12px; }}
            .title {{ font-family: Arial, sans-serif; font-size: 18px; font-weight: bold; }}
            .legend {{ font-family: Arial, sans-serif; font-size: 11px; }}
        </style>
    </defs>

    <rect width="{width}" height="{height}" fill="white"/>

    <text x="{width/2}" y="30" text-anchor="middle" class="title">
        DO vs Temperature (with Saturation Curve)
    </text>

    <!-- Grid -->
'''

    # Horizontal grid
    for DO_val in range(0, 16, 2):
        y = y_scale(DO_val)
        svg += f'    <line x1="{margin["left"]}" y1="{y}" x2="{width - margin["right"]}" y2="{y}" class="grid"/>\n'
        svg += f'    <text x="{margin["left"] - 10}" y="{y + 4}" text-anchor="end" class="label">{DO_val}</text>\n'

    # Vertical grid
    for T_val in range(0, 35, 5):
        x = x_scale(T_val)
        svg += f'    <line x1="{x}" y1="{margin["top"]}" x2="{x}" y2="{height - margin["bottom"]}" class="grid"/>\n'
        svg += f'    <text x="{x}" y="{height - margin["bottom"] + 20}" text-anchor="middle" class="label">{T_val}</text>\n'

    # Axes
    svg += f'''
    <line x1="{margin['left']}" y1="{height - margin['bottom']}"
          x2="{width - margin['right']}" y2="{height - margin['bottom']}" class="axis"/>
    <text x="{width/2}" y="{height - 20}" text-anchor="middle" class="label" style="font-size: 14px;">
        Temperature (°C)
    </text>

    <line x1="{margin['left']}" y1="{margin['top']}"
          x2="{margin['left']}" y2="{height - margin['bottom']}" class="axis"/>
    <text x="30" y="{height/2}" text-anchor="middle" class="label" style="font-size: 14px;"
          transform="rotate(-90, 30, {height/2})">
        DO (mg/L)
    </text>

    <!-- Saturation curve -->
'''

    # Draw saturation curve
    sat_points = []
    for T in range(0, 31):
        sat = 14.6 - 0.18 * T
        sat_points.append(f"{x_scale(T)},{y_scale(sat)}")
    svg += f'    <path d="M {" L ".join(sat_points)}" class="sat-curve"/>\n'

    # Plot points (sample every 5th point to reduce clutter)
    for i in range(0, len(data['day']), 5):
        T_s = data['T_surface'][i]
        T_b = data['T_bottom'][i]
        Cs = data['Cs'][i]
        Cb = data['Cb'][i]

        # Surface points
        svg += f'    <circle cx="{x_scale(T_s)}" cy="{y_scale(Cs)}" r="3" class="point-cs"/>\n'

        # Bottom points
        svg += f'    <circle cx="{x_scale(T_b)}" cy="{y_scale(Cb)}" r="3" class="point-cb"/>\n'

    # Legend
    legend_x = width - 220
    legend_y = 100
    svg += f'''
    <rect x="{legend_x - 10}" y="{legend_y - 15}" width="210" height="85"
          fill="white" stroke="black" stroke-width="1"/>

    <circle cx="{legend_x + 10}" cy="{legend_y}" r="4" class="point-cs"/>
    <text x="{legend_x + 25}" y="{legend_y + 4}" class="legend">Surface DO (Cs)</text>

    <circle cx="{legend_x + 10}" cy="{legend_y + 25}" r="4" class="point-cb"/>
    <text x="{legend_x + 25}" y="{legend_y + 29}" class="legend">Bottom DO (Cb)</text>

    <line x1="{legend_x}" y1="{legend_y + 50}" x2="{legend_x + 30}" y2="{legend_y + 50}" class="sat-curve"/>
    <text x="{legend_x + 40}" y="{legend_y + 54}" class="legend">Saturation Curve</text>
'''

    svg += '</svg>'

    with open(filename, 'w') as f:
        f.write(svg)

    print(f"✅ Created {filename}")

def main():
    print("=" * 70)
    print("GENERATING DISSOLVED OXYGEN DEMONSTRATION PLOTS")
    print("=" * 70)

    print("\n1. Generating synthetic data...")
    data = generate_synthetic_data(365)
    print(f"   ✅ Generated {len(data['day'])} days of data")

    # Statistics
    print("\n2. Data statistics:")
    print(f"   Temperature range: {min(data['T_surface']):.1f} - {max(data['T_surface']):.1f}°C")
    print(f"   Cs range: {min(data['Cs']):.2f} - {max(data['Cs']):.2f} mg/L")
    print(f"   Cb range: {min(data['Cb']):.2f} - {max(data['Cb']):.2f} mg/L")
    print(f"   Ice days: {sum(1 for ice in data['ice'] if ice > 0)}")
    print(f"   Hypoxic days (DO < 2): {sum(1 for do in data['DO_min'] if do < 2.0)}")

    print("\n3. Creating plots...")
    create_svg_plot(data, 'demo_do_timeseries.svg')
    create_profile_svg(data, 'demo_do_profiles.svg')
    create_scatter_svg(data, 'demo_do_scatter.svg')

    print("\n" + "=" * 70)
    print("✅ PLOTS CREATED SUCCESSFULLY!")
    print("=" * 70)
    print("\nGenerated files:")
    print("  1. demo_do_timeseries.svg - Annual DO time series")
    print("  2. demo_do_profiles.svg - Seasonal DO profiles")
    print("  3. demo_do_scatter.svg - DO vs Temperature scatter")
    print("\nThese are SVG files - open them in any web browser!")
    print("=" * 70)

if __name__ == '__main__':
    main()
