#!/bin/bash

# All available pressure levels as defined in the UI/code
ALL_LEVELS=("surface" "1000" "850" "700" "500" "250" "70" "10")

# Function to print usage
print_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -d, --date YYYYMMDD   Start date (default: current date)"
    echo "  -h, --hours N         Hours to download (default: 24)"
    echo "  -t, --hour HH         Start hour (default: current hour rounded to nearest 6)"
    echo "  -l, --levels LIST     Comma-separated list of levels to download"
    echo "                        Available levels: ${ALL_LEVELS[*]}"
    echo "                        (default: all levels)"
    echo
    echo "Examples:"
    echo "  $0                                   # Download all levels for next 24 hours"
    echo "  $0 -l surface,850,500               # Download only surface, 850hPa, and 500hPa levels"
    echo "  $0 -d 20250115 -h 48 -t 00         # Download all levels for 48 hours starting Jan 15, 2025 00Z"
    echo "  $0 -d 20250115 -l surface -h 6     # Download only surface level for 6 hours"
}

# Get current date in UTC
current_date=$(date -u +%Y%m%d)
current_hour=$(date -u +%H)
# Round down to nearest 6-hour block for GFS initialization times (00, 06, 12, 18)
current_hour=$((current_hour - current_hour % 6))

# Default settings
START_DATE=$current_date
HOURS=24
START_HOUR=$current_hour
LEVELS=("${ALL_LEVELS[@]}")  # Copy all levels by default

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--date)
            START_DATE="$2"
            shift 2
            ;;
        -h|--hours)
            HOURS="$2"
            shift 2
            ;;
        -t|--hour)
            START_HOUR="$2"
            shift 2
            ;;
        -l|--levels)
            IFS=',' read -ra LEVELS <<< "$2"
            # Validate levels
            for level in "${LEVELS[@]}"; do
                if [[ ! " ${ALL_LEVELS[@]} " =~ " ${level} " ]]; then
                    echo "Error: Invalid level '$level'"
                    echo "Available levels: ${ALL_LEVELS[*]}"
                    exit 1
                fi
            done
            shift 2
            ;;
        --help)
            print_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Calculate number of 3-hour timesteps needed
timesteps=$((HOURS / 3))

# Function to format date directory path
format_date_path() {
    local date=$1   # YYYYMMDD
    local year=${date:0:4}
    local month=${date:4:2}
    local day=${date:6:2}
    echo "$year/$month/$day"
}

# Function to format hour string
format_hour() {
    local hour=$1
    printf "%02d00" $hour
}

# Function to clean up temporary files
cleanup() {
    rm -f inventory_*.idx level_*.grb gfs.*.grb
}

# Set up trap for cleanup
trap cleanup EXIT

process_forecast() {
    local date=$1
    local init_hour=$2  # GFS initialization hour (00, 06, 12, 18)
    local fcst_hour=$3
    
    # Create date-based path
    local date_path=$(format_date_path $date)
    local hour_str=$(format_hour $((init_hour + fcst_hour)))
    
    # Ensure output directories exist
    local OUT_DIR="public/data/weather/${date_path}"
    mkdir -p "$OUT_DIR"
    
    # Pad hours with zeros
    init_hour=$(printf "%02d" $init_hour)
    fcst_hour=$(printf "%03d" $fcst_hour)
    
    echo "Processing $date ${init_hour}Z f${fcst_hour} (${hour_str})"
    
    GRIB_URL="https://nomads.ncep.noaa.gov/pub/data/nccf/com/gfs/prod/gfs.${date}/${init_hour}/atmos/gfs.t${init_hour}z.pgrb2.1p00.f${fcst_hour}"
    INV_URL="${GRIB_URL}.idx"
    
    # First check if the idx file exists
    if ! curl --head --silent --fail "${INV_URL}" > /dev/null; then
        echo "Index file not available: ${INV_URL}"
        return 1
    fi

    # Download inventory once and store locally
    local inv_file="inventory_${date}_${init_hour}_${fcst_hour}.idx"
    echo "Downloading inventory file..."
    ./get_inv.pl "$INV_URL" > "$inv_file"

    if [ ! -s "$inv_file" ]; then
        echo "Error: Empty or missing inventory file"
        return 1
    fi

    # Build combined egrep pattern for all requested levels
    local patterns=()
    for level in "${LEVELS[@]}"; do
        if [ "$level" == "surface" ]; then
            patterns+=(":(UGRD|VGRD):10 m above ground:")
        else
            patterns+=(":(UGRD|VGRD):${level} mb:")
        fi
    done
    
    # Join patterns with | to create single egrep expression
    local combined_pattern=$(IFS='|'; echo "${patterns[*]}")
    
    # Single GRIB download with all requested fields
    TEMP_GRIB="gfs.t${init_hour}z.pgrb2.1p00.f${fcst_hour}.wind.grb"
    echo "Downloading wind data for all requested levels..."
    
    # Download all levels at once using the local inventory
    egrep "$combined_pattern" "$inv_file" | ./get_grib.pl "$GRIB_URL" "$TEMP_GRIB"
    
    # Convert to separate JSON files for each level
    if [ -f "$TEMP_GRIB" ] && [ -s "$TEMP_GRIB" ]; then
        for level in "${LEVELS[@]}"; do
            if [ "$level" == "surface" ]; then
                filter=":(UGRD|VGRD):10 m above ground:"
                outfile="${hour_str}-wind-surface-level-gfs-1.0.json"
            else
                filter=":(UGRD|VGRD):${level} mb:"
                outfile="${hour_str}-wind-isobaric-${level}hPa-gfs-1.0.json"
            fi
            
            echo "Processing level: $level"
            
            # Extract data for this level
            grib2json -d -n -o "$outfile" "$TEMP_GRIB"
            if [ -f "$outfile" ]; then
                mv "$outfile" "${OUT_DIR}/"
                echo "Successfully processed $level -> ${OUT_DIR}/${outfile}"
            else
                echo "Failed to create JSON for level $level"
            fi
        done
    else
        echo "Failed to download wind data or empty GRIB file"
        return 1
    fi
}

# Process each timestep, considering GFS initialization times
current_date=$START_DATE
init_hour=$((START_HOUR - START_HOUR % 6))  # Round to nearest GFS init time
forecast_hour=0

# Print summary of what we're going to do
echo "Download settings:"
echo "  Start date: $current_date"
echo "  Initial hour: $init_hour"
echo "  Hours to download: $HOURS"
echo "  Levels: ${LEVELS[*]}"
echo

for ((i=0; i<=timesteps; i++)); do
    process_forecast $current_date $init_hour $forecast_hour
    
    # Increment 3 hours
    forecast_hour=$((forecast_hour + 3))
    
    # If forecast hour exceeds the available range for current init time,
    # move to next initialization time
    if [ $forecast_hour -ge 120 ]; then  # Arbitrary limit, adjust based on GFS availability
        init_hour=$((init_hour + 6))
        forecast_hour=0
        if [ $init_hour -ge 24 ]; then
            init_hour=0
            current_date=$(date -u -d "$current_date + 1 day" +%Y%m%d)
        fi
    fi
done

echo "All downloads complete"