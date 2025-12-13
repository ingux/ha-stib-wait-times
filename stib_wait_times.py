"""
STIB/MIVB Wait Times PyScript for Home Assistant

This script retrieves real-time wait times for STIB/MIVB public transport stops in Brussels
using the OpenDataSoft API v2.1.

Installation:
1. Enable PyScript in Home Assistant
2. Place this file in /config/pyscript/stib_wait_times.py
3. Restart Home Assistant or reload PyScript

Usage:
The script will create sensors for each configured stop with attributes containing:
- Next 2 passing times
- Line numbers  
- Destinations
- Wait times in minutes
"""

import aiohttp
import json
from datetime import datetime, timedelta

# Test that the file is loading
log.info("=" * 50)
log.info("STIB Wait Times: Script file loaded successfully!")
log.info("=" * 50)

# ============= CONFIGURATION =============
# API Key - Get yours from https://stibmivb.opendatasoft.com/account/
API_KEY = "c841e3a9d63006ae4c4841d9e34ac9e62f6d99a68987a04cf2a1b323"

STOPS_CONFIG = [
    {
        "stop_id": "1983",
        "lines": [34, 38, 80, 95],
        "name": "IDALIE_CENTRE"
    },
    {
        "stop_id": "1706",
        "lines": [34, 38, 80, 95],
        "name": "IDALIE_WAVRE"
    },
    {
        "stop_id": "1906",
        "lines": [34, 38, 80, 95],
        "name": "IDALIE_COURONNE"
    },
    {
        "stop_id": "2963",
        "lines": [54, 71],
        "name": "FERNAND_COQ_CENTRE"
    },
    {
        "stop_id": "2928",
        "lines": [54, 71],
        "name": "FERNAND_COQ_FLAGEY"
    }
]

# Line type configuration
METRO_LINES = [1, 2, 5, 6]
TRAM_LINES = [3, 4, 7, 8, 9, 19, 25, 32, 39, 44, 51, 55, 62, 81, 82, 92, 93, 97]
BUS_LINES = [
    12, 13, 20, 21, 27, 28, 29, 33, 34, 36, 38, 41, 42, 43, 45, 46, 47, 48, 49,
    50, 52, 53, 54, 56, 57, 58, 59, 60, 61, 63, 64, 65, 66, 69, 70, 71, 72, 73,
    74, 75, 76, 77, 78, 79, 80, 83, 84, 85, 86, 87, 88, 89, 95, 96
]

# Time range configuration
PAUSE_START_TIME = "00:30"
PAUSE_END_TIME = "06:00"

# API Configuration
API_BASE_URL = "https://stibmivb.opendatasoft.com/api/explore/v2.1"
DATASET_ID = "waiting-time-rt-production"
UPDATE_INTERVAL = 60
LANGUAGE = "fr"
# ========================================


def get_line_type(line_number):
    """Determine the type of transport based on line number."""
    try:
        line_int = int(line_number)
    except (ValueError, TypeError):
        return "bus"
    
    if line_int in METRO_LINES:
        return "metro"
    elif line_int in TRAM_LINES:
        return "tram"
    elif line_int in BUS_LINES:
        return "bus"
    else:
        return "bus"


def get_icon(line_type):
    """Get the appropriate icon for the line type."""
    icons = {
        "metro": "mdi:subway",
        "tram": "mdi:tram",
        "bus": "mdi:bus"
    }
    return icons.get(line_type, "mdi:bus")


def parse_wait_time(arrival_time_str):
    """Parse the arrival time string and calculate minutes until arrival."""
    if not arrival_time_str:
        return None, None
    
    try:
        arrival_time = datetime.fromisoformat(arrival_time_str.replace("Z", "+00:00"))
        now = datetime.now(arrival_time.tzinfo)
        delta = arrival_time - now
        minutes = max(0, int(delta.total_seconds() / 60))
        return minutes, arrival_time.isoformat()
    except Exception as e:
        log.warning(f"Error parsing time {arrival_time_str}: {e}")
        return None, None


