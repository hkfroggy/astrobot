"""
Clock widget — top-left panel (0, 0, 280, 320).

Upper ~230 px  Analog clock face + date
Lower  ~85 px  5-day weather forecast strip (icon · hi · lo)
"""
import pygame
import math
import datetime
import requests
import config
from .base import BaseWidget

try:
    from .weather import _draw_icon, _desc
except Exception:
    def _draw_icon(surf, code, cx, cy, size): pass
    def _desc(code): return ""


class ClockWidget(BaseWidget):

    def __init__(self, surface, rect):
        super().__init__(surface, rect)
        self._refresh_interval = 600    # re-fetch forecast every 10 min
        pygame.font.init()
        self._f_date    = self.make_font(15)
        self._f_small   = self.make_font(12)
        self._f_fc_day  = self.make_font(11)
        self._f_fc_hi   = self.make_font(12)
        self._f_fc_lo   = self.make_font(11)

    # ── Data fetch ────────────────────────────────────────────────────────────

    def fetch_data(self):
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={config.LATITUDE}&longitude={config.LONGITUDE}"
            "&daily=temperature_2m_max,temperature_2m_min,"
            "weathercode,precipitation_probability_max"
            f"&temperature_unit={'fahrenheit' if config.TEMP_UNIT == 'F' else 'celsius'}"
            f"&timezone={config.TIMEZONE}&forecast_days=5"
        )
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self):
        self.draw_bg()
        with self._lock:
            d = dict(self.data)

        now = datetime.datetime.now()
        cx  = self.rect.centerx

        # Clock radius — sized to leave ~80 px for the forecast strip within 300 px
        r  = 78
        cy = self.rect.top + r + 12     # = 90 px from widget top

        # ── Face ─────────────────────────────────────────────────────────────
        pygame.draw.circle(self.surface, config.CLOCK_BG,  (cx, cy), r)
        pygame.draw.circle(self.surface, config.CLOCK_RIM, (cx, cy), r, 2)

        for i in range(60):
            angle = math.radians(i * 6 - 90)
            if i % 5 == 0:
                r0, r1, w = r - 13, r - 1, 2
                clr = config.TICK_MAJOR
            else:
                r0, r1, w = r - 6,  r - 1, 1
                clr = config.TICK_MINOR
            pygame.draw.line(
                self.surface, clr,
                (cx + int(r0 * math.cos(angle)), cy + int(r0 * math.sin(angle))),
                (cx + int(r1 * math.cos(angle)), cy + int(r1 * math.sin(angle))), w,
            )

        f_num = self.make_font(11)
        for h in range(1, 13):
            a  = math.radians(h * 30 - 90)
            nr = r - 22
            self.text(str(h), f_num, config.TEXT_MID,
                      cx + int(nr * math.cos(a)),
                      cy + int(nr * math.sin(a)), "center")

        # ── Hands ─────────────────────────────────────────────────────────────
        h12   = (now.hour % 12) + now.minute / 60 + now.second / 3600
        h_ang = math.radians(h12 * 30 - 90)
        m_ang = math.radians(now.minute * 6 + now.second / 10 - 90)
        s_ang = math.radians(now.second * 6 - 90)

        def hand(angle, length, color, width, tail=0):
            x1 = cx + int(length * math.cos(angle))
            y1 = cy + int(length * math.sin(angle))
            x0 = cx - int(tail  * math.cos(angle))
            y0 = cy - int(tail  * math.sin(angle))
            pygame.draw.line(self.surface, color, (x0, y0), (x1, y1), width)

        hand(h_ang, int(r * 0.54), config.HAND_H, 4, 10)
        hand(m_ang, int(r * 0.80), config.HAND_M, 3,  8)
        hand(s_ang, int(r * 0.86), config.HAND_S, 1, 14)

        pygame.draw.circle(self.surface, config.HAND_S,  (cx, cy), 5)
        pygame.draw.circle(self.surface, config.TEXT_HI, (cx, cy), 3)

        # ── Date ─────────────────────────────────────────────────────────────
        date_y = cy + r + 9              # ≈ 195
        self.text(now.strftime("%A, %B %-d"),
                  self._f_date, config.GOLD, cx, date_y, "midtop")
        self.text(now.strftime("%Y"),
                  self._f_small, config.TEXT_MID, cx, date_y + 20, "midtop")

        # ── 5-day forecast strip ──────────────────────────────────────────────
        strip_y = date_y + 44            # ≈ 239

        pygame.draw.line(self.surface, config.DIVIDER,
                         (self.rect.x + 8, strip_y),
                         (self.rect.right - 8, strip_y), 1)

        if d:
            self._draw_forecast(d, strip_y + 4)

    # ── Forecast strip ────────────────────────────────────────────────────────

    def _draw_forecast(self, data, top_y):
        """
        Draw 5 equal-width columns, each showing:
          day abbreviation · weather icon · hi temp · lo temp
        """
        daily  = data.get("daily", {})
        times  = daily.get("time",               [])
        codes  = daily.get("weathercode",         [])
        hi_arr = daily.get("temperature_2m_max",  [])
        lo_arr = daily.get("temperature_2m_min",  [])
        precip = daily.get("precipitation_probability_max", [])

        n = min(5, len(times))
        if n == 0:
            return

        unit    = "°" if config.TEMP_UNIT == "F" else "°"
        col_w   = self.rect.width // 5      # 56 px per column

        # Vertical offsets within each column (relative to top_y)
        DAY_OFF  =  2    # day abbreviation
        ICON_CY  = 20    # icon centre
        HI_OFF   = 40    # hi temperature
        LO_OFF   = 54    # lo temperature

        for i in range(n):
            col_cx = self.rect.x + i * col_w + col_w // 2

            # Thin vertical separator between days (not before first)
            if i > 0:
                pygame.draw.line(self.surface, config.DIVIDER,
                                 (self.rect.x + i * col_w, top_y),
                                 (self.rect.x + i * col_w, self.rect.bottom - 4), 1)

            # Day name
            try:
                dt  = datetime.date.fromisoformat(times[i])
                lbl = "Today" if i == 0 else dt.strftime("%a")
            except Exception:
                lbl = f"D{i}"
            day_clr = config.GOLD if i == 0 else config.TEXT_MID
            self.text(lbl, self._f_fc_day, day_clr, col_cx, top_y + DAY_OFF, "midtop")

            # Weather icon (28 × 28 px)
            code = codes[i] if i < len(codes) else 0
            _draw_icon(self.surface, code, col_cx, top_y + ICON_CY, 28)

            # Hi temperature
            hi = hi_arr[i] if i < len(hi_arr) else None
            if hi is not None:
                hi_s = f"{round(hi)}{unit}"
                self.text(hi_s, self._f_fc_hi, (255, 185, 80),
                          col_cx, top_y + HI_OFF, "midtop")

            # Lo temperature
            lo = lo_arr[i] if i < len(lo_arr) else None
            if lo is not None:
                lo_s = f"{round(lo)}{unit}"
                self.text(lo_s, self._f_fc_lo, config.TEXT_MID,
                          col_cx, top_y + LO_OFF, "midtop")

            # Rain probability badge — only if ≥ 30 %
            pr = precip[i] if i < len(precip) else None
            if pr is not None and pr >= 30:
                self.text(f"{int(pr)}%", self._f_fc_lo, config.BLUE,
                          col_cx, top_y + LO_OFF + 13, "midtop")
