"""
Settings overlay — two-page modal popup.

Page 1 · Location search (Open-Meteo geocoding) + °F/°C toggle
Page 2 · DSO filters: magnitude range, field-of-view range, shooting window
"""
import pygame
import threading
import json
import math
import re
import requests
from pathlib import Path
import config

_SETTINGS_FILE = Path(__file__).parent / "settings.json"

# ── Persistence ───────────────────────────────────────────────────────────────

def load_settings() -> dict:
    if _SETTINGS_FILE.exists():
        try:
            return json.loads(_SETTINGS_FILE.read_text())
        except Exception:
            pass
    return {}


def save_settings(d: dict):
    _SETTINGS_FILE.write_text(json.dumps(d, indent=2))


def apply_to_config(d: dict):
    if "latitude"        in d: config.LATITUDE        = float(d["latitude"])
    if "longitude"       in d: config.LONGITUDE       = float(d["longitude"])
    if "timezone"        in d: config.TIMEZONE        = d["timezone"]
    if "location_name"   in d: config.LOCATION_NAME   = d["location_name"]
    if "temp_unit"       in d: config.TEMP_UNIT       = d["temp_unit"]
    if "dso_mag_min"     in d: config.DSO_MAG_MIN     = float(d["dso_mag_min"])
    if "dso_mag_max"     in d: config.DSO_MAG_MAX     = float(d["dso_mag_max"])
    if "dso_fov_min"     in d: config.DSO_FOV_MIN     = float(d["dso_fov_min"])
    if "dso_fov_max"     in d: config.DSO_FOV_MAX     = float(d["dso_fov_max"])
    if "dso_shoot_start" in d: config.DSO_SHOOT_START = float(d["dso_shoot_start"])
    if "dso_shoot_end"   in d: config.DSO_SHOOT_END   = float(d["dso_shoot_end"])


# ── Geocoding ─────────────────────────────────────────────────────────────────

def geocode_search(query: str) -> list:
    url = (
        "https://geocoding-api.open-meteo.com/v1/search"
        f"?name={requests.utils.quote(query.strip())}"
        "&count=8&language=en&format=json"
    )
    r = requests.get(url, timeout=8)
    r.raise_for_status()
    return r.json().get("results", [])


# ── Palette ───────────────────────────────────────────────────────────────────
_C = {
    "bg":       ( 12,  17,  36),
    "panel":    ( 18,  26,  50),
    "border":   ( 38,  58, 105),
    "border_a": ( 62, 140, 255),
    "hi":       (225, 235, 255),
    "mid":      (145, 165, 210),
    "lo":       ( 72,  95, 142),
    "gold":     (255, 205,  60),
    "blue":     ( 62, 140, 255),
    "green":    ( 72, 212, 112),
    "sel":      ( 22,  48,  98),
    "hover":    ( 16,  32,  66),
    "close":    (200, 100,  90),
    "tab_a":    ( 22,  38,  80),   # active tab bg
    "tab_i":    ( 14,  21,  44),   # inactive tab bg
    "sec":      ( 50,  72, 130),   # section header text
}

def _rr(surf, color, rect, r=6, w=0):
    pygame.draw.rect(surf, color, rect, w, border_radius=r)

def _mk_font(size):
    path = pygame.font.match_font("dejavusans,freesans,liberationsans,arial,sans")
    return pygame.font.Font(path, size)


# ── Popup geometry ────────────────────────────────────────────────────────────
_POP_W = 640
_POP_H = 460

_Y_TITLE  =  0     # title bar top
_Y_TABS   = 42     # tab row top
_TAB_H    = 30     # tab row height
_Y_CONT   = 72     # content area top (below tabs)

# Page 1 y-positions (content-relative, i.e. from _Y_CONT)
_P1 = dict(
    loc_lbl  =  8,
    search   = 26,
    list_top = 68,
    list_h   = 148,   # 4.8 rows × 31 px
    sel      = 224,
    div1     = 242,
    unit_lbl = 252,
    unit_btn = 270,
    div2     = 310,
    btns     = 320,
)