def is_within_pause_time():
    """Check if current time is within the pause period."""
    if not PAUSE_START_TIME or not PAUSE_END_TIME:
        return False
    
    try:
        now = datetime.now().time()
        pause_start = datetime.strptime(PAUSE_START_TIME, "%H:%M").time()
        pause_end = datetime.strptime(PAUSE_END_TIME, "%H:%M").time()
        
        if pause_start > pause_end:
            return now >= pause_start or now < pause_end
        else:
            return pause_start <= now < pause_end
    except Exception as e:
        log.error(f"Error parsing pause times: {e}")
        return False


async def fetch_wait_times(stop_id):
    """Fetch waiting times for a specific stop from the STIB API."""
    url = f"{API_BASE_URL}/catalog/datasets/{DATASET_ID}/records"
    
    params = {
        "where": f"pointid={stop_id}",
        "limit": 100
    }
    
    headers = {}
    if API_KEY and API_KEY != "YOUR_API_KEY_HERE":
        headers["Authorization"] = f"Apikey {API_KEY}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    log.error(f"STIB API Error for stop {stop_id}: {response.status} - {error_text}")
                    return None
                
                data = await response.json()
                return data
    except Exception as e:
        log.error(f"Error fetching data for stop {stop_id}: {e}")
        return None


async def update_stop(stop_config):
    """Update wait times for a single stop."""
    stop_id = stop_config["stop_id"]
    stop_name = stop_config.get("name", stop_id)
    filter_lines = stop_config.get("lines", [])
    
    log.info(f"STIB: Fetching data for stop {stop_id} ({stop_name})")
    
    data = await fetch_wait_times(stop_id)
    
    if not data:
        log.error(f"STIB: Failed to fetch data for stop {stop_id}")
        return
    
    if "results" not in data:
        log.error(f"STIB: No 'results' in response for stop {stop_id}")
        return
    
    records = data.get("results", [])
    
    if len(records) == 0:
        log.warning(f"STIB: No records for stop {stop_id}")
        return
    
    log.info(f"STIB: Found {len(records)} records for stop {stop_id}")
    
    # Group records by line number
    lines_data = {}
    for record in records:
        fields = record.get("pointid") and record or record.get("record", {}).get("fields", {})
        
        line_id = fields.get("lineid")
        if not line_id:
            continue
        
        line_id_str = str(line_id)
        
        if filter_lines:
            try:
                if int(line_id) not in filter_lines:
                    continue
            except (ValueError, TypeError):
                continue
        
        if line_id_str not in lines_data:
            lines_data[line_id_str] = []
        
        lines_data[line_id_str].append(fields)
    
    log.info(f"STIB: Processing {len(lines_data)} lines for stop {stop_id}: {list(lines_data.keys())}")
    
    if not lines_data:
        log.warning(f"STIB: No matching lines for stop {stop_id}")
        return
    
    # Create sensors for each line
    for line_id, line_records in lines_data.items():
        try:
            await process_line(stop_id, stop_name, line_id, line_records)
        except Exception as e:
            log.error(f"STIB: Error processing line {line_id}: {e}")


