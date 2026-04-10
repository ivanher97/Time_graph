import json
import os
import io
import csv
import math
import numpy as np
import streamlit as st
import plotly.graph_objects as go

# --- Page Configurations ---
st.set_page_config(
    page_title="MOTEC TELEMETRY",
    page_icon="logo.png",
    layout="wide",
)

# Miami 80s Theme Custom CSS
st.markdown("""
<style>
/* Base Dark Theme */
.stApp { background-color: #0b0710; color: #e0e0e0; }
/* Main Title Neon Pink & Cyan */
h1 { font-family: 'Courier New', Courier, monospace; color: #FF00FF !important; text-shadow: 0 0 10px #FF00FF, 0 0 20px #FF00FF !important; text-align: center; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 20px; }
/* Subheaders Cyan */
h2, h3 { color: #00FFFF !important; text-shadow: 0 0 5px #00FFFF !important; font-family: 'Courier New', Courier, monospace; }
/* File Uploader styling */
.stFileUploader label { color: #00FFFF !important; font-size: 1.2rem; text-shadow: 0 0 5px #00FFFF; }
/* Metrics */
[data-testid="stMetricValue"] { color: #FF00FF !important; text-shadow: 0 0 8px #FF00FF; font-family: 'Courier New', Courier, monospace; }
[data-testid="stMetricLabel"] { color: #00FFFF !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

col_logo1, col_logo2, col_logo3 = st.columns([2, 1, 2])
with col_logo2:
    st.image("logo.png", use_container_width=True)

st.title("MOTEC TELEMETRY")
st.markdown("<h3 style='text-align: center; color: #00FFFF;'>B Y &nbsp; H A M M E R M A N</h3>", unsafe_allow_html=True)
st.write("---")

def format_time(seconds):
    secs = float(seconds)
    m = int(secs // 60)
    s = int(secs % 60)
    ms = int(round((secs - int(secs)) * 1000))
    if ms >= 1000:
        s += 1
        ms = 0
    if s >= 60:
        m += 1
        s = 0
    return f"{m:02d}:{s:02d}.{ms:03d}"

# --- Helper Functions ---
@st.cache_data
def load_demo_data():
    filepath = os.path.join("data", "lap_times.json")
    if not os.path.exists(filepath):
        st.error(f"Demo data file not found: {filepath}")
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

@st.cache_data(show_spinner="Extracting Laps from your MoTeC File... (This may take a moment)")
def parse_motec_csv(file_bytes):
    laps = {}
    
    # We use io.TextIOWrapper to read the uploaded byte stream as text line by line
    text_stream = io.TextIOWrapper(file_bytes, encoding='utf-8')
    
    # Skip the first 14 lines (Motec header info)
    for _ in range(14):
        try:
            next(text_stream)
        except StopIteration:
            st.error("The file does not seem to have the correct MoTeC format (too few lines).")
            return []
    
    # Read the 15th line which contains column names
    header_line = next(text_stream).strip()
    reader = csv.reader([header_line])
    headers = next(reader)
    
    try:
        time_idx = headers.index('Time')
        lap_idx = headers.index('Lap Number')
        in_pits_idx = headers.index('In Pits')
    except ValueError as e:
        st.error(f"Could not find necessary columns in headers: {e}")
        return []

    # Next line is units ('s', 'km/h', etc), Next line is empty
    next(text_stream) # units
    next(text_stream) # empty
    next(text_stream) # empty

    reader = csv.reader(text_stream)
    for row in reader:
        if not row or len(row) <= lap_idx:
            continue
        
        try:
            time_val = float(row[time_idx])
            lap = int(row[lap_idx])
            in_pits_val = row[in_pits_idx]
            is_in_pits = in_pits_val == '1' or in_pits_val.lower() == 'true'
        except ValueError:
            continue
        
        if lap not in laps:
            laps[lap] = {
                'lap': lap,
                'start_time': time_val,
                'end_time': time_val,
                'in_pits': is_in_pits
            }
        else:
            if time_val > laps[lap]['end_time']:
                laps[lap]['end_time'] = time_val
            
            if is_in_pits:
                laps[lap]['in_pits'] = True

    lap_summaries = []
    for lap_num, data in sorted(laps.items()):
        duration = data['end_time'] - data['start_time']
        if lap_num == 0:
            continue
        lap_summaries.append({
            'lap': data['lap'],
            'time': round(duration, 4),
            'in_pits': data['in_pits']
        })
        
    return lap_summaries

# --- Upload Interface ---
st.sidebar.header("Data Source")
uploaded_file = st.sidebar.file_uploader("Upload your MoTeC CSV", type=['csv'])

use_demo = st.sidebar.checkbox("Use Demo Data", value=False)

if not uploaded_file and not use_demo:
    st.info("👈 Please upload a MoTeC `.csv` file from the sidebar, or select 'Use Demo Data' to see how the app works.")
    st.stop()

# --- Process Data ---
raw_laps = []
if use_demo:
    raw_laps = load_demo_data()
    st.success("Loaded Demo Data successfully!")
elif uploaded_file is not None:
    raw_laps = parse_motec_csv(uploaded_file)
    if raw_laps:
        st.success(f"Successfully processed {len(raw_laps)} laps from your file!")

if not raw_laps:
    st.stop()

# Mark laps as invalid if they are anomalies (like < 20s session ending glitches). Lap 0 is entirely dropped upstream.
display_laps = []
for lap in raw_laps:
    # Custom validity rule: extremely short bursts are mathematically invalid for the track
    lap['is_invalid'] = lap['time'] < 20 
    display_laps.append(lap)

# Valid laps for stats: Exclude 'In Pits' and 'Invalid' laps completely from stat calculation
valid_laps = [lap for lap in display_laps if not lap['in_pits'] and not lap['is_invalid']]

if valid_laps:
    times = [l['time'] for l in valid_laps]
    avg_time = np.mean(times)
    variance = np.var(times)
    valid_count = len(valid_laps)
    
    # Calculate Consistency
    if valid_count > 1:
        std_dev = float(np.std(times))
        # Penalty formula: every 1s of std dev removes 10 points. 
        # Capped between 0 and 100%. E.g. std_dev = 1.0s -> 90%
        consistency_score = max(0.0, min(100.0, 100.0 - (std_dev * 10.0)))
    elif valid_count == 1:
        consistency_score = 100.0
    else:
        consistency_score = 0.0
    
    # Identify fastest lap
    fastest_lap = min(valid_laps, key=lambda x: x['time'])
    fastest_lap_num = fastest_lap['lap']
    
    # Y-axis scaling for valid laps (tighter zoom)
    min_valid = fastest_lap['time']
    max_valid = max(times)
    y_padding = (max_valid - min_valid) * 0.1
    if y_padding < 0.2:
        y_padding = 0.5
        
    y_min = min_valid - y_padding
    y_max = max_valid + y_padding
    
    # Tick generation (every 2 tenths)
    step = 0.2
    # Ensure ticks align with exact tenths mathematically
    tick_min = math.floor(y_min * 5) / 5.0
    tick_max = math.ceil(y_max * 5) / 5.0
    tick_vals = np.arange(tick_min, tick_max + (step/10), step)
    tick_text = [format_time(t) for t in tick_vals]
else:
    avg_time = 0
    variance = 0
    valid_count = 0
    consistency_score = 0.0
    fastest_lap_num = None
    y_min, y_max = 0, 10
    tick_vals, tick_text = [], []

# --- Metrics Dashboard ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Average Lap time",
        value=f"{format_time(avg_time)}" if valid_count > 0 else "N/A"
    )

with col2:
    st.metric(
        label="Variance (s²)",
        value=f"{variance:.3f}" if valid_count > 0 else "N/A"
    )

with col3:
    st.metric(
        label="Consistency",
        value=f"{consistency_score:.1f}%" if valid_count > 0 else "N/A"
    )

with col4:
    st.metric(
        label="Valid Laps",
        value=valid_count
    )

with st.expander("ℹ️ ¿Qué significan y cómo se calculan la Varianza y la Consistencia?"):
    st.markdown("""
    **Varianza (s²)**: Mide qué tan dispersos están tus tiempos por vuelta respecto a tu *Media global*. Una varianza baja o cercana a 0 significa que todos tus tiempos han estado muy agrupados alrededor de la media, lo cual es indicativo de un ritmo muy constante. Matemáticamente es el promedio de las diferencias al cuadrado.
    
    **Consistencia (%)**: Un indicador propio (del 0% al 100%) que extrae la nota final de tu solidez general. Se basa en la *Desviación Típica*. Una puntuación del 100% refleja una precisión robótica (tiempos casi idénticos). Si tienes parones, pequeños accidentes, tráfico o ritmos muy irregulares, el porcentaje bajará penalizando la puntuación.
    """)

st.divider()

# --- Scatter Plot using Plotly ---
st.subheader("Lap Times Scatter Plot")

# Separate data structurally for charting
laps_list = []
times_list = []
colors_list = []
line_colors_list = []
line_widths_list = []
status_list = []
formatted_times = []

for lap in display_laps:
    laps_list.append(lap['lap'])
    times_list.append(lap['time'])
    formatted_times.append(format_time(lap['time']))
    
    if lap.get('is_invalid', False):
        colors_list.append('#000000')  # Black
        line_colors_list.append('#ffffff') # White Border
        line_widths_list.append(2)
        status_list.append('Invalid Lap')
    elif lap['in_pits']:
        colors_list.append('rgba(239, 68, 68, 0.4)')  # Opaque Red for Pits, less intrusive
        line_colors_list.append('rgba(255,255,255,0.2)')
        line_widths_list.append(1)
        status_list.append('In Pits')
    elif lap['lap'] == fastest_lap_num:
        colors_list.append('#a855f7')  # Purple
        line_colors_list.append('rgba(255,255,255,0.8)')
        line_widths_list.append(2)
        status_list.append('Fastest Lap')
    else:
        colors_list.append('#38bdf8')  # Blue
        line_colors_list.append('rgba(255,255,255,0.2)')
        line_widths_list.append(1)
        status_list.append('Valid')

fig = go.Figure()

# Function to get gradient color from Green (low diff) to Red (high diff)
def get_segment_color(delta):
    # Cap maximum expected diff to 3.0s for color peak
    normalized = min(3.0, float(delta)) / 3.0 
    # Green: 16, 185, 129
    # Red: 239, 68, 68
    r = int(16 + normalized * (239 - 16))
    g = int(185 + normalized * (68 - 185))
    b = int(129 + normalized * (68 - 129))
    return f'rgb({r},{g},{b})'

# Draw variation lines FIRST so they stay behind markers
for i in range(len(laps_list) - 1):
    lap_start, lap_end = laps_list[i], laps_list[i+1]
    time_start, time_end = times_list[i], times_list[i+1]
    
    # Calculate difference
    delta = abs(time_end - time_start)
    seg_color = get_segment_color(delta)
    
    fig.add_trace(go.Scatter(
        x=[lap_start, lap_end],
        y=[time_start, time_end],
        mode='lines',
        line=dict(color=seg_color, width=2.5),
        hoverinfo='skip',
        showlegend=False
    ))

# Add Scatter Points
fig.add_trace(go.Scatter(
    x=laps_list,
    y=times_list,
    mode='markers',
    marker=dict(
        size=14, # Increased point size
        color=colors_list,
        line=dict(width=line_widths_list, color=line_colors_list),
        opacity=1.0
    ),
    name="Lap Time",
    customdata=list(zip(status_list, formatted_times)),
    hovertemplate="<b>Lap %{x}</b><br>Time: %{customdata[1]}<br>Status: %{customdata[0]}<extra></extra>"
))

# Group Pit laps into Red Background blocks
for lap in display_laps:
    if lap['in_pits']:
        # This will merge consecutive pit zones because 0.5 padding connects adjacent integers 
        fig.add_vrect(
            x0=lap['lap'] - 0.5, x1=lap['lap'] + 0.5,
            fillcolor="rgba(239, 68, 68, 0.15)",  # Red background zone
            layer="below", line_width=0,
            annotation_text="PITS", annotation_position="bottom right",
            annotation_font_color="rgba(239, 68, 68, 0.8)", annotation_font_size=10
        )

# Identify blocks of "Perfect Consistency" 
# Rule: >= 4 consecutive laps, ALL laps < avg_time, Standard Dev <= 0.25s
temp_block = []
def check_and_add_block(block, fig):
    if len(block) >= 4:
        sub_times = [l['time'] for l in block]
        if np.std(sub_times) <= 0.25:
            # Draw golden bounding box
            start_lap, end_lap = block[0]['lap'], block[-1]['lap']
            fig.add_vrect(
                x0=start_lap - 0.5, x1=end_lap + 0.5,
                fillcolor="rgba(250, 204, 21, 0.12)",  # Golden highlight
                layer="below", line_width=1, line_color="#facc15",
                annotation_text="⭐ Perfect Consistency",
                annotation_position="top left",
                annotation_font_color="#facc15",
                annotation_font_size=12
            )

for lap in display_laps:
    if not lap['in_pits'] and lap['time'] < avg_time:
        if not temp_block or lap['lap'] == temp_block[-1]['lap'] + 1:
            temp_block.append(lap)
        else:
            check_and_add_block(temp_block, fig)
            temp_block = [lap]
    else:
        check_and_add_block(temp_block, fig)
        temp_block = []

check_and_add_block(temp_block, fig)

# Add horizontal yellow dashed line for Average Lap Time
if valid_count > 0:
    fig.add_hline(
        y=avg_time,
        line_dash="dash",
        line_color="#facc15",  # Yellow
        annotation_text="Avg Time",
        annotation_font_size=11,
        annotation_font_color="#facc15",
        annotation_position="top left"
    )

min_x = min(laps_list) if laps_list else 1
max_x = max(laps_list) if laps_list else 10
range_x = [max(1, min_x - 0.5), max_x + 0.5]

# Format the Layout overlay
fig.update_layout(
    height=800,  # Increased overall height
    xaxis_title="Lap Number",
    yaxis_title="Time",
    xaxis=dict(
        showgrid=True, 
        gridcolor='rgba(255,255,255,0.05)', 
        dtick=1,
        range=range_x,  # Default initial zoom bounds
        minallowed=0.5, # Strictly prevent viewport panning into negative leaps
        maxallowed=max_x + 0.5, # Stricly prevent viewport panning past recorded laps
        fixedrange=False,
        rangeslider=dict(
            visible=True,
            bgcolor="rgba(255,255,255,0.05)",
            thickness=0.05
        )
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor='rgba(255,255,255,0.05)',
        range=[y_min, y_max],
        tickmode='array',
        tickvals=tick_vals,
        ticktext=tick_text
    ),
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    hovermode='closest',
    margin=dict(l=20, r=20, t=20, b=20),
    showlegend=False,
    font=dict(family="Courier New, monospace", color="#00FFFF")
)

st.plotly_chart(fig, width='stretch')

st.caption("Data automatically excluded: Lap 0, In-Pit Laps, and severely short logic bursts (<20s).")

st.markdown("---")
st.markdown("""
<div style='text-align: center; margin-top: 30px; margin-bottom: 20px;'>
    <a href='https://www.youtube.com/@hammerman_97' target='_blank' style='color: #FF00FF; text-decoration: none; margin-right: 30px; font-size: 1.2rem; font-weight: bold; font-family: "Courier New", Courier, monospace;'>📺 YouTube</a>
    <a href='https://github.com/ivanher97' target='_blank' style='color: #00FFFF; text-decoration: none; font-size: 1.2rem; font-weight: bold; font-family: "Courier New", Courier, monospace;'>🐙 GitHub</a>
</div>
""", unsafe_allow_html=True)
