import streamlit as st
from streamlit_folium import st_folium
import folium
from folium.plugins import Draw
import sys
import os

# Add parent directory to path to import elevation_gen_lib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import from the same directory (since we'll copy elevation_gen_lib.py into webapp folder)
import elevation_gen_lib

st.set_page_config(page_title="Elevation Map Generator", layout="wide", page_icon="🏔️")

st.title("🏔️ Elevation Map Generator")
st.markdown("Draw a polygon on the map to generate a Joy Division-style elevation visualization")

# Sidebar controls
with st.sidebar:
    st.header("Settings")
    vert_exag = st.slider("Vertical Exaggeration", min_value=1.0, max_value=50.0, value=10.0, step=0.5)
    num_profiles = st.slider("Number of Profiles", min_value=50, max_value=200, value=100, step=10)
    use_color = st.checkbox("Use Color Gradient", value=True)
    
    st.markdown("---")
    st.markdown("### Instructions")
    st.markdown("""
    1. Click the polygon tool (⬟) on the map
    2. Draw a polygon by clicking points
    3. Double-click to complete
    4. Click 'Generate Map' below
    """)

# Create map with drawing tools
m = folium.Map(location=[51.5, -0.1], zoom_start=6, tiles='OpenStreetMap')

# Add draw control
draw = Draw(
    export=True,
    draw_options={
        'polyline': False,
        'polygon': True,
        'circle': False,
        'rectangle': True,
        'marker': False,
        'circlemarker': False
    },
    edit_options={'edit': True}
)
draw.add_to(m)

# Display map
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Draw Your Area")
    map_data = st_folium(m, width=700, height=500, key="map")

with col2:
    st.subheader("Generated Map")
    output_placeholder = st.empty()

# Generate button
if st.button("🎨 Generate Elevation Map", type="primary", use_container_width=True):
    if map_data and map_data.get('last_active_drawing'):
        drawing = map_data['last_active_drawing']
        
        if drawing and 'geometry' in drawing:
            try:
                # Extract coordinates from GeoJSON
                coords = drawing['geometry']['coordinates'][0]
                
                # Convert to WKT format (lon lat)
                wkt_coords = ','.join([f"{lon} {lat}" for lon, lat in coords])
                wkt = f"POLYGON(({wkt_coords}))"
                
                with st.spinner("🏔️ Downloading DEM data and generating visualization..."):
                    # Generate the map
                    png_path = generate_elevation_map(
                        wkt_polygon=wkt,
                        vertical_exaggeration=vert_exag,
                        use_color_gradient=use_color,
                        num_profiles=num_profiles
                    )
                    
                    # Display the result
                    with col2:
                        output_placeholder.image(png_path, caption="Generated Elevation Map", use_container_width=True)
                        
                        # Download button
                        with open(png_path, 'rb') as f:
                            st.download_button(
                                label="⬇️ Download PNG",
                                data=f,
                                file_name="elevation_map.png",
                                mime="image/png",
                                use_container_width=True
                            )
                    
                    st.success("✅ Map generated successfully!")
                    
            except Exception as e:
                st.error(f"❌ Error generating map: {str(e)}")
                st.exception(e)
    else:
        st.warning("⚠️ Please draw a polygon on the map first!")

# Footer
st.markdown("---")
st.markdown("Built with Streamlit • Elevation data from OpenTopography SRTM GL1")
