"""Shared spatial chrome, chosen for BOSIO's RGB332 output palette."""
CHROME = (32, 32, 64)
RAISED = (64, 64, 96)
EDGE = (96, 128, 160)
FOCUS = (128, 224, 192)
TEXT = (250, 250, 249)
SUBTLE = (160, 192, 192)
DANGER = (224, 96, 64)


def orbit_mark(canvas, x, y, radius=18):
    canvas.circle(x, y, radius, EDGE)
    canvas.circle(x, y, radius - 3, CHROME)
    canvas.circle(x, y, 5, FOCUS)
    canvas.rect(x - radius - 4, y - 1, 8, 3, FOCUS)
    canvas.rect(x + radius - 4, y - 1, 8, 3, FOCUS)
