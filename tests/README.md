# Tests inside Hiero

The tests in `tests/hiero` run in a real Hiero session, because they
render with Hiero's exporter. Hiero has no terminal mode, so a Hiero
window opens while they run. They are not part of CI: they need a Hiero
licence and a display.

## Run

Run it with the AYON launcher, so Hiero gets the AYON environment: the
ayon-core of the launcher, and the `oiiotool` and `ffmpeg` it provides.

```shell
/path/to/ayon run tests/run_hiero_tests.py
/path/to/ayon run tests/run_hiero_tests.py --app /Applications/Nuke16.1v1
/path/to/ayon run tests/run_hiero_tests.py -- tests/hiero/test_render_track_item.py -k handles
```

The parity tests (`test_same_frames_as_original_*`) need an ayon-core with
`CollectOTIOProductResources`. They are skipped when the launcher's
ayon-core is older: pass `--core` with a newer checkout.

A plain `python tests/run_hiero_tests.py` works too, with the tools below
found on your own.

Arguments after `--` go to pytest. The exit code is pytest's.

What the runner needs:

- **Hiero**: `--app` (a Nuke executable, `.app` bundle or install folder),
  `AYON_HIERO_EXECUTABLE`, or the newest Nuke 16/17 in the usual install
  folder. Tested with Hiero 16.1 and 17.0.
- **ayon-core**: `--core`, `AYON_CORE_ROOT`, the launcher's ayon-core
  (`ayon run`), or an `ayon-core` checkout next to this repository (or
  next to a parent folder, for worktrees).
- **uv**: installs `requirements-hiero.txt` into `tests/.deps/` for the
  Python of the Hiero build, again when the file changes.
- **oiiotool** (`OIIOTOOL` or `PATH`): makes the test media and reads
  pixels back. **ffprobe** (`FFPROBE` or `PATH`) for the movie tests.
  Tests that miss a tool are skipped.

## How it works

`run_hiero_tests.py` starts `Nuke --hiero -q --script
tests/hiero/bootstrap.py`. The bootstrap adds the paths from
`HIERO_TEST_PATHS` to `sys.path`, runs pytest with the arguments from
`HIERO_PYTEST_ARGS` (Nuke takes some flags after `--script` as its own),
writes pytest's output to the log the runner prints, stops the Frame
Server and exits with pytest's exit code. Without stopping the Frame
Server its worker processes keep running after Hiero exits.

The test media is an EXR sequence 1001-1100 whose red channel holds
`(frame - 1000) / 1000`, so tests check which source frame was rendered
into which output frame (`source_frame` fixture). A JUnit report goes to
`tests/.results/`.
