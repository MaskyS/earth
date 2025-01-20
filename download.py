from datetime import datetime, timezone, timedelta
from pathlib import Path
import re
import shutil
import pandas as pd
from herbie import FastHerbie
import subprocess

PRESSURE_LEVELS = ["1000", "850", "700", "500", "250", "70", "10"]

# Mapping levels to their corresponding surface values
LEVEL_SURFACE_VALUE_MAP = {
    "1000": 100000.0,
    "850": 85000.0,
    "700": 70000.0,
    "500": 50000.0,
    "250": 25000.0,
    "70": 7000.0,
    "10": 1000.0, 
    "surface": 10.0,
}

# Build single search pattern for all levels
SEARCH_PATTERN = (
    ":UGRD:(10 m above ground|"
    + "|".join(f"{level} mb" for level in PRESSURE_LEVELS)
    + ")|:VGRD:(10 m above ground|"
    + "|".join(f"{level} mb" for level in PRESSURE_LEVELS)
    + ")"
)

# Create date range for GFS runs (every 6 hours)
DATES = pd.date_range(
    start="2025-01-15 00:00",
    end="2025-01-15 18:00",  # Get all 4 GFS runs for the day
    freq="6H",
)



# Initialize FastHerbie
print("Initializing FastHerbie")
FH = FastHerbie(
    DATES,
    model="gfs",
    product="pgrb2.1p00",
    source="nomads",
    fxx=[0, 3],  # Get both analysis and 3-hour forecasts
    max_threads=5,  # Conservative thread count
)


