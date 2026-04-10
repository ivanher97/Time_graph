import csv
import json
import os
import sys

def extract_laps(csv_path, json_path):
    print(f"Reading {csv_path}...")
    laps = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        # Skip the first 14 lines (Motec header info)
        for _ in range(14):
            next(f)
        
        # Read the 15th line which contains column names
        header_line = next(f).strip()
        reader = csv.reader([header_line])
        headers = next(reader)
        
        # Determine the target column indexes
        try:
            time_idx = headers.index('Time')
            lap_idx = headers.index('Lap Number')
            in_pits_idx = headers.index('In Pits')
        except ValueError as e:
            print("Could not find necessary columns in headers:", e)
            return

        # Next line is units ('s', 'km/h', etc), Next line is empty
        next(f) # units
        next(f) # empty
        next(f) # empty

        print("Starting data processing...")
        row_count = 0
        reader = csv.reader(f)
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
                # Update end time to max seen so far for this lap
                if time_val > laps[lap]['end_time']:
                    laps[lap]['end_time'] = time_val
                
                # If any row is in pits, the whole lap is flagged
                if is_in_pits:
                    laps[lap]['in_pits'] = True
            
            row_count += 1
            if row_count % 50000 == 0:
                print(f"Processed {row_count} rows...")

    lap_summaries = []
    # Convert and calculate lap time
    for lap_num, data in sorted(laps.items()):
        # Lap time is end_time - start_time
        # Note: sometimes lap times are provided directly in Motec as an accumulation or "Last Lap Time".
        # But end_time - start_time is valid for continuous telemetry within a lap.
        duration = data['end_time'] - data['start_time']
        
        # We also skip Lap 0 explicitly here or later. The user said don't show lap 0.
        if lap_num == 0:
            continue

        lap_summaries.append({
            'lap': data['lap'],
            'time': round(duration, 4),
            'in_pits': data['in_pits']
        })

    print(f"Extraction complete. Found {len(lap_summaries)} valid laps.")
    
    with open(json_path, 'w', encoding='utf-8') as jf:
        json.dump(lap_summaries, jf, indent=2)
    print(f"Saved to {json_path}")

if __name__ == '__main__':
    csv_file = os.path.join('data', 'tiempos.csv')
    json_file = os.path.join('data', 'lap_times.json')
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found.")
        sys.exit(1)
    
    extract_laps(csv_file, json_file)
