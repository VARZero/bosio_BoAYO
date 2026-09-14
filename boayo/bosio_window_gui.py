#!/usr/bin/env python3
"""
=============================================================================
Bosio Multi-Window Spatial Computing GUI Engine (PYNQ-Z2)
High-Visibility Cockpit & Spatial Avionics UI (Scale 2 & Scale 3 Typography)
=============================================================================
"""

import math
import numpy as np

FACE_SIZE = 512
NUM_FACES = 20

# High-Visibility 5x7 Monospace Font Bitmap
FONT_5X7 = {
    '0': [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    '1': ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    '2': [" ### ", "#   #", "    #", "  ## ", " #   ", "#    ", "#####"],
    '3': ["#####", "   # ", "  #  ", "   # ", "    #", "#   #", " ### "],
    '4': ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    '5': ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    '6': ["  ## ", " #   ", "#    ", "#### ", "#   #", "#   #", " ### "],
    '7': ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    '8': [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    '9': [" ### ", "#   #", "#   #", " ####", "    #", "   # ", " ##  "],
    'A': [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    'B': ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    'C': [" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "],
    'D': ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    'E': ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    'F': ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    'G': [" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ### "],
    'H': ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    'I': [" ### ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    'J': ["  ###", "    #", "    #", "    #", "    #", "#   #", " ### "],
    'K': ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    'L': ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    'M': ["#   #", "## ##", "# # #", "#   #", "#   #", "#   #", "#   #"],
    'N': ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
    'O': [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    'P': ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    'Q': [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    'R': ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    'S': [" ### ", "#   #", "#    ", " ### ", "    #", "#   #", " ### "],
    'T': ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    'U': ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    'V': ["#   #", "#   #", "#   #", "#   #", " # # ", " # # ", "  #  "],
    'W': ["#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"],
    'X': ["#   #", " # # ", "  #  ", "  #  ", " # # ", "#   #", "#   #"],
    'Y': ["#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    'Z': ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    ':': ["     ", "  #  ", "     ", "     ", "  #  ", "     ", "     "],
    '%': ["#   #", "   # ", "  #  ", " #   ", "#   #", "     ", "     "],
    '[': [" ### ", " #   ", " #   ", " #   ", " #   ", " #   ", " ### "],
    ']': [" ### ", "   # ", "   # ", "   # ", "   # ", "   # ", " ### "],
    '-': ["     ", "     ", "     ", " ### ", "     ", "     ", "     "],
    '+': ["     ", "  #  ", "  #  ", "#####", "  #  ", "  #  ", "     "],
    '.': ["     ", "     ", "     ", "     ", "     ", " ##  ", " ##  "],
    '/': ["    #", "   # ", "  #  ", " #   ", "#    ", "     ", "     "],
    '|': ["  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    ' ': ["     ", "     ", "     ", "     ", "     ", "     ", "     "],
}

class BosioWindow:
    def __init__(self, title, az_deg, el_deg, w_deg=28.0, h_deg=17.0, tex_w=320, tex_h=200,
                 theme_color=0x0006B6D4, bg_color=0x000F172A):
        self.title = title
        self.az_deg = az_deg
        self.el_deg = el_deg
        self.w_deg = w_deg
        self.h_deg = h_deg
        self.tex_w = tex_w
        self.tex_h = tex_h
        self.theme_color = theme_color
        self.bg_color = bg_color

        self.canvas = np.full((tex_h, tex_w), bg_color, dtype=np.uint32)
        self.base_canvas = None
        self.lut = None

    def clear(self):
        self.canvas.fill(self.bg_color)

    def draw_pixel(self, x, y, color):
        if 0 <= x < self.tex_w and 0 <= y < self.tex_h:
            self.canvas[y, x] = color

    def draw_rect(self, x, y, w, h, color, fill=True):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.tex_w, x + w)
        y1 = min(self.tex_h, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        if fill:
            self.canvas[y0:y1, x0:x1] = color
        else:
            self.canvas[y0:y1, x0] = color
            self.canvas[y0:y1, x1-1] = color
            self.canvas[y0, x0:x1] = color
            self.canvas[y1-1, x0:x1] = color

    def draw_line(self, x0, y0, x1, y1, color):
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.draw_pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def draw_circle(self, cx, cy, r, color):
        x = r
        y = 0
        err = 0
        while x >= y:
            self.draw_pixel(cx + x, cy + y, color)
            self.draw_pixel(cx + y, cy + x, color)
            self.draw_pixel(cx - y, cy + x, color)
            self.draw_pixel(cx - x, cy + y, color)
            self.draw_pixel(cx - x, cy - y, color)
            self.draw_pixel(cx - y, cy - x, color)
            self.draw_pixel(cx + y, cy - x, color)
            self.draw_pixel(cx + x, cy - y, color)
            y += 1
            err += 1 + 2 * y
            if 2 * (err - x) + 1 > 0:
                x -= 1
                err += 1 - 2 * x

    def draw_text(self, text, start_x, start_y, color, scale=2, bold=True):
        cur_x = start_x
        for char in str(text).upper():
            bitmap = FONT_5X7.get(char, FONT_5X7[' '])
            for row_idx, row in enumerate(bitmap):
                for col_idx, pixel in enumerate(row):
                    if pixel == '#':
                        for sy in range(scale):
                            for sx in range(scale + (1 if bold else 0)):
                                self.draw_pixel(cur_x + col_idx * scale + sx,
                                                start_y + row_idx * scale + sy,
                                                color)
            cur_x += (5 + (2 if bold else 1)) * scale

    def draw_title_bar(self):
        bar_h = 24
        self.draw_rect(0, 0, self.tex_w, bar_h, self.theme_color, fill=True)
        self.draw_text(self.title, 8, 5, 0x00FFFFFF, scale=2, bold=True)
        btn_x = self.tex_w - 22
        self.draw_rect(btn_x, 3, 18, 18, 0x00E11D48, fill=True)
        self.draw_text("X", btn_x + 3, 5, 0x00FFFFFF, scale=2, bold=True)
        self.draw_rect(0, bar_h, self.tex_w, 2, 0x00FFFFFF, fill=True)

    def draw_progress_bar(self, x, y, w, h, ratio, fill_color, label=""):
        ratio = max(0.0, min(1.0, ratio))
        self.draw_rect(x, y, w, h, 0x00334155, fill=True)
        fill_w = int((w - 2) * ratio)
        if fill_w > 0:
            self.draw_rect(x + 1, y + 1, fill_w, h - 2, fill_color, fill=True)
        self.draw_rect(x, y, w, h, self.theme_color, fill=False)
        if label:
            self.draw_text(label, x + w + 8, y - 2, 0x00FFFFFF, scale=2, bold=True)


# =============================================================================
# Fast Base Canvases (Pre-rendered) & Dynamic Updaters
# =============================================================================

def init_all_window_bases(win_pfd, win_radar, win_sys, win_payload):
    """Pre-render static background canvases for all 4 windows (320x200)."""
    # 1. PFD Base
    win_pfd.clear()
    win_pfd.draw_title_bar()
    # Speed box (Left)
    win_pfd.draw_rect(10, 32, 80, 126, 0x001E293B, fill=True)
    win_pfd.draw_rect(10, 32, 80, 126, 0x0038BDF8, fill=False)
    win_pfd.draw_text("IAS", 28, 38, 0x0038BDF8, scale=2, bold=True)
    win_pfd.draw_text("KTS", 28, 130, 0x0094A3B8, scale=2, bold=True)

    # Altitude box (Right)
    win_pfd.draw_rect(win_pfd.tex_w - 90, 32, 80, 126, 0x001E293B, fill=True)
    win_pfd.draw_rect(win_pfd.tex_w - 90, 32, 80, 126, 0x0038BDF8, fill=False)
    win_pfd.draw_text("ALT", win_pfd.tex_w - 74, 38, 0x0038BDF8, scale=2, bold=True)
    win_pfd.draw_text("FT", win_pfd.tex_w - 66, 130, 0x0094A3B8, scale=2, bold=True)

    # Attitude indicator center circle
    cx = win_pfd.tex_w // 2
    cy = 95
    win_pfd.draw_circle(cx, cy, 46, 0x000284C7)
    win_pfd.draw_circle(cx, cy, 45, 0x0038BDF8)
    win_pfd.draw_line(cx - 30, cy, cx + 30, cy, 0x00FACC15)
    win_pfd.draw_line(cx, cy - 10, cx, cy + 10, 0x00FACC15)

    # Bottom status bar
    win_pfd.draw_rect(10, 166, win_pfd.tex_w - 20, 26, 0x001E293B, fill=True)
    win_pfd.draw_rect(10, 166, win_pfd.tex_w - 20, 26, 0x000284C7, fill=False)
    win_pfd.draw_text("HDG 360  MACH .72", 20, 171, 0x004ADE80, scale=2, bold=True)
    win_pfd.base_canvas = win_pfd.canvas.copy()

    # 2. Radar Base
    win_radar.clear()
    win_radar.draw_title_bar()
    rcx, rcy = 80, 105
    win_radar.draw_circle(rcx, rcy, 56, 0x0010B981)
    win_radar.draw_circle(rcx, rcy, 36, 0x00047857)
    win_radar.draw_circle(rcx, rcy, 18, 0x00047857)
    win_radar.draw_line(rcx - 56, rcy, rcx + 56, rcy, 0x00047857)
    win_radar.draw_line(rcx, rcy - 56, rcx, rcy + 56, 0x00047857)

    # Right info panel
    rx = 155
    win_radar.draw_text("RANGE: 40 NM", rx, 36, 0x00FFFFFF, scale=2, bold=True)
    win_radar.draw_text("TRACK: 4 TGT", rx, 62, 0x00F43F5E, scale=2, bold=True)
    win_radar.draw_text("SCAN: 360 DEG", rx, 88, 0x0094A3B8, scale=2, bold=True)
    win_radar.draw_text("MODE: AIR-AIR", rx, 114, 0x004ADE80, scale=2, bold=True)

    # Bottom status bar
    win_radar.draw_rect(10, 166, win_radar.tex_w - 20, 26, 0x00047857, fill=True)
    win_radar.draw_text("RADAR ACTIVE - SCAN", 20, 171, 0x00FFFFFF, scale=2, bold=True)
    win_radar.base_canvas = win_radar.canvas.copy()

    # 3. Sys Base
    win_sys.clear()
    win_sys.draw_title_bar()
    win_sys.draw_text("CPU-0:", 14, 34, 0x00C084FC, scale=2, bold=True)
    win_sys.draw_text("CPU-1:", 14, 78, 0x00C084FC, scale=2, bold=True)

    # DMA info box
    win_sys.draw_rect(212, 32, 96, 82, 0x003B0764, fill=True)
    win_sys.draw_rect(212, 32, 96, 82, 0x00C084FC, fill=False)
    win_sys.draw_text("DMA", 240, 38, 0x00FFFFFF, scale=2, bold=True)
    win_sys.draw_text("720P60", 222, 62, 0x004ADE80, scale=2, bold=True)
    win_sys.draw_text("HP0 ON", 222, 88, 0x00C084FC, scale=2, bold=True)

    win_sys.draw_text("DDR: 20.97 MB (4.1%)", 14, 126, 0x00FFFFFF, scale=2, bold=True)

    win_sys.draw_rect(10, 166, win_sys.tex_w - 20, 26, 0x003B0764, fill=True)
    win_sys.draw_text("STATUS: ALL NOMINAL", 20, 171, 0x004ADE80, scale=2, bold=True)
    win_sys.base_canvas = win_sys.canvas.copy()

    # 4. Payload Base
    win_payload.clear()
    win_payload.draw_title_bar()
    win_payload.draw_text("FREQ: 142.5 MHZ", 14, 34, 0x00F472B6, scale=2, bold=True)

    sx, sy, sw, sh = 14, 58, win_payload.tex_w - 28, 68
    win_payload.draw_rect(sx, sy, sw, sh, 0x000F172A, fill=True)
    win_payload.draw_rect(sx, sy, sw, sh, 0x00475569, fill=False)
    mid_y = sy + sh // 2
    win_payload.draw_line(sx, mid_y, sx + sw, mid_y, 0x00334155)
    for gx in range(sx + 35, sx + sw, 35):
        win_payload.draw_line(gx, sy, gx, sy + sh, 0x001E293B)

    win_payload.draw_text("SIGNAL: OK", 14, 134, 0x00FFFFFF, scale=2, bold=True)
    win_payload.draw_text("SNR: 28 DB", 175, 134, 0x00F472B6, scale=2, bold=True)

    win_payload.draw_rect(10, 166, win_payload.tex_w - 20, 26, 0x00831843, fill=True)
    win_payload.draw_text("SENSOR SUITE ACTIVE", 20, 171, 0x00F472B6, scale=2, bold=True)
    win_payload.base_canvas = win_payload.canvas.copy()


def update_pfd_fast(win, pitch_deg, roll_deg, ias=250, alt=8500):
    """Fast PFD update: horizon bar and giant scale=3 speed/alt numbers."""
    win.canvas[:] = win.base_canvas
    cx = win.tex_w // 2
    cy = 95
    r_rad = math.radians(roll_deg)
    p_offset = int(pitch_deg * 1.5)
    hx = math.cos(r_rad) * 36
    hy = math.sin(r_rad) * 36
    win.draw_line(int(cx - hx), int(cy - hy + p_offset),
                  int(cx + hx), int(cy + hy + p_offset), 0x0038BDF8)
    # Giant scale=3 numbers
    win.draw_text(f"{ias:3d}", 18, 72, 0x00FFFFFF, scale=3, bold=True)
    win.draw_text(f"{alt:4d}", win.tex_w - 87, 72, 0x00FFFFFF, scale=3, bold=True)


def update_radar_fast(win, sweep_deg, targets):
    """Fast Radar update: rotating sweep line & targets."""
    win.canvas[:] = win.base_canvas
    rcx, rcy = 80, 105
    r_outer = 56
    sw_rad = math.radians(sweep_deg)
    sx = rcx + int(math.sin(sw_rad) * r_outer)
    sy = rcy - int(math.cos(sw_rad) * r_outer)
    win.draw_line(rcx, rcy, sx, sy, 0x004ADE80)
    for tx, ty, tlabel in targets:
        px = rcx + tx
        py = rcy + ty
        win.draw_rect(px - 3, py - 3, 7, 7, 0x00F43F5E, fill=True)
        win.draw_text(tlabel, px + 6, py - 6, 0x00FDA4AF, scale=2, bold=True)


def update_sys_fast(win, t_sec):
    """Fast Telemetry update: CPU progress bars with scale=2 percentage labels."""
    win.canvas[:] = win.base_canvas
    cpu0 = 0.35 + 0.15 * math.sin(t_sec * 1.5)
    cpu1 = 0.40 + 0.20 * math.cos(t_sec * 2.0)
    # Percentage labels
    win.draw_text(f"{int(cpu0*100)}%", 95, 34, 0x00FFFFFF, scale=2, bold=True)
    win.draw_text(f"{int(cpu1*100)}%", 95, 78, 0x00FFFFFF, scale=2, bold=True)
    # Progress bars
    win.draw_rect(14, 54, 185, 16, 0x00334155, fill=True)
    fill_0 = int(183 * cpu0)
    if fill_0 > 0: win.draw_rect(15, 55, fill_0, 14, 0x00C084FC, fill=True)
    win.draw_rect(14, 54, 185, 16, win.theme_color, fill=False)

    win.draw_rect(14, 98, 185, 16, 0x00334155, fill=True)
    fill_1 = int(183 * cpu1)
    if fill_1 > 0: win.draw_rect(15, 99, fill_1, 14, 0x00E879F9, fill=True)
    win.draw_rect(14, 98, 185, 16, win.theme_color, fill=False)


def update_payload_fast(win, t_sec):
    """Fast Scope update: real-time animated sinusoidal waveform."""
    win.canvas[:] = win.base_canvas
    sx = 14
    sy = 58
    sw = win.tex_w - 28
    sh = 68
    mid_y = sy + sh // 2
    prev_px = sx
    prev_py = mid_y
    for x_step in range(0, sw, 3):
        cur_px = sx + x_step
        phase = (x_step / 16.0) + t_sec * 4.0
        wave = math.sin(phase) * 20.0 + math.sin(phase * 2.5) * 6.0
        cur_py = int(mid_y + wave)
        cur_py = max(sy + 2, min(sy + sh - 2, cur_py))
        if x_step > 0:
            win.draw_line(prev_px, prev_py, cur_px, cur_py, 0x00F43F5E)
            win.draw_line(prev_px, prev_py + 1, cur_px, cur_py + 1, 0x00F43F5E)
        prev_px = cur_px
        prev_py = cur_py