async def process_line(stop_id, stop_name, line_id, line_records):
    """Process and create sensor for a line."""
    sensor_name = f"sensor.stib_{stop_id}_{line_id}"
    line_type = get_line_type(line_id)
    
    if not line_records:
        return
    
    record = line_records[0]
    passing_times_raw = record.get("passingtimes", "[]")
    
    # Parse JSON string
    try:
        if isinstance(passing_times_raw, str):
            passing_times_list = json.loads(passing_times_raw)
        else:
            passing_times_list = passing_times_raw
    except Exception as e:
        log.error(f"STIB: Error parsing JSON for {sensor_name}: {e}")
        passing_times_list = []
    
    # Extract passages
    next_passages = []
    for passage in passing_times_list[:2]:
        destination = passage.get("destination", {})
        expected_time = passage.get("expectedArrivalTime", "")
        message = passage.get("message", {})
        
        # Get destination text
        dest_text = "Unknown"
        if isinstance(destination, dict):
            dest_text = destination.get(LANGUAGE, destination.get("fr", destination.get("nl", "Unknown")))
        elif isinstance(destination, str):
            dest_text = destination
        
        # Get message text
        msg_text = ""
        if isinstance(message, dict):
            msg_text = message.get(LANGUAGE, message.get("fr", message.get("nl", "")))
        elif isinstance(message, str):
            msg_text = message
        
        # If destination is empty/unknown but we have a message, use the message as destination
        # This handles "End of service", "Last passage", etc.
        if (not dest_text or dest_text == "Unknown") and msg_text:
            dest_text = msg_text
            msg_text = ""  # Clear message since we're using it as destination
        
        # Calculate minutes
        minutes, arrival_iso = parse_wait_time(expected_time)
        
        next_passages.append({
            "minutes": minutes,
            "destination": dest_text,
            "message": msg_text,
            "arrival_time": arrival_iso or expected_time
        })
    
    # Determine state
    if next_passages and next_passages[0]["minutes"] is not None:
        state_value = next_passages[0]["minutes"]
    else:
        state_value = "unknown"
    
    # Build attributes
    attributes = {
        "friendly_name": f"STIB {stop_name} Line {line_id}",
        "stop_id": stop_id,
        "stop_name": stop_name,
        "line_number": line_id,
        "line_type": line_type,
        "icon": get_icon(line_type),
        "unit_of_measurement": "min",
        "attribution": "Data provided by STIB-MIVB OpenData",
        "device_class": "duration"
    }
    
    # Add passage data
    for i, passage in enumerate(next_passages, 1):
        if passage["minutes"] is not None:
            attributes[f"next_passing_{i}_minutes"] = passage["minutes"]
        if passage["destination"]:
            attributes[f"next_passing_{i}_destination"] = passage["destination"]
        if passage["message"]:
            attributes[f"next_passing_{i}_message"] = passage["message"]
        if passage["arrival_time"]:
            attributes[f"next_passing_{i}_time"] = passage["arrival_time"]
    
    # Set sensor
    state.set(sensor_name, value=state_value, new_attributes=attributes)
    
    log.info(f"STIB: Updated {sensor_name} = {state_value} min, dest: {next_passages[0]['destination'] if next_passages else 'N/A'}")


@time_trigger("startup")
@time_trigger(f"period(now, {UPDATE_INTERVAL}s)")
async def stib_update():
    """Update STIB wait times periodically."""
    if is_within_pause_time():
        log.info("STIB: Skipping update (pause period)")
        return
    
    log.info(f"STIB: Starting update for {len(STOPS_CONFIG)} stops")
    
    for stop_config in STOPS_CONFIG:
        try:
            await update_stop(stop_config)
        except Exception as e:
            log.error(f"STIB: Error updating stop {stop_config['stop_id']}: {e}")


@service
async def stib_update_wait_times():
    """Service to manually trigger an update."""
    log.info("STIB: Manual update triggered")
    
    for stop_config in STOPS_CONFIG:
        try:
            await update_stop(stop_config)
        except Exception as e:
            log.error(f"STIB: Error updating stop {stop_config['stop_id']}: {e}")


@service
async def stib_update_single_stop(stop_id=None):
    """Service to update a single stop by ID."""
    if not stop_id:
        log.error("STIB: stop_id parameter required")
        return
    
    log.info(f"STIB: Manual update for stop {stop_id}")
    
    stop_config = None
    for config in STOPS_CONFIG:
        if config["stop_id"] == str(stop_id):
            stop_config = config
            break
    
    if not stop_config:
        log.error(f"STIB: Stop {stop_id} not in config")
        return
    
    try:
        await update_stop(stop_config)
    except Exception as e:
        log.error(f"STIB: Error updating stop {stop_id}: {e}")


@service
async def stib_debug_info():
    """Service to test and show debug information."""
    log.error("STIB DEBUG: Running debug")
    log.error(f"STIB DEBUG: API Key configured: {API_KEY != 'YOUR_API_KEY_HERE'}")
    log.error(f"STIB DEBUG: Stops configured: {len(STOPS_CONFIG)}")
    log.error(f"STIB DEBUG: Pause active: {is_within_pause_time()}")
    log.error(f"STIB DEBUG: Current time: {datetime.now().strftime('%H:%M:%S')}")
    
    if STOPS_CONFIG:
        first_stop = STOPS_CONFIG[0]
        log.error(f"STIB DEBUG: Testing stop {first_stop['stop_id']}")
        
        data = await fetch_wait_times(first_stop['stop_id'])
        
        if data:
            log.error(f"STIB DEBUG: Got {len(data.get('results', []))} results")
        else:
            log.error("STIB DEBUG: No data returned")