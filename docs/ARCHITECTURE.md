# BoAYo desktop shell

BoAYo owns one complete BOSIO scene. BOSIO rotates and scans that finished
scene; it does not draw BoAYo's window captions.

```text
PYNQ buttons + sensor pose
          |
          v
BoAYoShell (gaze, hit testing, internal move/resize/close)
          |
          v
640x360 black canvas (white content + caption controls)
          |
          v
BoayoScene -> existing BOSIO scene packer -> BosioV2 output core
```

The caption order is left resize, close, move, right resize. A gaze-focused
caption grows by 12 percent and brightens. The white rectangular area remains
application content; all surrounding pixels belong to the black BoAYo desktop.

Generate a host-side preview. The default preview reconstructs the 1280x720
view after 20-face/211-tile/MxM triangular-cell sampling and RGB332 palette
quantization. `--preview-source` is only for inspecting the clean source canvas:

```sh
python3 boayo_desktop.py --preview boayo.png
python3 boayo_desktop.py --preview boayo-move.png --preview-focus move
python3 boayo_desktop.py --preview boayo-source.png --preview-source
```

Run on PYNQ-Z2 with the existing BOSIO v2 bitstream and libraries:

```sh
sudo python3 boayo_desktop.py --bitstream /path/to/bosio_v2.bit --m 16
```

BTN0 creates a new execution panel at the current IMU gaze and gives it focus.
Execution panels are auto-hidden when gaze leaves them and reappear when the
gaze returns. BTN1 recreates the launcher at the current gaze. A Linux evdev
mouse supplies an independent spherical pointer: movement changes its gaze
coordinate, the left button clicks, and the wheel scrolls the launcher list.
Commands in `apps.json` are started as child processes; entries without a
working command use the built-in application view.

`libbosio_compositor.so` is not rebuilt or used for BoAYo caption composition.
The existing scene-packing path remains usable unchanged.
