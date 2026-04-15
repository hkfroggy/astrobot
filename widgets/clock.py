import pygame
import math
import datetime
import config
from .base import BaseWidget


class ClockWidget(BaseWidget):
    """
    Analog clock with hour/minute/second hands.
    No background thread — reads system time directly in draw().
    """

    def __init__(self, surface, rect):
        super().__init__(surface, rect)
        pygame.font.init()
        self._f_date  = self.make_font(15)
        self._f_small = self.make_font(12)

    # No background thread needed — time is read live in draw()
    def start_data_fetch(self):
        pass

    def fetch_data(self):
        return {}

    def draw(self):
        self.draw_bg()

        now = datetime.datetime.now()
        cx  = self.rect.centerx
        r   = min(self.rect.width, self.rect.height) // 2 - 26
        cy  = self.rect.top + r + 22

        # ── Face ─────────────────────────────────────────────────────────────
        pygame.draw.circle(self.surface, config.CLOCK_BG, (cx, cy), r)
        pygame.draw.circle(self.surface, config.CLOCK_RIM, (cx, cy), r, 2)

        # Tick marks + hour labels
        for i in range(60):
            angle = math.radians(i * 6 - 90)
            if i % 5 == 0:
                r0, r1, w = r - 13, r - 1, 2
                clr = config.TICK_MAJOR
            else:
                r0, r1, w = r - 6,  r - 1, 1
                clr = config.TICK_MINOR
            x0 = cx + int(r0 * math.cos(angle))
            y0 = cy + int(r0 * math.sin(angle))
            x1 = cx + int(r1 * math.cos(angle))
            y1 = cy + int(r1 * math.sin(angle))
            pygame.draw.line(self.surface, clr, (x0, y0), (x1, y1), w)

        for h in range(1, 13):
            a  = math.radians(h * 30 - 90)
            nr = r - 24
            hx = cx + int(nr * math.cos(a))
            hy = cy + int(nr * math.sin(a))
            self.text(str(h), self._f_small, config.TEXT_MID, hx, hy, "center")

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

        # Center cap
        pygame.draw.circle(self.surface, config.HAND_S,  (cx, cy), 5)
        pygame.draw.circle(self.surface, config.TEXT_HI, (cx, cy), 3)

        # ── Date ─────────────────────────────────────────────────────────────
        date_y = cy + r + 10
        self.text(now.strftime("%A, %B %-d"),
                  self._f_date, config.GOLD, cx, date_y, "midtop")
        self.text(now.strftime("%Y"),
                  self._f_small, config.TEXT_MID, cx, date_y + 20, "midtop")
