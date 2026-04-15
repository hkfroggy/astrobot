"""
Weather widget — top panel (280, 0, 744, 320).

Upper section  Left: current conditions (left-aligned, two compact rows)
               Right: 3-day sunrise colour forecast (red-sky prediction)
Lower section  Altitude-over-time chart: Milky Way core + Moon across tonight
"""
import pygame
import math
import requests
import datetime
import config
from .base import BaseWidget

try:
    import ephem as _ephem_mod
    _EPHEM = True
except ImportError:
    _ephem_mod = None
    _EPHEM = False

# ── WMO weather code → label ──────────────────────────────────────────────────
_WMO = {
    0: "Clear", 1: "Mostly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy Fog",
    51: "Lt Drizzle", 53: "Drizzle", 55: "Hvy Drizzle",
    61: "Lt Rain",    63: "Rain",    65: "Hvy Rain",
    71: "Lt Snow",    73: "Snow",    75: "Hvy Snow",   77: "Snow Grains",
    80: "Showers",   81: "Showers", 82: "Hvy Showers",
    85: "Snow Shwrs", 86: "Hvy Snow Shwrs",
    95: "Thunderstorm", 96: "T-Storm+Hail", 99: "T-Storm+Hail",
}


def _desc(code):
    return _WMO.get(code, f"Code {code}")


