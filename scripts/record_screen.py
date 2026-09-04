#!/usr/bin/env python3
"""
Sightline - screen recorder for demo-day backup captures.

WHY THIS EXISTS (do not replace it with ffmpeg):
  This laptop runs GNOME on Wayland. Gazebo and RViz are X11 clients rendered
  through XWayland, and their surfaces are composited by the Wayland compositor -
  they never appear in the X root window. Verified 2026-09-05: recording with
  `ffmpeg -f x11grab -i :0` while a GL client was on screen produced a frame with
  mean pixel value 0.01 and std 1.04, i.e. an empty black screen, with no error.
  x11grab CANNOT capture this desktop. Neither can wf-recorder (wlroots only).

  GNOME's own org.gnome.Shell.Screencast D-Bus API does work, but there is a trap:
  the recording is bound to the D-Bus *sender*. Calling it with `gdbus call` starts
  the recording and then immediately kills it, because gdbus exits and the shell
  logs "Fatal error while recording: Sender has vanished" - leaving a 48-byte mp4.
  This script holds a single D-Bus connection open for the whole take, which is the
  entire reason it is a script and not a one-liner.

USAGE
  ./scripts/record_screen.py OUTPUT_BASENAME --seconds 90
  ./scripts/record_screen.py media/nav2_goal_run --seconds 120

  Pass the basename WITHOUT an extension; GNOME appends .mp4 itself and warns if
  you supply one. The real output path is printed on stdout and is what you should
  reference in RUNBOOK section 8.

Ctrl-C stops the recording cleanly and keeps the footage recorded so far.
"""
import argparse
import os
import signal
import sys

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

BUS_NAME = "org.gnome.Shell.Screencast"
OBJ_PATH = "/org/gnome/Shell/Screencast"


def main():
    ap = argparse.ArgumentParser(description="Record the screen via GNOME Shell.")
    ap.add_argument("output", help="output basename, WITHOUT extension")
    ap.add_argument("--seconds", type=float, default=90.0,
                    help="recording length; Ctrl-C also stops cleanly (default 90)")
    ap.add_argument("--framerate", type=int, default=30)
    ap.add_argument("--no-cursor", action="store_true", help="hide the pointer")
    args = ap.parse_args()

    base = os.path.abspath(os.path.expanduser(args.output))
    if os.path.splitext(base)[1]:
        print(f"note: stripping extension from '{args.output}' - GNOME adds its own",
              file=sys.stderr)
        base = os.path.splitext(base)[0]
    os.makedirs(os.path.dirname(base), exist_ok=True)

    proxy = Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None,
        BUS_NAME, OBJ_PATH, BUS_NAME, None)

    opts = {
        "framerate": GLib.Variant("i", args.framerate),
        "draw-cursor": GLib.Variant("b", not args.no_cursor),
    }
    ok, path = proxy.call_sync(
        "Screencast",
        GLib.Variant("(sa{sv})", (base, opts)),
        Gio.DBusCallFlags.NONE, -1, None).unpack()

    if not ok:
        print("FAILED to start screencast", file=sys.stderr)
        return 1

    print(f"RECORDING -> {path}")
    print(f"stopping after {args.seconds:g}s (Ctrl-C to stop early)")

    loop = GLib.MainLoop()
    # Hold this process - and therefore the D-Bus connection - alive. If the
    # sender goes away the shell aborts the recording (see docstring).
    GLib.timeout_add(int(args.seconds * 1000), lambda: (loop.quit(), False)[1])
    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig,
                             lambda: (loop.quit(), False)[1])
    try:
        loop.run()
    finally:
        try:
            proxy.call_sync("StopScreencast", None,
                            Gio.DBusCallFlags.NONE, 5000, None)
        except GLib.Error as exc:
            print(f"warning: StopScreencast: {exc}", file=sys.stderr)

    size = os.path.getsize(path) if os.path.exists(path) else 0
    print(f"SAVED {path} ({size/1e6:.1f} MB)")
    if size < 100_000:
        print("WARNING: file is suspiciously small - the recording probably failed. "
              "Play it back before trusting it.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