def process_grib_files(grib_files: list[Path]):
    """Process downloaded GRIB files to JSON"""
    print("Processing to JSON...")

    files_by_valid_time = {}

    for grib_file in grib_files:
        try:
            # Extract date from the directory structure
            # Expected path: public/data/weather/gfs/YYYYMMDD/subset_*.pgrb2.1p00.f000
            parts = grib_file.parts
            date_part = parts[-2]  # '20250115'
            date_obj = datetime.strptime(date_part, "%Y%m%d")
            year = date_obj.strftime("%Y")
            month = date_obj.strftime("%m")
            day = date_obj.strftime("%d")

            # Extract run time and forecast hour
            run_match = re.search(r"t(\d{2})z", grib_file.name)
            forecast_match = re.search(r"\.f(\d{3})", grib_file.name)

            if not (run_match and forecast_match):
                print(f"Skipping file with invalid name pattern: {grib_file}")
                continue

            run_hour = int(run_match.group(1))
            forecast_hours = int(forecast_match.group(1))

            # Calculate actual valid time
            base_time = datetime(int(year), int(month), int(day), run_hour)
            valid_time = base_time + timedelta(hours=forecast_hours)

            # Format hour stamp for filename (e.g., "0300")
            hour_stamp = f"{valid_time.hour:02d}00"

            # Key for grouping files
            valid_time_key = (
                valid_time.year,
                valid_time.month,
                valid_time.day,
                valid_time.hour,
            )

            file_info = {
                "hour_stamp": hour_stamp,
                "file": grib_file,
                "is_analysis": forecast_hours == 0,
                "run_hour": run_hour,
                "valid_time": valid_time,
            }

            if valid_time_key not in files_by_valid_time:
                files_by_valid_time[valid_time_key] = []
            files_by_valid_time[valid_time_key].append(file_info)

        except Exception as e:
            print(f"Error processing {grib_file}: {e}")
            continue

    # Process each valid time point
    for valid_time_key, file_infos in sorted(files_by_valid_time.items()):
        # Prefer analysis files over forecast files
        selected_file = None
        for file_info in file_infos:
            if file_info["is_analysis"]:
                selected_file = file_info
                break
        if not selected_file:
            # If no analysis file, take the forecast from the most recent run
            selected_file = max(file_infos, key=lambda x: x["run_hour"])

        year, month, day, _ = valid_time_key
        output_dir = Path(f"public/data/weather/{year}/{month:02d}/{day:02d}")
        output_dir.mkdir(parents=True, exist_ok=True)

        hour_stamp = selected_file["hour_stamp"]
        grib_file = selected_file["file"]

        print(f"Processing files for {year}-{month}-{day} at {hour_stamp} UTC")

        # Generate output filenames for each level
        for level in ["surface"] + PRESSURE_LEVELS:
            if level == "surface":
                outfile = f"{hour_stamp}-wind-surface-level-gfs-1.0.json"
                fs = "103" # filter surface type code
            else:
                outfile = f"{hour_stamp}-wind-isobaric-{level}hPa-gfs-1.0.json"
                fs = "100"
            output_path = output_dir / outfile

            try:
                subprocess.run(
                    [
                        "grib2json",
                        "-d",  # Print data
                        "-n",  # Print names
                        "--filter.surface", str(fs), # Filter by level (surface type)
                        "--filter.value", str(LEVEL_SURFACE_VALUE_MAP[level]), # Filter by level (surface value)
                        "-o",
                        str(output_path),
                        str(grib_file),
                    ],
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                print(f"Error processing {grib_file}: {e}")
                continue

    # Handle 'current' wind files
    print("Generating 'current' wind files...")
    generate_current_wind_files()


def validate_time_sequence(files_by_valid_time):
    """Ensure we have a complete sequence of files at 3-hour intervals"""
    times = sorted(files_by_valid_time.keys())
    if not times:
        return False

    expected_hours = range(0, 24, 3)
    actual_hours = [t[3] for t in times]

    missing_hours = set(expected_hours) - set(actual_hours)
    if missing_hours:
        print(f"Warning: Missing data for hours: {missing_hours}")
        return False
    return True


def generate_current_wind_files():
    """
    Generates 'current' wind JSON files by selecting the latest available data for each level.
    Surface level is prioritized from the most recent date, and other levels fallback to older dates if needed.
    """
    weather_dir = Path("public/data/weather")
    if not weather_dir.exists():
        print(f"Weather directory '{weather_dir}' does not exist.")
        return

    # Dictionary to hold the latest file for each level
    latest_files = {}

    # Iterate over all JSON files recursively and find the latest for each level
    for json_file in weather_dir.rglob("*.json"):
        # Parse filename to extract stamp and level
        match = re.match(
            r"(\d{4})-wind-(surface-level|isobaric-\d+hPa)-gfs-1\.0\.json",
            json_file.name,
        )
        if match:
            stamp, level = match.groups()
            try:
                # Extract date from path: assuming public/data/weather/YYYY/MM/DD/filename.json
                year = json_file.parent.parent.parent.name
                month = json_file.parent.parent.name
                day = json_file.parent.name
                file_date = datetime.strptime(
                    f"{year}{month}{day}{stamp}", "%Y%m%d%H%M"
                )
            except Exception as e:
                print(f"Error parsing date from path '{json_file}': {e}")
                continue

            # Update latest_files if this file is newer
            if level not in latest_files or file_date > latest_files[level]["date"]:
                latest_files[level] = {"date": file_date, "file": json_file}

    if not latest_files:
        print("No 'current' wind files found to generate.")
        return

    # Create or update 'current' directory
    current_dir = weather_dir / "current"
    current_dir.mkdir(parents=True, exist_ok=True)

    # Copy the latest files to 'current' directory with the 'current' stamp
    for level, info in latest_files.items():
        src_file = info["file"]
        if level == "surface":
            outfile = "current-wind-surface-level-gfs-1.0.json"
        else:
            outfile = f"current-wind-{level}-gfs-1.0.json"
        dest_file = current_dir / outfile
        try:
            shutil.copy2(src_file, dest_file)
            print(f"Copied '{src_file}' to '{dest_file}'")
        except Exception as e:
            print(f"Failed to copy '{src_file}' to '{dest_file}': {e}")


# Download and process
print("Downloading files...")
grib_files = FH.download(
    search=SEARCH_PATTERN, save_dir=Path("public/data/weather"), max_threads=5
)

process_grib_files(grib_files)
