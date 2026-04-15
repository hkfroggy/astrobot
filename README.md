# AstroBot

A full-screen astronomy & weather dashboard for a 7-inch Raspberry Pi display (1024 × 640 px), built with Python and pygame.

---

## Features

### 🕐 Clock — top-left panel
- Full **analog clock** face with hour, minute, and sweeping second hand
- Tick marks and hour numerals on the dial
- **Date line** below the face (weekday, month, day, year)
- **5-day weather forecast strip** at the bottom of the panel
  - One column per day showing a weather icon, high temperature, low temperature
  - Rain probability badge (blue %) appears when chance ≥ 30 %
  - Today is highlighted in gold; remaining days show 3-letter abbreviation

---

### 🌤 Weather — top-right panel

#### Current Conditions (top-left of panel)
- Large current temperature with feels-like
- Hand-drawn weather icon (sun, cloud, rain, snow, fog, thunderstorm)
- Condition description, H/L temperatures
- Sunrise ↗ and sunset ↘ times
- Wind direction + speed, relative humidity

#### Mist Forest Forecast (top-centre of panel)
- 5-day morning mist prediction evaluated at the pre-dawn window (−2 h → sunrise)
- Uses relative humidity, dew-point depression, and wind speed
- Verdicts: **Dense Mist → Mist Likely → Misty → Damp Air → Dry-ish → Clear & Dry**
- Each row shows a colour-coded mist icon (wavy lines or sun), day label, verdict, and sunrise time

#### Sunrise Sky Forecast (top-right of panel)
- 5-day sunrise colour prediction based on the "red sky at morning" rule
- Evaluates mid/high cloud cover vs. low stratus in the ±1 h sunrise window
- Verdicts: **Vivid Red! → Good Color → Some Color → Clear → Low Cloud → Overcast → Rain/Snow**
- Each row shows a colour-coded cloud icon, day label, verdict, and sunrise time

#### Night Sky Altitude Chart (lower section)
- Hourly altitude chart from 17:00 → 07:00 (next morning)
- **Purple filled area + line** — Milky Way galactic core (Sgr A*) altitude
- **Gold line** — Moon altitude across the night
- **Cyan now-marker** — current time position with dots at actual object altitudes
- Dark-window shading (astronomical twilight period)
- Dark-time header showing dark-window start → end and Moon illumination %

---

### 🔭 Deep Sky — bottom-left panel
- Rotating slideshow of up to **10 tonight's best DSOs** (filtered by altitude ≥ 20°, magnitude, FoV, and shooting window)
- Real astronomical images fetched from **CDS DSS2 colour survey** (2MASS infrared fallback)
- Animated loading spinner while images download; procedural placeholder art as final fallback
- Image overlay: object name, common name, constellation badge (top-right), type colour badge, magnitude, max altitude, rise–set window, transit time
- **Page dots** at the bottom indicating current slide position
- Auto-advances every 10 seconds
- Catalog of 28 objects including galaxies, nebulae, clusters, SNRs, and dark nebulae

---

### 🌙 Moon — bottom-centre panel
- **High-fidelity phase disk** rendered entirely in code
  - Correct lit/dark terminator for any phase fraction
  - **11 lunar maria** (Mare Imbrium, Tranquillitatis, Crisium, etc.) drawn as soft blobs on the lit face
  - **Limb-darkening** gradient pressed against the lunar rim
  - **Atmospheric glow corona** around the disk near full / gibbous phases
- Phase name (New Moon → Waxing Crescent → … → Waning Crescent)
- Illumination percentage and lunar day (e.g. "Day 7.3 of 29.5")
- Next **rise** ▲ and **set** ▼ times in two columns

---

### 🌊 Tides & Swell — bottom-right panel

#### Tide Chart (top half)
- 24-hour **tide height curve** for today — filled area + line
- **Cyan now-marker** dot on the curve at the current hour
- **Gold H / Blue L** dot annotations at each high and low tide, with height labels

#### Swell Chart (bottom half)
- 24-hour **wave height chart** — filled area + line
- **Cyan now-marker** with current wave height label
- Header line: current wave height (m), period (s), compass direction, direction arrow
- Both charts are exactly equal height, split 50 / 50

---

### ⚙ Settings Overlay
- Opens via the **gear button** (top-right corner) or pressing `S`
- Editable fields: location name, latitude, longitude, timezone, temperature unit (°F / °C)
- DSO filter sliders: magnitude range, FoV range, shooting window start/end
- **Save** writes `settings.json` and immediately re-fetches all widget data with the new location/units
- **Cancel** discards changes

---

### General
- Runs **full-screen at 1024 × 640 px** on Raspberry Pi; `--windowed` flag for desktop development
- Dark space-theme colour palette throughout
- All network data fetched in **background threads** — UI never blocks on API calls
- Per-widget configurable **refresh intervals** (weather 10 min, tides 1 h, astronomy 5 min)
- Mouse cursor always visible; `Esc` or `Q` to quit
- Custom **white-robot-on-blue** app icon drawn entirely with pygame primitives

