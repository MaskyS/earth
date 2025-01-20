# Key GFS Data Usage Concepts

### Why Mix Analysis and Forecast Files

- GFS produces full analysis (f000) only every 6 hours (00Z, 06Z, 12Z, 18Z)
- Frontend requires 3-hour resolution for smooth animations/transitions
- Gap-filling strategy:
```
00Z: analysis (f000) from 00Z run
03Z: forecast (f003) from 00Z run
06Z: analysis (f000) from 06Z run
09Z: forecast (f003) from 06Z run
...etc
```
- This provides complete 3-hour resolution data while using the most accurate data available at each time point.

### GFS Data Structure
- GFS (Global Forecast System) produces data 4x daily at 00Z, 06Z, 12Z, and 18Z
- Each run produces:
  - Analysis (f000): Current conditions for that run time
  - Forecasts (f003, f006, etc.): Predictions for future times
- Analysis files are always preferred over forecast files when both exist for a timestamp

### File Naming Conventions (DO NOT MODIFY)
- Format: `HHMM-wind-<level>-gfs-1.0.json` 
- Example: `0600-wind-isobaric-1000hPa-gfs-1.0.json`
- The frontend expects these exact names and will break if changed

### Pressure Levels (DO NOT MODIFY)
```python
PRESSURE_LEVELS = ["1000", "850", "700", "500", "250", "70", "10"]
```
- These specific levels are required by the frontend
- Order matters - used in both filename construction and GRIB data extraction
- "surface" is a special level handled separately

### GRIB Search Pattern
- The complex GRIB pattern combines both U and V wind components
- Required for all pressure levels AND surface (10m above ground)
- Must maintain exact format for FastHerbie to work

### Critical Directory Structure
```
public/data/weather/YYYY/MM/DD/HHMM-wind-*.json
public/data/weather/current/current-wind-*.json
```
- Frontend relies on this exact structure
- "current" directory special handling required

## Hidden Dependencies

### Earth.js Integration
- Frontend expects 3-hour resolution data (00, 03, 06, 09, 12, 15, 18, 21)
- Uses both analysis and forecast files to achieve this
- Animations depend on continuous 3-hour data availability

### FastHerbie Usage
- `fxx=[0, 3]` is crucial - must get both analysis and 3-hour forecasts
- Don't increase `max_threads` above 5 (NOMADS server restriction)

### grib2json Assumptions
- Always called with `-d` and `-n` flags
- Outputs must maintain specific JSON structure for frontend

## Potential Pitfalls

### Time Handling
- All times are UTC
- GFS uses forecasts relative to run time (f000, f003)
- Frontend expects absolute times (0300, 0600)
- Time conversion must account for day boundaries

### File Selection Logic
1. Always prefer analysis (f000) files
2. When no analysis exists, use forecast from most recent run
3. Never mix data sources for same pressure level