# ── Display ───────────────────────────────────────────────────────────────────
SCREEN_WIDTH  = 1024
SCREEN_HEIGHT = 640
FPS           = 30
FULLSCREEN    = True   # set False for windowed dev mode

# ── Location — update for your site ──────────────────────────────────────────
LATITUDE      = 34.05       # decimal degrees N  (negative = S)
LONGITUDE     = -118.24     # decimal degrees E  (negative = W)
TIMEZONE      = "America/Los_Angeles"
LOCATION_NAME = "Los Angeles, CA"

# ── NOAA tide station ─────────────────────────────────────────────────────────
# Find your station ID at tidesandcurrents.noaa.gov/tide_predictions.html
# Leave empty ("") to skip tide data (non-US locations).
NOAA_STATION_ID   = "9410660"
NOAA_TIDE_UNITS   = "english"     # "english" = feet  |  "metric" = meters
NOAA_TIDE_UNIT_LBL = "ft"

# ── Temperature unit ─────────────────────────────────────────────────────────
TEMP_UNIT = "F"    # "F" = Fahrenheit  |  "C" = Celsius

# ── DSO filter defaults (overridden by settings.json) ────────────────────────
DSO_MAG_MIN     = 0.0    # brightest limit  (lower number = brighter)
DSO_MAG_MAX     = 12.0   # faintest limit
DSO_FOV_MIN     = 0.05   # smallest object FoV to show (degrees)
DSO_FOV_MAX     = 5.0    # largest object FoV to show (degrees)
DSO_SHOOT_START = 20.0   # shooting window start hour (24h decimal, e.g. 20.5 = 20:30)
DSO_SHOOT_END   =  5.0   # shooting window end   hour (24h decimal)

# ── Refresh intervals (seconds) ───────────────────────────────────────────────
WEATHER_REFRESH = 600    # 10 min
TIDE_REFRESH    = 3600   # 1 hr
ASTRO_REFRESH   = 300    # 5 min

# ── Layout rects (x, y, w, h) — must tile to 1024×640 ────────────────────────
LAYOUT = {
    "clock":    (0,   0,   280, 320),
    "weather":  (280, 0,   744, 320),
    "deep_sky": (0,   320, 360, 320),
    "moon":     (360, 320, 220, 320),
    "tides":    (580, 320, 444, 320),
}

# ── Color palette (dark-space theme) ─────────────────────────────────────────
BG_COLOR     = (  8,  10,  20)
PANEL_BG     = ( 12,  18,  34)
DIVIDER      = ( 30,  46,  78)

TEXT_HI      = (225, 235, 255)
TEXT_MID     = (145, 165, 210)
TEXT_LO      = ( 75,  98, 145)

GOLD         = (255, 205,  60)
BLUE         = ( 65, 145, 255)
CYAN         = ( 55, 210, 215)
RED          = (255,  85,  70)
GREEN        = ( 75, 215, 115)
ORANGE       = (255, 155,  45)
PURPLE       = (175, 100, 255)
PINK         = (255, 140, 180)

# Clock
CLOCK_BG     = ( 10,  16,  32)
CLOCK_RIM    = ( 42,  68, 118)
TICK_MAJOR   = (175, 200, 240)
TICK_MINOR   = ( 65,  90, 140)
HAND_H       = (220, 235, 255)
HAND_M       = (155, 195, 255)
HAND_S       = (255,  85,  70)

# Moon
MOON_LIT     = (232, 228, 205)
MOON_SHADOW  = ( 10,  14,  28)

# Tides
TIDE_LINE    = ( 65, 145, 255)
TIDE_FILL    = ( 15,  42,  92)

# ── Load user settings (settings.json overrides defaults above) ───────────────
def _load_user_settings():
    import json
    from pathlib import Path
    f = Path(__file__).parent / "settings.json"
    if not f.exists():
        return
    try:
        d = json.loads(f.read_text())
    except Exception:
        return
    global LATITUDE, LONGITUDE, TIMEZONE, LOCATION_NAME, TEMP_UNIT
    global DSO_MAG_MIN, DSO_MAG_MAX, DSO_FOV_MIN, DSO_FOV_MAX
    global DSO_SHOOT_START, DSO_SHOOT_END
    if "latitude"        in d: LATITUDE        = float(d["latitude"])
    if "longitude"       in d: LONGITUDE       = float(d["longitude"])
    if "timezone"        in d: TIMEZONE        = d["timezone"]
    if "location_name"   in d: LOCATION_NAME   = d["location_name"]
    if "temp_unit"       in d: TEMP_UNIT       = d["temp_unit"]
    if "dso_mag_min"     in d: DSO_MAG_MIN     = float(d["dso_mag_min"])
    if "dso_mag_max"     in d: DSO_MAG_MAX     = float(d["dso_mag_max"])
    if "dso_fov_min"     in d: DSO_FOV_MIN     = float(d["dso_fov_min"])
    if "dso_fov_max"     in d: DSO_FOV_MAX     = float(d["dso_fov_max"])
    if "dso_shoot_start" in d: DSO_SHOOT_START = float(d["dso_shoot_start"])
    if "dso_shoot_end"   in d: DSO_SHOOT_END   = float(d["dso_shoot_end"])

_load_user_settings()
