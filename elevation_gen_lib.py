import numpy as np
import rasterio
import requests
import tempfile
from shapely import wkt
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import os

# API Key for OpenTopography
API_KEY = "b89e173b75937fd863fb55618dc05230"
API_URL = "https://portal.opentopography.org/API/globaldem"

def elevation_to_color(elevation, min_elev, max_elev, format='matplotlib'):
    """Map elevation to color: dark blue (low) -> light blue -> cyan -> green -> yellow -> red (high)"""
    # Clamp elevation to valid range
    elevation = np.clip(elevation, min_elev, max_elev)
    norm = (elevation - min_elev) / (max_elev - min_elev + 1e-10)
    # Clamp normalized value to [0, 1]
    norm = np.clip(norm, 0.0, 1.0)
    
    # Color stops: 0-0.01=dark blue, 0.01-0.1=light blue, 0.1-0.3=cyan, 0.3-0.5=green, 0.5-0.75=yellow, 0.75-1=red
    if norm < 0.01:
        r, g, b = 0, 0, 139
    elif norm < 0.1:
        t = (norm - 0.01) / 0.09
        r, g, b = int(0 + 135 * t), int(0 + 206 * t), int(139 + 111 * t)
    elif norm < 0.3:
        t = (norm - 0.1) / 0.2
        r, g, b = int(135 * (1-t) + 0 * t), int(206 + 49 * t), int(250 + 5 * t)
    elif norm < 0.5:
        t = (norm - 0.3) / 0.2
        r, g, b = int(0), int(255), int(255 * (1-t))
    elif norm < 0.75:
        t = (norm - 0.5) / 0.25
        r, g, b = int(255 * t), int(255), int(0)
    else:
        t = (norm - 0.75) / 0.25
        r, g, b = int(255), int(255 * (1-t)), int(0)
    
    # Clamp RGB values to valid range [0, 255]
    r, g, b = np.clip(r, 0, 255), np.clip(g, 0, 255), np.clip(b, 0, 255)
    
    if format == 'matplotlib':
        return (r/255.0, g/255.0, b/255.0)
    else:
        return f'rgb({r},{g},{b})'

def generate_elevation_map(wkt_polygon, vertical_exaggeration=10.0, use_color_gradient=True, 
                          num_profiles=100, num_points_per_profile=200, output_path='webapp/elevation_output.png'):
    """
    Generate elevation map from WKT polygon
    
    Args:
        wkt_polygon: WKT string defining the area
        vertical_exaggeration: Multiplier for elevation changes
        use_color_gradient: Whether to use color gradient
        num_profiles: Number of horizontal profiles
        num_points_per_profile: Number of points per profile
        output_path: Path to save the PNG
    
    Returns:
        Path to generated PNG file
    """
    
    # Parse WKT and extract bounding box
    polygon = wkt.loads(wkt_polygon)
    bounds = polygon.bounds  # (minx, miny, maxx, maxy)
    lon_min, lat_min, lon_max, lat_max = bounds
    
    # Calculate aspect ratio for image dimensions
    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min
    
    # Adjust for latitude distortion (approximate correction)
    lat_center = (lat_min + lat_max) / 2
    lon_range_corrected = lon_range * np.cos(np.radians(lat_center))
    aspect_ratio = lon_range_corrected / lat_range
    
    # Download DEM from OpenTopography
    params = {
        'demtype': 'SRTMGL1',
        'south': lat_min,
        'north': lat_max,
        'west': lon_min,
        'east': lon_max,
        'outputFormat': 'GTiff',
        'API_Key': API_KEY
    }
    
    print(f"Downloading DEM for area: {lat_min},{lon_min} to {lat_max},{lon_max}")
    response = requests.get(API_URL, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Error downloading DEM: {response.status_code}\nResponse: {response.text}")
    
    temp_dem = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    temp_dem.write(response.content)
    temp_dem.close()
    print(f"DEM downloaded successfully")
    
    # Read DEM and sample profiles
    with rasterio.open(temp_dem.name) as src:
        rows = np.linspace(src.height - 1, 0, num_profiles).astype(int)
        cols = np.linspace(0, src.width - 1, num_points_per_profile).astype(int)
        
        elevation_profiles = []
        for r in rows:
            profile = src.read(1)[r, cols]
            elevation_profiles.append(profile)
    
    # Calculate global elevation range
    all_elevations = np.concatenate(elevation_profiles)
    # Clamp negative elevations to 0 for the min/max calculation
    all_elevations_clamped = np.maximum(all_elevations, 0)
    global_min = np.min(all_elevations_clamped)
    global_max = np.max(all_elevations_clamped)
    elevation_range = global_max - global_min
    
    print(f"Elevation range: {elevation_range:.1f}m (min: {global_min:.1f}m, max: {global_max:.1f}m)")
    
    # Calculate exaggerated range
    exaggerated_min = global_min
    exaggerated_max = global_min + (elevation_range * vertical_exaggeration)
    
    # Visualization parameters
    vertical_offset = 3
    amplitude_scale = 0.5
    
    # Calculate figure dimensions to match geographic aspect ratio
    fig_width = 16  # base width in inches
    fig_height = fig_width / aspect_ratio
    
    # Generate PNG using matplotlib
    print("Generating PNG...")
    fig_mpl, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=200)
    ax.set_xlim(0, num_points_per_profile)
    ax.set_ylim(0, len(elevation_profiles) * vertical_offset)
    ax.set_facecolor('black')
    fig_mpl.patch.set_facecolor('black')
    ax.axis('off')
    ax.set_aspect('auto')  # Allow aspect to match figure shape
    
    # Plot profiles in reverse order
    for i in reversed(range(len(elevation_profiles))):
        profile = elevation_profiles[i]
        
        # Clamp negative elevations to 0 before processing
        profile = np.maximum(profile, 0)
        
        # Apply vertical exaggeration
        exaggerated_profile = global_min + ((profile - global_min) * vertical_exaggeration)
        normalized = (exaggerated_profile - exaggerated_min) / (exaggerated_max - exaggerated_min + 1e-10)
        scaled = normalized * amplitude_scale * vertical_offset * 10
        
        y_offset = i * vertical_offset
        x_vals = np.arange(num_points_per_profile)
        y_vals = scaled + y_offset
        
        # Fill to zero with black
        ax.fill_between(x_vals, y_vals, 0, color='black', zorder=len(elevation_profiles)-i)
        
        if use_color_gradient:
            for j in range(len(profile) - 1):
                color = elevation_to_color(profile[j], global_min, global_max, format='matplotlib')
                ax.plot([j, j+1], [y_vals[j], y_vals[j+1]], 
                       color=color, linewidth=2, zorder=len(elevation_profiles)-i+0.1)
        else:
            ax.plot(x_vals, y_vals, color='white', linewidth=2, zorder=len(elevation_profiles)-i+0.1)
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    
    plt.tight_layout(pad=0)
    plt.savefig(output_path, dpi=200, bbox_inches='tight', pad_inches=0, 
                facecolor='black', edgecolor='none')
    plt.close()
    
    print(f"PNG file generated: {output_path}")
    
    # Cleanup
    os.unlink(temp_dem.name)
    
    return output_path