---

## Data Sources

All data sources used by AstroBot are **free and require no API key**.

---

### 🌤 Open-Meteo Weather API
**Used by:** Weather widget (current conditions, hourly cloud cover, sunrise-colour & mist forecasts), Clock widget (5-day daily forecast)  
**Endpoint:** `https://api.open-meteo.com/v1/forecast`  
**Docs:** https://open-meteo.com/en/docs  
**Licence:** Free for non-commercial use (CC BY 4.0)

| Data pulled | Widget |
|---|---|
| Current temperature, feels-like, weather code, wind, humidity | Weather |
| Daily max/min temperature, sunrise, sunset (5 days) | Weather, Clock |
| Hourly cloud cover (total, low, mid, high) | Weather — sunrise-colour prediction |
| Hourly relative humidity, dew point, wind speed | Weather — mist-forest prediction |
| Daily weather code + hi/lo + rain probability (5 days) | Clock — forecast strip |

**No registration or API key required.**

---

### 🌊 Open-Meteo Marine API
**Used by:** Tides & Swell widget  
**Endpoint:** `https://marine-api.open-meteo.com/v1/marine`  
**Docs:** https://open-meteo.com/en/docs/marine-weather-api  
**Licence:** Free for non-commercial use (CC BY 4.0)

| Data pulled | Widget |
|---|---|
| Hourly wave height (m) — 24-hour chart | Tides & Swell |
| Current wave period (s) | Tides & Swell |
| Current wave direction (°) | Tides & Swell |

Provides global swell coverage. Works even when no NOAA station is configured.  
**No registration or API key required.**

---

### 🌊 NOAA CO-OPS Tides & Currents API
**Used by:** Tides & Swell widget  
**Endpoint:** `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter`  
**Docs:** https://api.tidesandcurrents.noaa.gov/api/prod/  
**Coverage:** US coastal stations only

| Data pulled | Widget |
|---|---|
| Hourly tide height predictions (24 h) — tide curve | Tides & Swell |
| High/Low tide times and heights | Tides & Swell (chart annotations) |

Set your local station ID in `config.py` → `NOAA_STATION_ID`.  
Find your station at https://tidesandcurrents.noaa.gov/tide_predictions.html  
Leave `NOAA_STATION_ID = ""` to disable (swell data still works).  
**No registration or API key required.**

---

### 🔭 CDS HiPS2FITS — Astronomical Image Service
**Used by:** Deep Sky widget  
**Endpoint:** `https://alasky.u-strasbg.fr/hips-image-services/hips2fits`  
**Docs:** https://aladin.cds.unistra.fr/hips/  
**Provider:** Centre de Données astronomiques de Strasbourg (CDS)

| Data pulled | Widget |
|---|---|
| DSS2 colour images (primary survey) | Deep Sky — object slideshow |
| 2MASS near-infrared images (fallback) | Deep Sky — object slideshow |

Images are fetched on demand for each DSO in the nightly list and cached in memory for the session. FoV and position are computed per-object.  
**No registration or API key required.**

---

### 🌙 PyEphem — Local Astronomical Calculations
**Used by:** Moon widget, Weather widget (night-sky chart), Deep Sky widget  
**Library:** `ephem` (Python package)  
**Install:** `pip install ephem`  
**Docs:** https://rhodesmill.org/pyephem/  

All calculations run **locally on the device** — no network calls.

| Calculation | Widget |
|---|---|
| Moon phase fraction, illumination %, age (days) | Moon |
| Moon rise / set times | Moon |
| Moon azimuth & altitude (hourly chart) | Weather — night-sky chart |
| Galactic centre (Sgr A*) azimuth & altitude (hourly chart) | Weather — night-sky chart |
| Astronomical dark window (Sun < −6°) | Weather — night-sky chart |
| DSO transit time, max altitude, rise/set window | Deep Sky — nightly list |

If `ephem` is not installed the app falls back to simplified approximations where possible.

---

## Configuration

Edit `config.py` to set your location, units, and NOAA station:

```python
LATITUDE      = 34.05        # decimal degrees N (negative = S)
LONGITUDE     = -118.24      # decimal degrees E (negative = W)
TIMEZONE      = "America/Los_Angeles"
TEMP_UNIT     = "F"          # "F" or "C"
NOAA_STATION_ID = "9410660"  # leave "" to disable tides
```

Settings can also be changed at runtime via the ⚙ gear button (top-right corner).

---

## Requirements

```
pygame>=2.0
requests
ephem          # optional but recommended
```

Install:
```bash
pip install -r requirements.txt
```

Run:
```bash
python main.py             # full-screen
python main.py --windowed  # windowed / dev mode
```