def _draw_icon(surf, code, cx, cy, size):
    """Minimal hand-drawn weather icon centred at (cx, cy)."""
    s = size // 2
    c = code or 0
    if c == 0:
        pygame.draw.circle(surf, (255, 220, 50), (cx, cy), s - 2)
        for a in range(0, 360, 45):
            r = math.radians(a)
            pygame.draw.line(surf, (255, 220, 50),
                             (cx + int((s+1)*math.cos(r)), cy + int((s+1)*math.sin(r))),
                             (cx + int((s+7)*math.cos(r)), cy + int((s+7)*math.sin(r))), 2)
    elif c in (1, 2):
        pygame.draw.circle(surf, (255, 210, 50), (cx - s//3, cy - s//3), s//2 + 2)
        pygame.draw.ellipse(surf, (180, 190, 215), pygame.Rect(cx-s, cy, s*2, s))
    elif c == 3:
        pygame.draw.ellipse(surf, (130, 145, 175), pygame.Rect(cx-s, cy-s//2, s*2, s))
    elif c in (45, 48):
        for i in range(3):
            fy = cy - s//2 + i*(s//2)
            pygame.draw.line(surf, (140, 155, 175), (cx-s, fy), (cx+s, fy), 2)
    elif 51 <= c <= 67 or c in (80, 81, 82):
        pygame.draw.ellipse(surf, (90, 115, 165), pygame.Rect(cx-s, cy-s//2, s*2, s))
        for i in range(3):
            rx = cx - s//2 + i*(s//2)
            pygame.draw.line(surf, (75, 140, 225), (rx, cy+4), (rx-4, cy+s), 2)
    elif 71 <= c <= 77 or c in (85, 86):
        pygame.draw.ellipse(surf, (165, 178, 200), pygame.Rect(cx-s, cy-s//2, s*2, s))
        for i in range(3):
            rx = cx - s//2 + i*(s//2)
            pygame.draw.circle(surf, (220, 228, 255), (rx, cy+s//2), 3)
    elif c >= 95:
        pygame.draw.ellipse(surf, (70, 78, 100), pygame.Rect(cx-s, cy-s//2, s*2, s))
        pygame.draw.lines(surf, (255, 220, 50), False,
                          [(cx+2, cy), (cx-5, cy+s//2), (cx+2, cy+s//3), (cx-3, cy+s)], 2)
    else:
        pygame.draw.circle(surf, config.TEXT_MID, (cx, cy), s//2)


# ── Sunrise colour forecast ───────────────────────────────────────────────────
#
# "Red sky at morning" rule: dramatic sunrise colour requires mid/high-altitude
# clouds (cirrus, altocumulus) in the eastern sky to scatter the low-angle red
# light.  Pure clear skies give only a faint glow; total overcast hides it.
# We fetch 5 days of hourly cloud-cover from Open-Meteo and evaluate the ~1-hour
# window around each sunrise.

def _classify_sunrise(total, low, mid, high, wcode):
    """
    Return (label, detail, color) for how colourful the sunrise will be.
    All cloud inputs are 0-100 %.
    """
    # Precipitation blocks everything
    if wcode is not None and wcode >= 51:
        return "Rain / Snow",  "Precipitation expected",     (90,  100, 120)

    sky_painters = (mid or 0) + (high or 0)   # mid/high clouds catch the light
    ground_block = (low or 0)                  # low stratus blocks the view

    if total is None:
        return "No data", "", (80, 90, 110)

    if total > 92:
        return "Overcast",      "Sky hidden",                (80,  90,  110)
    if total < 8:
        return "Clear",         "Faint glow only",           (220, 200,  80)

    # Ideal window: plenty of high/mid canvas, not blocked by low cloud
    if sky_painters >= 40 and ground_block < 55:
        if sky_painters >= 65:
            return "Vivid Red!",    "High clouds will glow",     (255,  70,  50)
        else:
            return "Good Color",    "Scattered clouds → orange", (255, 140,  45)

    if total < 45 and ground_block < 45:
        return "Some Color",    "Patchy clouds, worth a look",   (200, 165,  55)

    if ground_block > 70:
        return "Low Cloud",     "Stratus may hide the glow",     (110, 125, 150)

    return "Partly Cloudy",     "Mild color possible",           (150, 155, 120)


def _process_sunrise_forecast(raw_data):
    """
    Build a 5-entry list from open-meteo JSON (5-day hourly + daily).
    Each entry: {label, time, verdict, detail, color}
    """
    try:
        hourly = raw_data.get("hourly", {})
        daily  = raw_data.get("daily",  {})

        times   = hourly.get("time",             [])
        cc_tot  = hourly.get("cloudcover",        [])
        cc_low  = hourly.get("cloudcover_low",    [])
        cc_mid  = hourly.get("cloudcover_mid",    [])
        cc_high = hourly.get("cloudcover_high",   [])
        h_wcode = hourly.get("weathercode",       [])

        # Build a quick lookup: "YYYY-MM-DDTHH:00" → index
        idx_map = {t: i for i, t in enumerate(times)}

        sunrises = daily.get("sunrise", [])
        result   = []
        day_labels = ["Today", "Tmrw"]

        for day_i, sr_iso in enumerate(sunrises[:5]):
            if not sr_iso:
                continue
            try:
                sr_dt = datetime.datetime.fromisoformat(sr_iso)
                # Round to nearest hour for the lookup key
                sr_h  = sr_dt.replace(minute=0, second=0, microsecond=0)
                # Collect values from the hour before → hour after sunrise
                tots, lows, mids, highs, wcodes = [], [], [], [], []
                for dh in (-1, 0, 1):
                    key = (sr_h + datetime.timedelta(hours=dh)).strftime("%Y-%m-%dT%H:%M")
                    j = idx_map.get(key)
                    if j is not None and j < len(cc_tot):
                        tots.append(cc_tot[j]  if j < len(cc_tot)  else None)
                        lows.append(cc_low[j]  if j < len(cc_low)  else None)
                        mids.append(cc_mid[j]  if j < len(cc_mid)  else None)
                        highs.append(cc_high[j] if j < len(cc_high) else None)
                        wcodes.append(h_wcode[j] if j < len(h_wcode) else None)

                def _avg(lst):
                    v = [x for x in lst if x is not None]
                    return sum(v) / len(v) if v else None

                # Use worst weather code in window
                wc = max((w for w in wcodes if w is not None), default=None)
                verdict, detail, color = _classify_sunrise(
                    _avg(tots), _avg(lows), _avg(mids), _avg(highs), wc
                )
                lbl = day_labels[day_i] if day_i < len(day_labels) else sr_dt.strftime("%a")
                result.append({
                    "label":   lbl,
                    "time":    sr_dt.strftime("%-I:%M %p"),
                    "verdict": verdict,
                    "detail":  detail,
                    "color":   color,
                })
            except Exception as e:
                print(f"[sunrise day {day_i}] {e}")
        return result

    except Exception as e:
        print(f"[sunrise forecast] {e}")
        return []


# ── Sky position + hourly chart computation ───────────────────────────────────

_GC_RA  = "17:45:40"
_GC_DEC = "-29:00:28"

_COMPASS16 = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
              "S","SSW","SW","WSW","W","WNW","NW","NNW"]


def _az_label(deg):
    return _COMPASS16[round(deg / 22.5) % 16]


def _hour_label(h):
    h = h % 24
    if   h == 0:  return "12a"
    elif h < 12:  return f"{h}a"
    elif h == 12: return "12p"
    else:         return f"{h - 12}p"


def _compute_sky_positions():
    out = {
        "moon_az": None, "moon_alt": None,
        "moon_illum": 0, "moon_rise": "--", "moon_set": "--",
        "mw_az": None, "mw_alt": None, "mw_transit": "--",
        "is_dark": False, "dark_start": "--", "dark_end": "--",
        "chart": {},
    }
    if not _EPHEM:
        return out
    try:
        now = datetime.datetime.now()

        def _mk_obs(horizon="0"):
            o = _ephem_mod.Observer()
            o.lat     = str(config.LATITUDE)
            o.lon     = str(config.LONGITUDE)
            o.date    = now
            o.horizon = horizon
            return o

        def _fmt(t):
            try:    return _ephem_mod.localtime(t).strftime("%-I:%M %p")
            except: return "--"

        obs = _mk_obs("0")

        moon = _ephem_mod.Moon(obs)
        out["moon_az"]    = math.degrees(float(moon.az))
        out["moon_alt"]   = math.degrees(float(moon.alt))
        out["moon_illum"] = round(moon.phase, 1)
        try:
            out["moon_rise"] = _fmt(obs.next_rising(moon))
            out["moon_set"]  = _fmt(obs.next_setting(moon))
        except Exception:
            pass

        gc = _ephem_mod.FixedBody()
        gc._ra = _GC_RA;  gc._dec = _GC_DEC;  gc._epoch = _ephem_mod.J2000
        gc.compute(obs)
        out["mw_az"]  = math.degrees(float(gc.az))
        out["mw_alt"] = math.degrees(float(gc.alt))
        try:
            out["mw_transit"] = _fmt(obs.next_transit(gc))
        except Exception:
            pass

        obs_sun = _mk_obs("-6")
        sun = _ephem_mod.Sun(obs_sun);  sun.compute(obs_sun)
        out["is_dark"] = float(sun.alt) < 0
        try: out["dark_start"] = _fmt(obs_sun.next_setting(sun))
        except Exception: pass
        try: out["dark_end"]   = _fmt(obs_sun.next_rising(sun))
        except Exception: pass

        # Hourly chart 17:00 → 07:00 (15 pts)
        base = now.replace(hour=17, minute=0, second=0, microsecond=0)
        if now.hour < 12:
            base -= datetime.timedelta(days=1)
        N_PTS     = 15
        labels    = []
        mw_alts   = []
        moon_alts = []
        for i in range(N_PTS):
            t = base + datetime.timedelta(hours=i)
            obs_t = _ephem_mod.Observer()
            obs_t.lat = str(config.LATITUDE);  obs_t.lon = str(config.LONGITUDE)
            obs_t.date = t;  obs_t.horizon = "0"
            gc_t = _ephem_mod.FixedBody()
            gc_t._ra = _GC_RA;  gc_t._dec = _GC_DEC;  gc_t._epoch = _ephem_mod.J2000
            gc_t.compute(obs_t)
            moon_t = _ephem_mod.Moon(obs_t)
            labels.append(_hour_label(t.hour))
            mw_alts.append(round(math.degrees(float(gc_t.alt)), 1))
            moon_alts.append(round(math.degrees(float(moon_t.alt)), 1))

        elapsed_h = (now - base).total_seconds() / 3600.0
        out["chart"] = {
            "labels":   labels,
            "mw":       mw_alts,
            "moon":     moon_alts,
            "now_frac": max(0.0, min(1.0, elapsed_h / (N_PTS - 1))),
        }

    except Exception as e:
        print(f"[sky pos] {e}")
    return out


# ── Mist / fog forecast ───────────────────────────────────────────────────────
#
# Morning mist and ground fog form when:
#   • relative humidity is high (≥80 %)
#   • temperature is near the dew point (small dew-point depression)
#   • winds are calm (< ~8 mph)
#   • the sky was clear overnight (radiative cooling)
# We evaluate the 2-hour pre-dawn window before each sunrise.

def _classify_mist(rh, dew_dep, wind_mph, wcode):
    """
    Return (verdict, color).
    rh        – relative humidity %
    dew_dep   – temperature_2m − dewpoint_2m (configured temperature unit)
    wind_mph  – wind speed in mph
    wcode     – WMO weather code (or None)
    """
    if wcode is not None and wcode in (45, 48):
        return "Dense Fog",   (110, 165, 215)
    if wcode is not None and wcode >= 51:
        return "Rainy",       ( 80, 100, 130)

    if rh is None:
        return "No data",     ( 80,  90, 110)

    # Normalise dew-point depression to °C for thresholding
    dep_c = (dew_dep / 1.8) if config.TEMP_UNIT == "F" else dew_dep

    if rh >= 95 and dep_c <= 1.5 and wind_mph < 4:
        return "Dense Mist",  (100, 155, 215)
    if rh >= 88 and dep_c <= 3.0 and wind_mph < 8:
        return "Mist Likely", ( 85, 140, 195)
    if rh >= 80 and dep_c <= 5.0:
        return "Misty",       ( 75, 125, 175)
    if rh >= 70:
        return "Damp Air",    ( 70, 110, 155)
    if rh >= 50:
        return "Dry-ish",     (145, 165, 130)
    return "Clear & Dry",     (190, 195, 140)


def _process_mist_forecast(raw_data):
    """
    5-entry list — conditions at pre-dawn (−2 h → sunrise) for each day.
    Each entry: {label, time, verdict, color}
    """
    try:
        hourly = raw_data.get("hourly", {})
        daily  = raw_data.get("daily",  {})

        times   = hourly.get("time",               [])
        rh_arr  = hourly.get("relative_humidity_2m",[])
        temp_arr= hourly.get("temperature_2m",     [])
        dew_arr = hourly.get("dewpoint_2m",        [])
        wind_arr= hourly.get("windspeed_10m",      [])
        wc_arr  = hourly.get("weathercode",        [])

        idx_map = {t: i for i, t in enumerate(times)}
        sunrises   = daily.get("sunrise", [])
        day_labels = ["Today", "Tmrw"]
        result = []

        for day_i, sr_iso in enumerate(sunrises[:5]):
            if not sr_iso:
                continue
            try:
                sr_dt = datetime.datetime.fromisoformat(sr_iso)
                sr_h  = sr_dt.replace(minute=0, second=0, microsecond=0)

                rhs, deps, winds, wcodes = [], [], [], []
                for dh in (-2, -1, 0):            # 2 h before → sunrise
                    key = (sr_h + datetime.timedelta(hours=dh)).strftime("%Y-%m-%dT%H:%M")
                    j = idx_map.get(key)
                    if j is not None:
                        if j < len(rh_arr):   rhs.append(rh_arr[j])
                        if j < len(temp_arr) and j < len(dew_arr) and \
                           temp_arr[j] is not None and dew_arr[j] is not None:
                            deps.append(temp_arr[j] - dew_arr[j])
                        if j < len(wind_arr): winds.append(wind_arr[j])
                        if j < len(wc_arr):   wcodes.append(wc_arr[j])

                def _avg(lst):
                    v = [x for x in lst if x is not None]
                    return sum(v) / len(v) if v else None

                wc = max((w for w in wcodes if w is not None), default=None)
                verdict, color = _classify_mist(
                    _avg(rhs), _avg(deps) or 10.0, _avg(winds) or 0.0, wc
                )
                lbl = day_labels[day_i] if day_i < len(day_labels) else sr_dt.strftime("%a")
                result.append({
                    "label":   lbl,
                    "time":    sr_dt.strftime("%-I:%M %p"),
                    "verdict": verdict,
                    "color":   color,
                })
            except Exception as e:
                print(f"[mist day {day_i}] {e}")
        return result

    except Exception as e:
        print(f"[mist forecast] {e}")
        return []


# ── Mini coloured cloud icon ──────────────────────────────────────────────────

def _draw_cloud_icon(surf, cx, cy, color):
    """
    Draw a small ~20×13 px stylised cloud centred at (cx, cy), filled with
    `color`.  For clear-sky entries we draw a sun disc instead.
    """
    r, g, b = color[0], color[1], color[2]

    # "Clear" verdict → draw a tiny sun
    if r > 200 and g > 180 and b < 120:
        pygame.draw.circle(surf, color, (cx, cy), 5)
        for a in range(0, 360, 60):
            rad = math.radians(a)
            pygame.draw.line(surf, color,
                             (cx + int(6 * math.cos(rad)), cy + int(6 * math.sin(rad))),
                             (cx + int(9 * math.cos(rad)), cy + int(9 * math.sin(rad))), 1)
        return

    # Cloud body: two overlapping circles for the bumps + a wide ellipse for the base
    #  bump-left  (-4, -2) r=5
    #  bump-right (+3, -3) r=4
    #  base        (0, +1) 11×6
    pygame.draw.circle(surf, color, (cx - 4, cy - 2), 5)
    pygame.draw.circle(surf, color, (cx + 3, cy - 3), 4)
    pygame.draw.ellipse(surf, color, pygame.Rect(cx - 9, cy - 1, 18, 7))


def _draw_mist_icon(surf, cx, cy, verdict, color):
    """
    Draw a small ~20×14 px mist/fog icon centred at (cx, cy).
      Dense Fog / Mist  → three horizontal wavy lines
      Damp / Dry-ish    → two short faint lines
      Rainy             → three diagonal rain drops
      Clear & Dry       → tiny sun disc + rays
    """
    r, g, b = color

    if "Clear" in verdict or "Dry" in verdict:
        # Sun
        pygame.draw.circle(surf, color, (cx, cy), 4)
        for a in range(0, 360, 60):
            rad = math.radians(a)
            pygame.draw.line(surf, color,
                             (cx + int(6 * math.cos(rad)), cy + int(6 * math.sin(rad))),
                             (cx + int(9 * math.cos(rad)), cy + int(9 * math.sin(rad))), 1)
        return

    if "Rain" in verdict:
        # Three diagonal drops below a small cloud puff
        pygame.draw.ellipse(surf, color, pygame.Rect(cx - 7, cy - 6, 14, 6))
        for i in range(3):
            dx = -4 + i * 4
            pygame.draw.line(surf, color, (cx + dx, cy + 2), (cx + dx - 2, cy + 7), 1)
        return

    # Mist / fog: stacked horizontal lines with varying width and alpha-like dimming
    rows = [(-5, 14, 2), (0, 18, 2), (5, 12, 1)]   # (dy, width, thickness)
    for dy, w, th in rows:
        pygame.draw.line(surf, color,
                         (cx - w // 2, cy + dy),
                         (cx + w // 2, cy + dy), th)
        # small curved end caps for a wavy feel
        pygame.draw.circle(surf, color, (cx - w // 2, cy + dy), th // 2 + 1 if th > 1 else 1)
        pygame.draw.circle(surf, color, (cx + w // 2, cy + dy), th // 2 + 1 if th > 1 else 1)


# ── Widget ────────────────────────────────────────────────────────────────────

class WeatherWidget(BaseWidget):

    def __init__(self, surface, rect):
        super().__init__(surface, rect)
        self._refresh_interval = config.WEATHER_REFRESH
        self._f_big   = self.make_font(48)
        self._f_large = self.make_font(20)
        self._f_med   = self.make_font(16)
        self._f_small = self.make_font(13)
        self._f_tiny  = self.make_font(11)

    def fetch_data(self):
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={config.LATITUDE}&longitude={config.LONGITUDE}"
            "&current=temperature_2m,weathercode,windspeed_10m,"
            "winddirection_10m,relativehumidity_2m,apparent_temperature"
            "&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset"
            "&hourly=cloudcover,cloudcover_low,cloudcover_mid,cloudcover_high,"
            "weathercode,relative_humidity_2m,temperature_2m,dewpoint_2m,windspeed_10m"
            f"&temperature_unit={'fahrenheit' if config.TEMP_UNIT == 'F' else 'celsius'}"
            "&windspeed_unit=mph"
            f"&timezone={config.TIMEZONE}&forecast_days=5"
        )
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        data["astro"]             = _compute_sky_positions()
        data["sunrise_forecast"]  = _process_sunrise_forecast(data)
        data["mist_forecast"]     = _process_mist_forecast(data)
        return data

    # ── Draw ─────────────────────────────────────────────────────────────────

    def draw(self):
        self.draw_bg()
        with self._lock:
            d = dict(self.data)

        if not d:
            self.loading(self._f_med)
            return

        cur      = d.get("current",          {})
        daily    = d.get("daily",            {})
        astro    = d.get("astro",            {})
        sr_fcst  = d.get("sunrise_forecast", [])
        mist_fcst= d.get("mist_forecast",    [])

        temp  = cur.get("temperature_2m",      "--")
        code  = cur.get("weathercode",          0)
        wind  = cur.get("windspeed_10m",        "--")
        wdir  = cur.get("winddirection_10m",    0)
        humid = cur.get("relativehumidity_2m",  "--")
        feels = cur.get("apparent_temperature", "--")
        hi    = (daily.get("temperature_2m_max") or ["--"])[0]
        lo    = (daily.get("temperature_2m_min") or ["--"])[0]
        sr    = (daily.get("sunrise")  or [""])[0]
        ss    = (daily.get("sunset")   or [""])[0]

        def fmt_t(iso):
            if not iso: return "--"
            try:    return datetime.datetime.fromisoformat(iso).strftime("%-I:%M %p")
            except: return iso[-5:] if len(iso) >= 5 else iso

        unit = "°F" if config.TEMP_UNIT == "F" else "°C"
        hi_s   = f"{round(hi)}{unit}"   if isinstance(hi,    (int, float)) else str(hi)
        lo_s   = f"{round(lo)}{unit}"   if isinstance(lo,    (int, float)) else str(lo)
        t_s    = f"{round(temp)}{unit}" if isinstance(temp,  (int, float)) else str(temp)
        fl_s   = f"Feels {round(feels)}{unit}" if isinstance(feels, (int, float)) else ""

        rx = self.rect.x + 12
        ry = self.rect.y + 10

        # ── Three-panel layout in the top 130 px ─────────────────────────────
        #
        #  [  Weather summary  |  Mist Forest  |  Sunrise Sky  ][ gear ]
        #
        # Gear left edge = SCREEN_WIDTH − 46 = 978 → leave 30 px → right limit 948.
        # Each side panel ≈ 174 px; weather summary gets the rest (~290 px).
        PANEL_RIGHT = self.rect.right - 78          # 946 — right text limit
        SR_DIV_X    = PANEL_RIGHT - 174             # sunrise panel left divider
        MIST_DIV_X  = SR_DIV_X   - 182             # mist panel left divider
        MIST_X      = MIST_DIV_X + 12              # mist text left
        SR_X        = SR_DIV_X   + 12              # sunrise text left

        # Row A  — temperature (left column) + condition name (right column)
        # Icon sits BELOW the temperature so it never overlaps the large text.
        self.text(t_s, self._f_big, config.TEXT_HI, rx, ry)

        # Icon: centred under the temperature number, well below the 48-px baseline
        _draw_icon(self.surface, code, rx + 32, ry + 74, 30)

        cond_x = rx + 112
        self.text(_desc(code), self._f_large, config.GOLD,     cond_x, ry + 4)
        self.text(fl_s,        self._f_small, config.TEXT_MID, cond_x, ry + 28)

        # Row B  — H/L + sunrise/sunset
        row_b = ry + 52
        self.text(f"H {hi_s}  L {lo_s}",   self._f_small, config.TEXT_MID, cond_x, row_b)
        self.text(f"\u2197 {fmt_t(sr)}  \u2198 {fmt_t(ss)}",
                  self._f_small, config.ORANGE, cond_x, row_b + 18)

        # Row C  — wind + humidity
        row_c = row_b + 40
        self.text(f"{_wind_label(wdir)}  {wind} mph",
                  self._f_small, config.TEXT_MID, cond_x, row_c)
        self.text(f"Humidity  {humid}%",
                  self._f_small, config.TEXT_MID, cond_x, row_c + 18)

        # Vertical dividers (weather | mist) and (mist | sunrise)
        for dx in (MIST_DIV_X, SR_DIV_X):
            pygame.draw.line(self.surface, config.DIVIDER,
                             (dx, self.rect.y + 8),
                             (dx, self.rect.y + 122), 1)

        # ── Mist Forest panel ─────────────────────────────────────────────────
        self._draw_mist_panel(mist_fcst, MIST_X, ry, SR_DIV_X - 4)

        # ── Sunrise colour panel ──────────────────────────────────────────────
        self._draw_sunrise_panel(sr_fcst, SR_X, ry, PANEL_RIGHT)

        # ── Horizontal divider before night chart ─────────────────────────────
        div_y = self.rect.y + 130
        pygame.draw.line(self.surface, config.DIVIDER,
                         (self.rect.x + 6, div_y),
                         (self.rect.right - 6, div_y), 1)

        # ── Night sky chart ───────────────────────────────────────────────────
        self._draw_night_chart(astro, div_y + 4)

    # ── Mist Forest panel ────────────────────────────────────────────────────
    #
    # Layout — 5 rows of 19 px each.
    # Each row:  [mist icon] [day] [verdict coloured] [time right-aligned]

    def _draw_mist_panel(self, mist_fcst, ax, ry, panel_right):
        HDR_COLOR = (110, 175, 220)
        self.text("MIST FOREST", self._f_small, HDR_COLOR, ax, ry)

        if not mist_fcst:
            self.text("No forecast data", self._f_tiny, config.TEXT_LO, ax, ry + 16)
            return

        ROW_H     = 19
        ICON_CX   = ax + 10
        DAY_X     = ax + 24
        VERDICT_X = ax + 60

        row_y = ry + 16
        for entry in mist_fcst[:5]:
            clr     = entry["color"]
            lbl     = entry["label"]
            t       = entry["time"]
            verdict = entry["verdict"]

            icon_cy = row_y + ROW_H // 2
            _draw_mist_icon(self.surface, ICON_CX, icon_cy, verdict, clr)
            self.text(lbl,     self._f_tiny, config.TEXT_MID, DAY_X,     row_y)
            self.text(verdict, self._f_tiny, clr,             VERDICT_X, row_y)
            self.text(t,       self._f_tiny, config.TEXT_LO,  panel_right, row_y, "topright")

            row_y += ROW_H

    # ── Sunrise colour panel ──────────────────────────────────────────────────
    #
    # Layout — 5 rows of 19 px each.
    # Each row:  [cloud icon] [day] [verdict coloured] [time right-aligned]

    def _draw_sunrise_panel(self, sr_fcst, ax, ry, panel_right):
        HDR_COLOR = (255, 175, 90)
        self.text("SUNRISE SKY", self._f_small, HDR_COLOR, ax, ry)

        if not sr_fcst:
            self.text("No forecast data", self._f_tiny, config.TEXT_LO, ax, ry + 16)
            return

        ROW_H     = 19
        ICON_CX   = ax + 10
        DAY_X     = ax + 24
        VERDICT_X = ax + 60

        row_y = ry + 16
        for entry in sr_fcst[:5]:
            clr     = entry["color"]
            lbl     = entry["label"]
            t       = entry["time"]
            verdict = entry["verdict"]

            icon_cy = row_y + ROW_H // 2
            _draw_cloud_icon(self.surface, ICON_CX, icon_cy, clr)
            self.text(lbl,     self._f_tiny, config.TEXT_MID, DAY_X,     row_y)
            self.text(verdict, self._f_tiny, clr,             VERDICT_X, row_y)
            self.text(t,       self._f_tiny, config.TEXT_LO,  panel_right, row_y, "topright")

            row_y += ROW_H

    # ── Night sky altitude chart ──────────────────────────────────────────────

    def _draw_night_chart(self, astro, top_y):
        chart      = astro.get("chart",       {})
        labels     = chart.get("labels",      [])
        mw_alts    = chart.get("mw",          [])
        moon_alts  = chart.get("moon",        [])
        now_frac   = chart.get("now_frac",   -1.0)
        is_dark    = astro.get("is_dark",     False)
        dark_start = astro.get("dark_start",  "--")
        dark_end   = astro.get("dark_end",    "--")
        moon_illum = astro.get("moon_illum",   0)
        n = len(mw_alts)

        # Header row
        hdr_clr = config.CYAN if is_dark else config.TEXT_LO
        self.text("NIGHT SKY", self._f_small, hdr_clr, self.rect.x + 10, top_y + 2)
        dk_str = ("Dark now  " if is_dark else "") + f"{dark_start}  →  {dark_end}"
        self.text(dk_str, self._f_tiny, config.TEXT_LO, self.rect.x + 108, top_y + 4)
        moon_clr = config.GOLD if moon_illum > 50 else config.TEXT_MID
        self.text(f"☽ {moon_illum:.0f}% lit", self._f_tiny, moon_clr,
                  self.rect.right - 76, top_y + 4, "topright")

        if n < 2:
            self.text("Computing…", self._f_small, config.TEXT_LO,
                      self.rect.centerx, top_y + 80, "midtop")
            return

        # Chart geometry
        lpad, rpad, tpad, bpad = 34, 8, 18, 18
        cx0 = self.rect.x + lpad
        cx1 = self.rect.right - rpad
        cy0 = top_y + tpad
        cy1 = self.rect.bottom - bpad
        cw, ch = cx1 - cx0, cy1 - cy0

        peak  = max((a for a in mw_alts + moon_alts if a is not None), default=30.0)
        y_max = max(30.0, peak + 4.0)
        y_min = -4.0
        y_span = y_max - y_min

        def yp(alt):
            return int(cy1 - max(0.0, min(1.0, (alt - y_min) / y_span)) * ch)

        def xp(i):
            return cx0 + int(i / (n - 1) * cw)

        h0 = yp(0.0)

        # Background + night shading
        pygame.draw.rect(self.surface, (7, 10, 22), pygame.Rect(cx0, cy0, cw, ch))
        pygame.draw.rect(self.surface, (10, 14, 30),
                         pygame.Rect(xp(2), cy0, xp(12) - xp(2), ch))

        # Y grid
        for g_alt in range(0, int(y_max) + 1, 10):
            gy = yp(g_alt)
            if cy0 <= gy <= cy1:
                pygame.draw.line(self.surface,
                                 config.DIVIDER if g_alt == 0 else (20, 30, 56),
                                 (cx0, gy), (cx1, gy), 1)
                self.text(f"{g_alt}°", self._f_tiny, config.TEXT_LO, cx0 - 4, gy, "midright")

        # X grid every 2 h
        for i in range(0, n, 2):
            pygame.draw.line(self.surface, (18, 26, 50), (xp(i), cy0), (xp(i), cy1), 1)

        # MW filled area
        poly = [(xp(0), h0)]
        for i, alt in enumerate(mw_alts):
            poly.append((xp(i), yp(max(0.0, alt))))
        poly.append((xp(n - 1), h0))
        if len(poly) >= 3:
            pygame.draw.polygon(self.surface, (38, 18, 72), poly)

        # Lines
        pygame.draw.lines(self.surface, config.PURPLE, False,
                          [(xp(i), yp(a)) for i, a in enumerate(mw_alts)], 2)
        pygame.draw.lines(self.surface, config.GOLD, False,
                          [(xp(i), yp(a)) for i, a in enumerate(moon_alts)], 1)

        # Horizon label
        self.text("Horizon", self._f_tiny, (35, 50, 90), cx0 + 4, h0 - 11)

        # "Now" marker
        if 0.0 <= now_frac <= 1.0:
            nx = cx0 + int(now_frac * cw)
            pygame.draw.line(self.surface, config.CYAN, (nx, cy0), (nx, cy1), 1)
            self.text("▼", self._f_tiny, config.CYAN, nx, cy0, "midtop")
            cur_i = round(now_frac * (n - 1))
            if 0 <= cur_i < n:
                for yval, clr, r in ((mw_alts[cur_i], config.PURPLE, 4),
                                     (moon_alts[cur_i], config.GOLD, 3)):
                    py = yp(yval)
                    if cy0 <= py <= cy1:
                        pygame.draw.circle(self.surface, clr, (nx, py), r)

        # X labels
        for i, lbl in enumerate(labels):
            if i % 2 == 0:
                lx = xp(i)
                pygame.draw.line(self.surface, config.DIVIDER, (lx, cy1), (lx, cy1 + 3), 1)
                self.text(lbl, self._f_tiny, config.TEXT_LO, lx, cy1 + 4, "midtop")

        # Legend + border
        self.text("★ MW Core", self._f_tiny, config.PURPLE, cx1 - 4, cy0 + 2,  "topright")
        self.text("☽ Moon",    self._f_tiny, config.GOLD,   cx1 - 4, cy0 + 14, "topright")
        pygame.draw.rect(self.surface, config.DIVIDER, pygame.Rect(cx0, cy0, cw, ch), 1)


# ── Helpers ───────────────────────────────────────────────────────────────────

_COMPASS = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]


def _wind_label(deg):
    if deg is None: return ""
    return _COMPASS[round(deg / 22.5) % 16]