# Page 2 y-positions (content-relative)
_P2 = dict(
    mag_hdr  =   6,
    mag_min  =  28,
    mag_max  =  66,
    fov_hdr  = 110,
    fov_min  = 132,
    fov_max  = 170,
    win_hdr  = 214,
    win_start= 238,
    win_end  = 280,
    hint     = 322,
    btns     = 320,
)

_BTNS_Y = _Y_CONT + 320   # shared button row y
_SLIDER_W = _POP_W - 32   # 16 margin each side


# ── Slider widget ─────────────────────────────────────────────────────────────

class _Slider:
    """Horizontal slider — all coordinates popup-relative."""
    LBL_W = 70
    VAL_W = 68
    TK_H  =  4   # track height
    TH_R  =  8   # thumb radius

    def __init__(self, label, x, y, width, min_v, max_v, value,
                 fmt="{:.1f}", suffix="", step=None):
        self.label  = label
        self.x      = x
        self.y      = y
        self.width  = width
        self.min_v  = float(min_v)
        self.max_v  = float(max_v)
        self.value  = float(value)
        self.fmt    = fmt
        self.suffix = suffix
        self.step   = step

    @property
    def _track_x(self): return self.x + self.LBL_W
    @property
    def _track_w(self): return self.width - self.LBL_W - self.VAL_W - 8
    @property
    def _track_y(self): return self.y + 14

    def _thumb_cx(self):
        span = max(self.max_v - self.min_v, 1e-9)
        frac = (self.value - self.min_v) / span
        return self._track_x + int(frac * self._track_w)

    def _frac_to_val(self, rx):
        frac = max(0.0, min(1.0, (rx - self._track_x) / self._track_w))
        v = self.min_v + frac * (self.max_v - self.min_v)
        if self.step:
            v = round(v / self.step) * self.step
        return max(self.min_v, min(self.max_v, v))

    def hit_thumb(self, rx, ry):
        dx = rx - self._thumb_cx()
        dy = ry - (self._track_y + self.TK_H // 2)
        return dx * dx + dy * dy <= (self.TH_R + 5) ** 2

    def hit_track(self, rx, ry):
        return (self._track_x <= rx <= self._track_x + self._track_w and
                self._track_y - 12 <= ry <= self._track_y + self.TK_H + 12)

    def set_from_x(self, rx):
        self.value = self._frac_to_val(rx)

    def draw(self, surf, pr: pygame.Rect, fonts: dict):
        ax = pr.x + self.x
        ay = pr.y + self.y
        tx = pr.x + self._track_x
        ty = pr.y + self._track_y

        # Label
        surf.blit(fonts["small"].render(self.label, True, _C["mid"]), (ax, ay + 8))

        # Track bg
        pygame.draw.rect(surf, (20, 30, 58),
                         pygame.Rect(tx, ty, self._track_w, self.TK_H), border_radius=2)
        # Filled
        span = max(self.max_v - self.min_v, 1e-9)
        fw = max(0, int((self.value - self.min_v) / span * self._track_w))
        if fw:
            pygame.draw.rect(surf, _C["blue"],
                             pygame.Rect(tx, ty, fw, self.TK_H), border_radius=2)

        # Thumb
        tcx = pr.x + self._thumb_cx()
        tcy = ty + self.TK_H // 2
        pygame.draw.circle(surf, _C["border_a"], (tcx, tcy), self.TH_R + 2)
        pygame.draw.circle(surf, _C["hi"],       (tcx, tcy), self.TH_R - 1)

        # Value
        val_s = self.fmt.format(self.value) + self.suffix
        vs = fonts["small"].render(val_s, True, _C["hi"])
        surf.blit(vs, (tx + self._track_w + 10, ay + 8))


# ── Time stepper widget ───────────────────────────────────────────────────────

class _TimeStepper:
    """Label + [−] HH:MM [+] row — popup-relative coordinates."""
    BTN_W = 32
    BTN_H = 28
    DSP_W = 72

    def __init__(self, label, x, y, value_h: float, step: float = 0.5):
        self.label  = label
        self.x      = x
        self.y      = y
        self.value  = float(value_h)   # decimal hours 0-23
        self.step   = step

    def _minus_rect(self): return pygame.Rect(self.x + 74, self.y + 4, self.BTN_W, self.BTN_H)
    def _dsp_rect(self):   return pygame.Rect(self.x + 74 + self.BTN_W + 6, self.y + 4, self.DSP_W, self.BTN_H)
    def _plus_rect(self):  return pygame.Rect(self.x + 74 + self.BTN_W + 6 + self.DSP_W + 6, self.y + 4, self.BTN_W, self.BTN_H)

    def hit_minus(self, rx, ry): return self._minus_rect().collidepoint(rx, ry)
    def hit_plus(self,  rx, ry): return self._plus_rect().collidepoint(rx, ry)

    def decrement(self): self.value = (self.value - self.step) % 24
    def increment(self): self.value = (self.value + self.step) % 24

    def time_str(self):
        h = int(self.value) % 24
        m = round((self.value - int(self.value)) * 60)
        return f"{h:02d}:{m:02d}"

    def draw(self, surf, pr: pygame.Rect, fonts: dict):
        ay = pr.y + self.y
        ax = pr.x + self.x
        # Label
        surf.blit(fonts["small"].render(self.label, True, _C["mid"]), (ax, ay + 10))

        for rect_fn, lbl, clr in (
            (self._minus_rect, "−", _C["hi"]),
            (self._plus_rect,  "+", _C["hi"]),
        ):
            r = rect_fn()
            ar = pygame.Rect(pr.x + r.x, pr.y + r.y, r.w, r.h)
            _rr(surf, _C["panel"],  ar, 4)
            _rr(surf, _C["border"], ar, 4, 1)
            s = fonts["btn"].render(lbl, True, clr)
            surf.blit(s, s.get_rect(center=ar.center))

        dr = self._dsp_rect()
        adr = pygame.Rect(pr.x + dr.x, pr.y + dr.y, dr.w, dr.h)
        _rr(surf, (16, 24, 48), adr, 4)
        _rr(surf, _C["border"], adr, 4, 1)
        ts = fonts["btn"].render(self.time_str(), True, _C["gold"])
        surf.blit(ts, ts.get_rect(center=adr.center))


# ── Gear button ───────────────────────────────────────────────────────────────

def draw_gear_button(surf, rect, hovered=False):
    cx, cy = rect.centerx, rect.centery
    r_btn  = rect.width // 2
    bg_clr = (30, 44, 80) if hovered else (18, 26, 50)
    pygame.draw.circle(surf, bg_clr, (cx, cy), r_btn)
    pygame.draw.circle(surf, _C["border"], (cx, cy), r_btn, 1)
    clr = _C["hi"] if hovered else _C["mid"]
    gr  = r_btn - 6
    for i in range(8):
        a  = math.radians(i * 45)
        x0 = cx + int((gr - 3) * math.cos(a))
        y0 = cy + int((gr - 3) * math.sin(a))
        x1 = cx + int((gr + 3) * math.cos(a))
        y1 = cy + int((gr + 3) * math.sin(a))
        pygame.draw.line(surf, clr, (x0, y0), (x1, y1), 3)
    pygame.draw.circle(surf, clr, (cx, cy), gr - 2, 2)
    pygame.draw.circle(surf, clr, (cx, cy), gr // 3, 2)


# ── Settings overlay ──────────────────────────────────────────────────────────

_LIST_VISIBLE = _P1["list_h"] // 31


class SettingsOverlay:
    """
    Two-page modal settings popup.
    Call handle_event(event) → None | "saved" | "cancelled"
    Call draw() every frame.
    """

    def __init__(self, screen):
        self.screen = screen
        self._open  = False
        self._page  = 1        # 1 = Location/Units,  2 = DSO Filters
        self._fonts: dict = {}

        # Page 1 state
        self._query        = ""
        self._results      = []
        self._selected     = None
        self._temp_unit    = "F"
        self._focused      = False
        self._searching    = False
        self._search_err   = ""
        self._list_hover   = -1
        self._scroll       = 0
        self._cursor_tick  = 0
        self._search_timer = None

        # Page 2 state – sliders & steppers created lazily in open()
        self._sliders:  list[_Slider]      = []
        self._steppers: list[_TimeStepper] = []
        self._drag_slider: "_Slider | None" = None

    # ── Public ────────────────────────────────────────────────────────────────

    def open(self):
        self._init_fonts()
        self._open       = True
        self._page       = 1
        self._drag_slider = None

        # Page 1
        self._query      = config.LOCATION_NAME
        self._results    = []
        self._scroll     = 0
        self._focused    = False
        self._searching  = False
        self._search_err = ""
        self._temp_unit  = getattr(config, "TEMP_UNIT", "F")
        self._selected   = {
            "latitude":  config.LATITUDE,
            "longitude": config.LONGITUDE,
            "timezone":  config.TIMEZONE,
            "display":   config.LOCATION_NAME,
        }

        # Page 2 – rebuild sliders/steppers from current config values
        cx = _Y_CONT  # content y-offset added inside _abs()
        sx = 16       # slider x (inside popup)
        sw = _SLIDER_W

        self._sliders = [
            _Slider("Mag min",  sx, _Y_CONT + _P2["mag_min"], sw,
                    0.0, 8.0, getattr(config, "DSO_MAG_MIN", 0.0),
                    fmt="{:.1f}", step=0.5),
            _Slider("Mag max",  sx, _Y_CONT + _P2["mag_max"], sw,
                    4.0, 15.0, getattr(config, "DSO_MAG_MAX", 12.0),
                    fmt="{:.1f}", step=0.5),
            _Slider("FoV min°", sx, _Y_CONT + _P2["fov_min"], sw,
                    0.05, 2.0, getattr(config, "DSO_FOV_MIN", 0.05),
                    fmt="{:.2f}", suffix="°", step=0.05),
            _Slider("FoV max°", sx, _Y_CONT + _P2["fov_max"], sw,
                    0.5, 6.0, getattr(config, "DSO_FOV_MAX", 5.0),
                    fmt="{:.1f}", suffix="°", step=0.25),
        ]
        self._steppers = [
            _TimeStepper("Start", sx, _Y_CONT + _P2["win_start"],
                         getattr(config, "DSO_SHOOT_START", 20.0), step=0.5),
            _TimeStepper("End",   sx, _Y_CONT + _P2["win_end"],
                         getattr(config, "DSO_SHOOT_END",   5.0),  step=0.5),
        ]

    @property
    def is_open(self): return self._open

    # ── Event handling ────────────────────────────────────────────────────────

    def handle_event(self, event) -> "str | None":
        if not self._open:
            return None
        pr = self._popup_rect()

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag_slider = None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if not pr.collidepoint(mx, my):
                return self._close("cancelled")
            rx, ry = mx - pr.x, my - pr.y
            return self._handle_click(rx, ry)

        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            rx = mx - pr.x
            ry = my - pr.y
            if self._drag_slider is not None:
                self._drag_slider.set_from_x(rx)
            elif pr.collidepoint(mx, my) and self._page == 1:
                lr = self._list_rel()
                if lr.collidepoint(rx, ry):
                    self._list_hover = (ry - lr.y) // 31 + self._scroll
                else:
                    self._list_hover = -1

        elif event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if pr.collidepoint(mx, my):
                if self._page == 1:
                    lr = self._list_rel()
                    rx, ry = mx - pr.x, my - pr.y
                    if lr.collidepoint(rx, ry):
                        self._scroll = max(0, min(
                            max(0, len(self._results) - _LIST_VISIBLE),
                            self._scroll - event.y
                        ))

        elif event.type == pygame.KEYDOWN:
            if self._page == 1 and self._focused:
                if event.key == pygame.K_ESCAPE:
                    return self._close("cancelled")
                elif event.key == pygame.K_RETURN:
                    self._kick_search()
                elif event.key == pygame.K_BACKSPACE:
                    self._query = self._query[:-1]
                    self._schedule_search()
                elif event.unicode and event.unicode.isprintable():
                    self._query += event.unicode
                    self._schedule_search()
            else:
                if event.key == pygame.K_ESCAPE:
                    return self._close("cancelled")

        return None

    def _handle_click(self, rx, ry) -> "str | None":
        # Close ×
        if self._close_rect().collidepoint(rx, ry):
            return self._close("cancelled")

        # Tab buttons
        if self._tab_rect(1).collidepoint(rx, ry):
            self._page = 1; return None
        if self._tab_rect(2).collidepoint(rx, ry):
            self._page = 2; return None

        # Shared buttons
        if self._cancel_btn_rect().collidepoint(rx, ry):
            return self._close("cancelled")
        if self._save_btn_rect().collidepoint(rx, ry):
            return self._save()

        # ── Page 1 ────────────────────────────────────────────────────────────
        if self._page == 1:
            if self._input_rect().collidepoint(rx, ry):
                self._focused = True; return None
            else:
                self._focused = False
            if self._search_btn_rect().collidepoint(rx, ry):
                self._kick_search(); return None
            lr = self._list_rel()
            if lr.collidepoint(rx, ry):
                idx = (ry - lr.y) // 31 + self._scroll
                if 0 <= idx < len(self._results):
                    item = self._results[idx]
                    self._selected = {**item, "display": self._item_label(item)}
                    self._query    = self._item_label(item)
                return None
            if self._unit_btn_rect("F").collidepoint(rx, ry):
                self._temp_unit = "F"; return None
            if self._unit_btn_rect("C").collidepoint(rx, ry):
                self._temp_unit = "C"; return None

        # ── Page 2 ────────────────────────────────────────────────────────────
        elif self._page == 2:
            # Slider thumb/track
            for sl in self._sliders:
                if sl.hit_thumb(rx, ry) or sl.hit_track(rx, ry):
                    sl.set_from_x(rx)
                    self._drag_slider = sl
                    return None
            # Time stepper buttons
            for st in self._steppers:
                if st.hit_minus(rx, ry): st.decrement(); return None
                if st.hit_plus(rx, ry):  st.increment(); return None

        return None

    # ── Drawing ───────────────────────────────────────────────────────────────

    def draw(self):
        if not self._open:
            return
        self._init_fonts()
        self._cursor_tick += 1

        sw, sh = self.screen.get_size()
        # Backdrop
        dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 155))
        self.screen.blit(dim, (0, 0))

        pr = self._popup_rect()
        _rr(self.screen, _C["bg"],     pr, 10)
        _rr(self.screen, _C["border"], pr, 10, 2)

        # Title bar
        _rr(self.screen, _C["panel"], pygame.Rect(pr.x, pr.y, _POP_W, _Y_TABS), 10)
        pygame.draw.line(self.screen, _C["border"],
                         (pr.x, pr.y + _Y_TABS), (pr.x + _POP_W, pr.y + _Y_TABS), 1)
        self._txt("Settings", "title", _C["hi"], pr.x + 18, pr.y + 11)

        # Close ×
        xr = self._close_rect()
        ax, ay = pr.x + xr.x, pr.y + xr.y
        hw = xr.width // 2
        pygame.draw.line(self.screen, _C["close"],
                         (ax, ay), (ax + xr.w, ay + xr.h), 2)
        pygame.draw.line(self.screen, _C["close"],
                         (ax + xr.w, ay), (ax, ay + xr.h), 2)

        # Tab buttons
        for n, label in ((1, "  Location & Units"), (2, "  DSO Filters")):
            tr_rel = self._tab_rect(n)
            tr     = pygame.Rect(pr.x + tr_rel.x, pr.y + tr_rel.y, tr_rel.w, tr_rel.h)
            active = (self._page == n)
            _rr(self.screen, _C["tab_a"] if active else _C["tab_i"], tr, 0)
            pygame.draw.line(self.screen, _C["border_a"] if active else _C["border"],
                             (tr.x, tr.bottom), (tr.right, tr.bottom), 2 if active else 1)
            self._txt(label, "label", _C["hi"] if active else _C["mid"],
                      tr.centerx, tr.centery, "center")

        if self._page == 1:
            self._draw_page1(pr)
        else:
            self._draw_page2(pr)

        # ── Shared action buttons ─────────────────────────────────────────────
        pygame.draw.line(self.screen, _C["border"],
                         (pr.x + 14, pr.y + _BTNS_Y - 8),
                         (pr.x + _POP_W - 14, pr.y + _BTNS_Y - 8), 1)
        for label, rect_fn, bg, fg in (
            ("Cancel", self._cancel_btn_rect, _C["panel"], _C["mid"]),
            ("Save",   self._save_btn_rect,   _C["blue"],  _C["hi"]),
        ):
            br  = rect_fn()
            abr = pygame.Rect(pr.x + br.x, pr.y + br.y, br.w, br.h)
            _rr(self.screen, bg,          abr, 6)
            _rr(self.screen, _C["border"], abr, 6, 1)
            ls = self._fonts["btn"].render(label, True, fg)
            self.screen.blit(ls, ls.get_rect(center=abr.center))

    def _draw_page1(self, pr: pygame.Rect):
        oc = _Y_CONT  # offset for content area

        self._txt("Location", "label", _C["mid"],
                  pr.x + 18, pr.y + oc + _P1["loc_lbl"])

        # Search input
        inp     = self._input_rect()
        inp_abs = pygame.Rect(pr.x + inp.x, pr.y + inp.y, inp.w, inp.h)
        bdr     = _C["border_a"] if self._focused else _C["border"]
        _rr(self.screen, (16, 24, 48), inp_abs, 5)
        _rr(self.screen, bdr,          inp_abs, 5, 2)
        disp = self._query or "Search for a city…"
        clr  = _C["hi"] if self._query else _C["lo"]
        ts   = self._fonts["input"].render(disp, True, clr)
        clip_w = inp_abs.width - 16
        if ts.get_width() > clip_w:
            ts = ts.subsurface(pygame.Rect(ts.get_width() - clip_w, 0, clip_w, ts.get_height()))
        self.screen.blit(ts, (inp_abs.x + 8, inp_abs.centery - ts.get_height() // 2))
        if self._focused and (self._cursor_tick // 28) % 2 == 0:
            tw  = min(self._fonts["input"].size(self._query)[0], clip_w)
            cx2 = inp_abs.x + 8 + tw
            pygame.draw.line(self.screen, _C["hi"],
                             (cx2, inp_abs.y + 6), (cx2, inp_abs.bottom - 6), 1)

        # Search button
        sbtn = self._search_btn_rect()
        sbtn_abs = pygame.Rect(pr.x + sbtn.x, pr.y + sbtn.y, sbtn.w, sbtn.h)
        _rr(self.screen, (40, 90, 170) if self._searching else _C["blue"], sbtn_abs, 5)
        sl = self._fonts["btn"].render("…" if self._searching else "Search", True, _C["hi"])
        self.screen.blit(sl, sl.get_rect(center=sbtn_abs.center))

        # Results list
        lr     = self._list_rel()
        lr_abs = pygame.Rect(pr.x + lr.x, pr.y + lr.y, lr.w, lr.h)
        _rr(self.screen, _C["panel"],  lr_abs, 5)
        _rr(self.screen, _C["border"], lr_abs, 5, 1)
        for i in range(_LIST_VISIBLE):
            idx = i + self._scroll
            if idx >= len(self._results): break
            item  = self._results[idx]
            iy    = lr_abs.y + i * 31
            ir    = pygame.Rect(lr_abs.x + 1, iy + 1, lr_abs.w - 2, 30)
            is_sel = (self._selected and
                      round(item.get("latitude", 0), 4) ==
                      round(self._selected.get("latitude", 0), 4))
            if is_sel:
                _rr(self.screen, _C["sel"],   ir, 3)
            elif idx == self._list_hover:
                _rr(self.screen, _C["hover"], ir, 3)
            self._txt(self._item_label(item), "item", _C["hi"],
                      ir.x + 10, ir.centery - 7)
        if not self._results:
            msg = (self._search_err or
                   ("Searching…" if self._searching
                    else "Enter a city name and press Search"))
            self._txt(msg, "small", _C["lo"],
                      lr_abs.centerx, lr_abs.centery - 7, anchor="midtop")
        # Scroll indicator
        if len(self._results) > _LIST_VISIBLE:
            total = len(self._results)
            sb_h  = max(20, int(lr_abs.height * _LIST_VISIBLE / total))
            sb_y  = lr_abs.y + int(lr_abs.height * self._scroll / total)
            pygame.draw.rect(self.screen, _C["border"],
                             pygame.Rect(lr_abs.right - 5, sb_y, 4, sb_h), border_radius=2)

        # Selected
        if self._selected:
            self._txt(f"✓  {self._selected.get('display', '')}", "small", _C["gold"],
                      pr.x + 18, pr.y + oc + _P1["sel"])

        # Divider + unit
        pygame.draw.line(self.screen, _C["border"],
                         (pr.x + 14, pr.y + oc + _P1["div1"]),
                         (pr.x + _POP_W - 14, pr.y + oc + _P1["div1"]), 1)
        self._txt("Temperature Unit", "label", _C["mid"],
                  pr.x + 18, pr.y + oc + _P1["unit_lbl"])
        for unit in ("F", "C"):
            br    = self._unit_btn_rect(unit)
            br_abs = pygame.Rect(pr.x + br.x, pr.y + br.y, br.w, br.h)
            act   = (self._temp_unit == unit)
            _rr(self.screen, _C["blue"] if act else _C["panel"], br_abs, 6)
            _rr(self.screen, _C["border_a"] if act else _C["border"], br_abs, 6, 2)
            ul = self._fonts["btn"].render(f"°{unit}", True,
                                           _C["hi"] if act else _C["mid"])
            self.screen.blit(ul, ul.get_rect(center=br_abs.center))

    def _draw_page2(self, pr: pygame.Rect):
        oc = _Y_CONT

        # ── Magnitude section ─────────────────────────────────────────────────
        self._section_header(pr, oc + _P2["mag_hdr"], "Magnitude",
                             "(lower number = brighter)")
        for sl in self._sliders[:2]:
            sl.draw(self.screen, pr, self._fonts)

        # ── Field of View section ─────────────────────────────────────────────
        self._section_header(pr, oc + _P2["fov_hdr"], "Field of View",
                             "(degrees  —  small objects → large nebulae)")
        for sl in self._sliders[2:]:
            sl.draw(self.screen, pr, self._fonts)

        # ── Shooting Window section ───────────────────────────────────────────
        self._section_header(pr, oc + _P2["win_hdr"], "Shooting Window",
                             "(objects transiting in this range are prioritised)")
        for st in self._steppers:
            st.draw(self.screen, pr, self._fonts)

        # Step hint
        hint_y = pr.y + oc + _P2["hint"]
        self._txt("Tap  −  /  +  to step by 30 minutes",
                  "small", _C["lo"], pr.x + 16, hint_y)
        # Range summary line
        s_str = self._steppers[0].time_str()
        e_str = self._steppers[1].time_str()
        mag_lo = self._sliders[0].value
        mag_hi = self._sliders[1].value
        fov_lo = self._sliders[2].value
        fov_hi = self._sliders[3].value
        summary = (f"Mag {mag_lo:.1f}–{mag_hi:.1f}  ·  "
                   f"FoV {fov_lo:.2f}°–{fov_hi:.1f}°  ·  "
                   f"{s_str}–{e_str}")
        self._txt(summary, "small", _C["gold"],
                  pr.x + _POP_W - 16, hint_y + 16, anchor="topright")

    def _section_header(self, pr, rel_y, title, subtitle=""):
        ay = pr.y + rel_y
        pygame.draw.line(self.screen, _C["border"],
                         (pr.x + 14, ay - 2), (pr.x + _POP_W - 14, ay - 2), 1)
        self._txt(title,    "label", _C["gold"],  pr.x + 16, ay + 2)
        if subtitle:
            self._txt(subtitle, "small", _C["lo"], pr.x + 16 + self._fonts["label"].size(title)[0] + 10, ay + 4)

    # ── Geometry (all popup-relative) ─────────────────────────────────────────

    def _popup_rect(self):
        sw, sh = self.screen.get_size()
        return pygame.Rect((sw - _POP_W) // 2, (sh - _POP_H) // 2, _POP_W, _POP_H)

    def _tab_rect(self, n):  # n = 1 or 2
        return pygame.Rect((n - 1) * _POP_W // 2, _Y_TABS, _POP_W // 2, _TAB_H)

    def _close_rect(self):
        return pygame.Rect(_POP_W - 34, 12, 18, 18)

    # Page 1
    def _input_rect(self):
        return pygame.Rect(16, _Y_CONT + _P1["search"], _POP_W - 120, 36)

    def _search_btn_rect(self):
        return pygame.Rect(_POP_W - 98, _Y_CONT + _P1["search"], 82, 36)

    def _list_rel(self):
        return pygame.Rect(16, _Y_CONT + _P1["list_top"],
                           _POP_W - 32, _P1["list_h"])

    def _unit_btn_rect(self, unit):
        x = 160 + (0 if unit == "F" else 66)
        return pygame.Rect(x, _Y_CONT + _P1["unit_btn"], 56, 32)

    # Shared
    def _cancel_btn_rect(self):
        return pygame.Rect(16, _BTNS_Y, 115, 38)

    def _save_btn_rect(self):
        return pygame.Rect(_POP_W - 131, _BTNS_Y, 115, 38)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _init_fonts(self):
        if self._fonts: return
        self._fonts = {
            "title": _mk_font(19),
            "label": _mk_font(14),
            "input": _mk_font(15),
            "item":  _mk_font(14),
            "btn":   _mk_font(15),
            "small": _mk_font(12),
        }

    def _txt(self, text, key, color, x, y, anchor="topleft"):
        surf = self._fonts[key].render(str(text), True, color)
        r    = surf.get_rect(**{anchor: (x, y)})
        self.screen.blit(surf, r)

    def _item_label(self, item):
        parts = [item.get("name", "")]
        if item.get("admin1"):  parts.append(item["admin1"])
        if item.get("country"): parts.append(item["country"])
        return ", ".join(p for p in parts if p)

    def _schedule_search(self):
        if self._search_timer: self._search_timer.cancel()
        t = threading.Timer(0.55, self._kick_search)
        t.daemon = True; t.start()
        self._search_timer = t

    def _kick_search(self):
        q = self._query.strip()
        if not q: return
        self._searching  = True
        self._search_err = ""
        self._results    = []
        self._scroll     = 0
        threading.Thread(target=self._search_worker, args=(q,), daemon=True).start()

    def _search_worker(self, q):
        try:
            res = geocode_search(q)
            self._results   = res
            self._searching = False
            if not res: self._search_err = "No results found"
        except Exception as e:
            self._searching  = False
            self._search_err = f"Error: {e}"

    def _save(self):
        if not self._selected:
            return None
        d = {
            "latitude":        self._selected.get("latitude",  config.LATITUDE),
            "longitude":       self._selected.get("longitude", config.LONGITUDE),
            "timezone":        self._selected.get("timezone",  config.TIMEZONE),
            "location_name":   self._selected.get("display",   config.LOCATION_NAME),
            "temp_unit":       self._temp_unit,
            "dso_mag_min":     self._sliders[0].value,
            "dso_mag_max":     self._sliders[1].value,
            "dso_fov_min":     self._sliders[2].value,
            "dso_fov_max":     self._sliders[3].value,
            "dso_shoot_start": self._steppers[0].value,
            "dso_shoot_end":   self._steppers[1].value,
        }
        save_settings(d)
        apply_to_config(d)
        return self._close("saved")

    def _close(self, reason):
        self._open = False
        if self._search_timer:
            self._search_timer.cancel()
            self._search_timer = None
        return reason
