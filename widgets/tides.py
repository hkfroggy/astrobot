"""
Tides & Swell widget.
  Tides  — NOAA CO-OPS API (free, no key; US stations only)
           Set NOAA_STATION_ID = "" in config.py to disable.
  Swell  — Open-Meteo Marine API (free, no key; global coverage)
"""
import pygame
import math
import requests
import datetime
import config
from .base import BaseWidget


class TidesWidget(BaseWidget):

    def __init__(self, surface, rect):
        super().__init__(surface, rect)
        self._refresh_interval = config.TIDE_REFRESH
        self._f_title  = self.make_font(14)
        self._f_med    = self.make_font(16)
        self._f_small  = self.make_font(13)
        self._f_tiny   = self.make_font(11)

    def fetch_data(self):
        result = {"tides": None, "hilo": [], "swell": None}

        today  = datetime.date.today()
        ds     = today.strftime("%Y%m%d")
        de     = (today + datetime.timedelta(days=1)).strftime("%Y%m%d")

        # ── NOAA hourly tide predictions ──────────────────────────────────────
        if config.NOAA_STATION_ID:
            try:
                url = (
                    "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
                    f"?begin_date={ds}&end_date={ds}&station={config.NOAA_STATION_ID}"
                    f"&product=predictions&datum=MLLW&time_zone=lst_ldt"
                    f"&interval=h&units={config.NOAA_TIDE_UNITS}"
                    "&application=astrobot&format=json"
                )
                r = requests.get(url, timeout=10)
                r.raise_for_status()
                predictions = r.json().get("predictions", [])
                result["tides"] = [
                    (p["t"][-5:], float(p["v"]))   # "HH:MM", height
                    for p in predictions
                ]
            except Exception as e:
                print(f"[Tides] NOAA hourly error: {e}")

            # High/Low tide times
            try:
                url_hilo = (
                    "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
                    f"?begin_date={ds}&end_date={de}&station={config.NOAA_STATION_ID}"
                    f"&product=predictions&datum=MLLW&time_zone=lst_ldt"
                    f"&interval=hilo&units={config.NOAA_TIDE_UNITS}"
                    "&application=astrobot&format=json"
                )
                r = requests.get(url_hilo, timeout=10)
                r.raise_for_status()
                hilo_raw = r.json().get("predictions", [])
                result["hilo"] = [
                    {
                        "type":   p["type"],         # "H" or "L"
                        "time":   p["t"][-5:],        # "HH:MM"
                        "height": float(p["v"]),
                    }
                    for p in hilo_raw
                    if p["t"][:10] == today.isoformat()
                ]
            except Exception as e:
                print(f"[Tides] NOAA hilo error: {e}")

        # ── Open-Meteo Marine (swell) ─────────────────────────────────────────
        try:
            url_m = (
                "https://marine-api.open-meteo.com/v1/marine"
                f"?latitude={config.LATITUDE}&longitude={config.LONGITUDE}"
                "&hourly=wave_height,wave_period,wave_direction"
                f"&timezone={config.TIMEZONE}&forecast_days=1"
            )
            r = requests.get(url_m, timeout=10)
            r.raise_for_status()
            hrly  = r.json().get("hourly", {})
            now_h = datetime.datetime.now().hour
            times = hrly.get("time", [])
            wh    = hrly.get("wave_height",    [None] * 24)
            wp    = hrly.get("wave_period",    [None] * 24)
            wd    = hrly.get("wave_direction", [None] * 24)

            # Build 24-slot arrays indexed by hour-of-day
            h_by_hr = [None] * 24
            p_by_hr = [None] * 24
            d_by_hr = [None] * 24
            for i, t_str in enumerate(times):
                try:
                    hr = datetime.datetime.fromisoformat(t_str).hour
                    if 0 <= hr < 24:
                        if i < len(wh): h_by_hr[hr] = wh[i]
                        if i < len(wp): p_by_hr[hr] = wp[i]
                        if i < len(wd): d_by_hr[hr] = wd[i]
                except Exception:
                    pass

            result["swell"] = {
                "height":    h_by_hr[now_h],
                "period":    p_by_hr[now_h],
                "direction": d_by_hr[now_h],
                "hourly_h":  h_by_hr,   # 24-slot wave-height series for chart
            }
        except Exception as e:
            print(f"[Tides] Marine error: {e}")

        return result

    def draw(self):
        self.draw_bg()
        with self._lock:
            d = dict(self.data)

        rx = self.rect.x + 10
        ry = self.rect.y + 8
        rw = self.rect.width  - 20
        rh = self.rect.height - 16

        # Title
        self.text("TIDES & SWELL", self._f_title, config.TEXT_LO,
                  self.rect.centerx, ry, "midtop")
        pygame.draw.line(self.surface, config.DIVIDER,
                         (self.rect.x + 6, ry + 18),
                         (self.rect.right - 6, ry + 18), 1)
        ry += 22

        if not d:
            self.loading(self._f_med)
            return

        tides = d.get("tides")
        hilo  = d.get("hilo",  [])
        swell = d.get("swell") or {}

        # ── Tide curve chart ──────────────────────────────────────────────────
        chart_h = 110
        chart_w = rw
        chart_x = rx
        chart_y = ry

        if tides:
            heights = [h for _, h in tides]
            mn, mx  = min(heights), max(heights)
            spread  = max(mx - mn, 0.5)

            def _px(i, h):
                px = chart_x + int(i * chart_w / (len(tides) - 1))
                py = chart_y + chart_h - int((h - mn) / spread * (chart_h - 10)) - 5
                return px, py

            # Filled area
            pts = [_px(i, h) for i, (_, h) in enumerate(tides)]
            poly = [pts[0]] + pts + [(pts[-1][0], chart_y + chart_h),
                                      (pts[0][0],  chart_y + chart_h)]
            pygame.draw.polygon(self.surface, config.TIDE_FILL, poly)
            # Line
            pygame.draw.lines(self.surface, config.TIDE_LINE, False, pts, 2)

            # Now-marker
            now_h = datetime.datetime.now().hour
            if 0 <= now_h < len(tides):
                nx, ny = _px(now_h, tides[now_h][1])
                pygame.draw.circle(self.surface, config.CYAN, (nx, ny), 5)

            # High/Low markers
            for hl in hilo:
                try:
                    hh = int(hl["time"][:2])
                    if 0 <= hh < len(tides):
                        hx, hy = _px(hh, hl["height"])
                        clr  = config.GOLD if hl["type"] == "H" else config.BLUE
                        lbl  = f"{'H' if hl['type']=='H' else 'L'} {hl['height']:.1f}"
                        pygame.draw.circle(self.surface, clr, (hx, hy), 5)
                        offset = -14 if hl["type"] == "H" else 6
                        self.text(lbl, self._f_tiny, clr, hx, hy + offset, "midtop")
                except Exception:
                    pass

            # X-axis hour labels
            for h_lbl in (0, 6, 12, 18, 23):
                lx, _ = _px(h_lbl, mn)
                self.text(f"{h_lbl:02d}:00", self._f_tiny, config.TEXT_LO,
                          lx, chart_y + chart_h + 2, "midtop")

        else:
            no_msg = ("Tide data unavailable" if not config.NOAA_STATION_ID
                      else "Loading tide data…")
            self.text(no_msg, self._f_small, config.TEXT_LO,
                      self.rect.centerx, chart_y + chart_h // 2, "center")

        ry += chart_h + 22
        pygame.draw.line(self.surface, config.DIVIDER,
                         (self.rect.x + 6, ry - 6),
                         (self.rect.right - 6, ry - 6), 1)

        # ── Hi/Lo tide table ──────────────────────────────────────────────────
        col_x = [rx, rx + rw // 2]
        col_i = 0
        hl_y  = ry

        for hl in hilo[:4]:
            cx2  = col_x[col_i % 2]
            clr  = config.GOLD if hl["type"] == "H" else config.CYAN
            lbl  = "HIGH" if hl["type"] == "H" else "LOW"
            unit = config.NOAA_TIDE_UNIT_LBL
            self.text(f"{lbl}  {hl['time']}", self._f_small, clr,      cx2, hl_y)
            self.text(f"{hl['height']:.2f} {unit}",
                      self._f_tiny, config.TEXT_MID, cx2, hl_y + 15)
            if col_i % 2 == 1:
                hl_y += 36
            col_i += 1

        # ── Swell chart ───────────────────────────────────────────────────────
        # Pin the swell section to the bottom of the widget so it always uses
        # whatever space is left after the tide chart + hi/lo table.
        SWELL_H  = 68    # total height reserved for header + chart
        ry2      = self.rect.bottom - SWELL_H

        pygame.draw.line(self.surface, config.DIVIDER,
                         (self.rect.x + 6, ry2 - 2),
                         (self.rect.right - 6, ry2 - 2), 1)

        sh        = swell.get("height")
        sp        = swell.get("period")
        sd        = swell.get("direction")
        hourly_h  = swell.get("hourly_h") or []

        # Header line: "SWELL"  +  current period  +  direction  +  arrow
        self.text("SWELL", self._f_tiny, config.TEXT_LO, rx, ry2)
        if sh is not None:
            sp_s = f"{sp:.0f}s" if sp is not None else "--"
            sd_s = _dir_label(sd) if sd is not None else "--"
            self.text(f"{sh:.1f}m  {sp_s}  {sd_s}",
                      self._f_tiny, config.BLUE,
                      rx + 46, ry2)
            if sd is not None:
                _draw_arrow(self.surface, self.rect.right - 22, ry2 + 7, 10, sd)

        # Chart geometry — fills the remaining space below the header
        valid = [(i, h) for i, h in enumerate(hourly_h) if h is not None]
        cy0   = ry2 + 16
        cy1   = self.rect.bottom - 14
        ch    = cy1 - cy0
        cw    = rw

        if valid and ch > 8:
            h_min  = 0.0
            h_max  = max(h for _, h in valid)
            span   = max(h_max - h_min, 0.3)

            def _spx(hr, h):
                x = rx + int(hr / 23 * cw)
                y = cy1 - int((h - h_min) / span * (ch - 2)) - 1
                return x, y

            # Background
            pygame.draw.rect(self.surface, (5, 12, 28),
                             pygame.Rect(rx, cy0, cw, ch))

            # Filled area
            poly = [_spx(hr, h) for hr, h in valid]
            poly = [(rx, cy1)] + poly + [(rx + cw, cy1)]
            if len(poly) >= 3:
                pygame.draw.polygon(self.surface, (14, 42, 88), poly)

            # Line
            if len(valid) >= 2:
                pygame.draw.lines(self.surface, config.BLUE, False,
                                  [_spx(hr, h) for hr, h in valid], 2)

            # Now-marker
            now_h = datetime.datetime.now().hour
            cur_h = next((h for hr, h in valid if hr == now_h), None)
            if cur_h is not None:
                nx, ny = _spx(now_h, cur_h)
                pygame.draw.circle(self.surface, config.CYAN, (nx, ny), 4)
                self.text(f"{cur_h:.1f}m", self._f_tiny, config.CYAN,
                          nx, ny - 2, "midbottom")

            # X-axis labels
            for hr_lbl in (0, 6, 12, 18, 23):
                lx = rx + int(hr_lbl / 23 * cw)
                pygame.draw.line(self.surface, config.DIVIDER,
                                 (lx, cy1), (lx, cy1 + 3), 1)
                self.text(f"{hr_lbl:02d}", self._f_tiny, config.TEXT_LO,
                          lx, cy1 + 4, "midtop")

            # Y max label
            self.text(f"{h_max:.1f}m", self._f_tiny, config.TEXT_LO,
                      rx + 2, cy0 + 1)

            # Border
            pygame.draw.rect(self.surface, config.DIVIDER,
                             pygame.Rect(rx, cy0, cw, ch), 1)
        else:
            self.text("Swell data unavailable", self._f_tiny, config.TEXT_LO,
                      rx, ry2 + 14)


# ── Helpers ───────────────────────────────────────────────────────────────────

_COMPASS_16 = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
               "S","SSW","SW","WSW","W","WNW","NW","NNW"]

def _dir_label(deg):
    return _COMPASS_16[round(deg / 22.5) % 16]


def _draw_arrow(surf, cx, cy, r, deg):
    """Draw a compass direction arrow."""
    angle = math.radians(deg - 90)
    tip_x = cx + int(r * math.cos(angle))
    tip_y = cy + int(r * math.sin(angle))
    tail_x = cx - int(r * 0.6 * math.cos(angle))
    tail_y = cy - int(r * 0.6 * math.sin(angle))
    pygame.draw.circle(surf, config.TEXT_LO, (cx, cy), r, 1)
    pygame.draw.line(surf, config.BLUE, (tail_x, tail_y), (tip_x, tip_y), 2)
    pygame.draw.circle(surf, config.BLUE, (tip_x, tip_y), 3)
