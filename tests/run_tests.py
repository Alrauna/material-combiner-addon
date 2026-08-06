"""Cross-platform Blender test runner for Material Combiner.

Replaces the PowerShell runners so the same suites run on Windows and Linux.
Every mode builds an isolated Blender profile under a caller-supplied work
directory, so the user's real configuration is never touched.

Examples:
    python tests/run_tests.py source --blender BLENDER --work WORK \\
        --script tests/blender/verify_public_api.py --result public_api.json

    python tests/run_tests.py package --blender BLENDER --work WORK \\
        --package dist/addon.zip \\
        --script tests/blender/verify_packaged_dependency.py

    python tests/run_tests.py checkpoint --blender BLENDER --work WORK \\
        --package dist/addon.zip --cats CATS.zip
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
# Target length for the installed extension directory in --long-path mode.
#
# The defect window is narrow and overshooting hides it. Path.resolve() keeps
# the \\?\ prefix only when its result exceeds MAX_PATH, so the extension root
# must stay under 260 (resolving to a plain path) while files inside it exceed
# 260 (resolving with the prefix). That mix is what broke the dependency trust
# check. Pad past 260 here and every path is prefixed, everything agrees, and
# the regression passes even when the fix is reverted.
LONG_PATH_EXTENSION_TARGET = 245
ADDON = REPO / "addon"
EXTENSION_ID = "shotariyas_material_combiner"
CATS_ID = "cats_blender_plugin"
CONTRACT = REPO / "tests" / "contracts" / "public_api_contract.json"
PROFILE_DIRECTORIES = (
    "config",
    "scripts",
    "datafiles",
    "extensions",
    "home",
    "appdata",
    "localappdata",
    "cache",
    "temp",
    "results",
)


def fs_path(path: Path) -> Path:
    """Return a path usable past MAX_PATH.

    GitHub's Windows images do not enable long paths system-wide, so the
    runner must opt in with extended-length syntax rather than assume the
    registry setting is present.
    """
    if os.name != "nt":
        return path
    text = str(path.absolute())
    if text.startswith("\\\\?\\"):
        return path
    if text.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + text[2:])
    return Path("\\\\?\\" + text)


def pad_to_long_path(work: Path) -> Path:
    """Nest the work directory so it lands inside the defect window."""
    suffix = len(
        str(Path("profile") / "extensions" / "user_default" / EXTENSION_ID)
    )
    needed = LONG_PATH_EXTENSION_TARGET - suffix - len(str(work)) - 2
    if needed <= 0:
        return work
    return work / ("p" * needed)


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Profile:
    """An isolated Blender profile inside a work directory."""

    def __init__(
        self,
        work: Path,
        drive_letter: str | None,
        long_path: bool = False,
    ) -> None:
        self.base = work
        self.work = pad_to_long_path(work) if long_path else work
        self.root = self.work / "profile"
        self.results = self.root / "results"
        self._drive = drive_letter if os.name == "nt" else None

    def create(self) -> None:
        if fs_path(self.base).exists():
            shutil.rmtree(fs_path(self.base))
        for name in PROFILE_DIRECTORIES:
            fs_path(self.root / name).mkdir(parents=True, exist_ok=True)

    def __enter__(self) -> Profile:
        self.create()
        if self._drive:
            drive = f"{self._drive}:"
            existing = subprocess.run(
                ["subst"], capture_output=True, text=True, check=False
            ).stdout
            if any(
                line.startswith(f"{drive}\\:") for line in existing.splitlines()
            ):
                raise RuntimeError(f"Drive alias already in use: {drive}")
            subprocess.run(
                ["subst", drive, str(self.work)], check=True
            )
            self.runtime = Path(f"{drive}\\") / "profile"
        else:
            self.runtime = self.root
        return self

    def __exit__(self, *exc: object) -> None:
        if self._drive:
            subprocess.run(
                ["subst", f"{self._drive}:", "/d"], check=False
            )

    @property
    def extension_dir(self) -> Path:
        return self.root / "extensions" / "user_default" / EXTENSION_ID

    def environment(self) -> dict[str, str]:
        """Redirect every path Blender and Python consult."""
        runtime = self.runtime
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.update(
            {
                "BLENDER_USER_CONFIG": str(runtime / "config"),
                "BLENDER_USER_SCRIPTS": str(runtime / "scripts"),
                "BLENDER_USER_DATAFILES": str(runtime / "datafiles"),
                "BLENDER_USER_EXTENSIONS": str(runtime / "extensions"),
                "HOME": str(runtime / "home"),
                "USERPROFILE": str(runtime / "home"),
                "APPDATA": str(runtime / "appdata"),
                "LOCALAPPDATA": str(runtime / "localappdata"),
                "XDG_CACHE_HOME": str(runtime / "cache"),
                "TEMP": str(runtime / "temp"),
                "TMP": str(runtime / "temp"),
                "TMPDIR": str(runtime / "temp"),
                "PYTHONNOUSERSITE": "1",
                "SMC_TEST_CONTRACT": str(CONTRACT),
            }
        )
        return env


def display_prefix(foreground: bool) -> list[str]:
    """Return a command prefix giving Blender a display when it needs one.

    The atlas undo check needs a real window. Headless Linux CI has no
    display, so wrap it in a virtual framebuffer. Without this the check
    silently reports that it needs a foreground context and never runs.
    """
    if not foreground or os.name == "nt":
        return []
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return []
    xvfb = shutil.which("xvfb-run")
    if xvfb is None:
        raise SystemExit(
            "Foreground mode needs a display. Install xvfb, or export "
            "DISPLAY if one is already available."
        )
    return [xvfb, "-a", "--server-args=-screen 0 1280x1024x24"]


def run_blender(
    blender: Path,
    profile: Profile,
    arguments: list[str],
    *,
    name: str,
    result_name: str | None = None,
    extra_env: dict[str, str] | None = None,
    prefix: list[str] | None = None,
) -> int:
    """Run Blender once, capturing its output beside the results."""
    env = profile.environment()
    if result_name:
        env["SMC_TEST_RESULT"] = str(profile.runtime / "results" / result_name)
    if extra_env:
        env.update(extra_env)

    completed = subprocess.run(
        [*(prefix or []), str(blender), *arguments],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    for stream, suffix in (
        (completed.stdout, "stdout"),
        (completed.stderr, "stderr"),
    ):
        fs_path(profile.results / f"{name}.{suffix}.log").write_text(
            stream or "", encoding="utf-8", newline="\n"
        )

    exit_code = completed.returncode
    if exit_code == 0 and result_name:
        if not fs_path(profile.results / result_name).is_file():
            exit_code = 1
            with fs_path(profile.results / f"{name}.stderr.log").open(
                "a", encoding="utf-8", newline="\n"
            ) as stream:
                stream.write(f"\nBlender did not create {result_name}\n")
    return exit_code


def install_package(
    blender: Path, profile: Profile, package: Path, name: str
) -> int:
    return run_blender(
        blender,
        profile,
        [
            "--factory-startup",
            "--disable-autoexec",
            "--command",
            "extension",
            "install-file",
            "-r",
            "user_default",
            str(package),
        ],
        name=name,
    )


def copy_addon(profile: Profile, exclude_wheel: bool) -> None:
    """Copy only the extension source into the isolated profile."""
    destination = fs_path(profile.extension_dir)
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        ADDON,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    if exclude_wheel:
        shutil.rmtree(destination / "wheels", ignore_errors=True)


def report(payload: dict[str, object], exit_code: int) -> int:
    payload["exit_code"] = exit_code
    print(json.dumps(payload, indent=2))
    return exit_code


def command_source(args: argparse.Namespace) -> int:
    with Profile(args.work, args.drive_letter, args.long_path) as profile:
        copy_addon(profile, args.exclude_wheel)
        arguments = ["--factory-startup", "--disable-autoexec"]
        if not args.foreground:
            arguments.append("--background")
        arguments += ["--python", str(REPO / args.script)]

        extra_env = {}
        if args.foreground:
            extra_env["SMC_TEST_FOREGROUND"] = "1"
        if args.pillow_root:
            extra_env["SMC_TEST_PILLOW_ROOT"] = str(
                Path(args.pillow_root).resolve()
            )

        exit_code = run_blender(
            args.blender,
            profile,
            arguments,
            name="source",
            result_name=args.result,
            extra_env=extra_env,
            prefix=display_prefix(args.foreground),
        )
        return report(
            {
                "mode": "source",
                "script": args.script,
                "result": str(profile.results / args.result),
                "extension_path_length": len(str(profile.extension_dir)),
            },
            exit_code,
        )


def command_package(args: argparse.Namespace) -> int:
    with Profile(args.work, args.drive_letter) as profile:
        exit_code = install_package(
            args.blender, profile, args.package, "install"
        )
        if exit_code == 0:
            exit_code = run_blender(
                args.blender,
                profile,
                [
                    "--factory-startup",
                    "--disable-autoexec",
                    "--background",
                    "--python",
                    str(REPO / args.script),
                ],
                name="package",
                result_name=args.result,
            )
        return report(
            {
                "mode": "package",
                "package": str(args.package),
                "result": str(profile.results / args.result),
            },
            exit_code,
        )


def command_checkpoint(args: argparse.Namespace) -> int:
    """Install Material Combiner beside CATS, then restart and uninstall."""
    actual = sha256_file(args.cats)
    if args.cats_sha256 and actual.lower() != args.cats_sha256.lower():
        return report(
            {
                "mode": "checkpoint",
                "error": "CATS reference hash mismatch",
                "expected_sha256": args.cats_sha256,
                "actual_sha256": actual,
            },
            1,
        )

    steps = [
        ("integration", "verify_cats_checkpoint.py", "cats_checkpoint.json"),
        ("restart", "verify_checkpoint_restart.py", "checkpoint_restart.json"),
    ]
    with Profile(args.work, args.drive_letter) as profile:
        exit_code = install_package(
            args.blender, profile, args.package, "install-mc"
        )
        if exit_code == 0:
            exit_code = install_package(
                args.blender, profile, args.cats, "install-cats"
            )
        for name, script, result_name in steps:
            if exit_code:
                break
            arguments = ["--disable-autoexec", "--background"]
            if name != "restart":
                arguments.insert(0, "--factory-startup")
            arguments += [
                "--python",
                str(REPO / "tests" / "blender" / script),
            ]
            exit_code = run_blender(
                args.blender,
                profile,
                arguments,
                name=name,
                result_name=result_name,
            )
        if exit_code == 0:
            exit_code = run_blender(
                args.blender,
                profile,
                [
                    "--disable-autoexec",
                    "--command",
                    "extension",
                    "remove",
                    f"{CATS_ID},{EXTENSION_ID}",
                ],
                name="uninstall",
            )
        if exit_code == 0:
            exit_code = run_blender(
                args.blender,
                profile,
                [
                    "--factory-startup",
                    "--disable-autoexec",
                    "--background",
                    "--python",
                    str(
                        REPO
                        / "tests"
                        / "blender"
                        / "verify_checkpoint_uninstall.py"
                    ),
                ],
                name="uninstall-check",
                result_name="checkpoint_uninstall.json",
            )
        return report(
            {
                "mode": "checkpoint",
                "cats_sha256": actual,
                "results_directory": str(profile.results),
            },
            exit_code,
        )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--blender", type=Path, required=True)
    root.add_argument("--work", type=Path, required=True)
    root.add_argument(
        "--drive-letter",
        default="Q",
        help="Windows drive alias that shortens runtime paths. "
        "Use --no-drive-alias to disable. Ignored on other platforms.",
    )
    root.add_argument(
        "--no-drive-alias",
        dest="drive_letter",
        action="store_const",
        const=None,
    )

    modes = root.add_subparsers(dest="mode", required=True)

    source = modes.add_parser("source", help="run against the addon source")
    source.add_argument("--script", required=True)
    source.add_argument("--result", default="result.json")
    source.add_argument("--exclude-wheel", action="store_true")
    source.add_argument(
        "--foreground",
        action="store_true",
        help="Run Blender with a window, which the atlas undo check needs. "
        "On Linux without a display, xvfb-run supplies one.",
    )
    source.add_argument(
        "--long-path",
        action="store_true",
        help="Nest the work directory so files inside it exceed the Windows "
        "MAX_PATH limit, exercising the extended-length path handling.",
    )
    source.add_argument("--pillow-root", default="")
    source.set_defaults(func=command_source)

    package = modes.add_parser("package", help="run against a built package")
    package.add_argument("--package", type=Path, required=True)
    package.add_argument("--script", required=True)
    package.add_argument("--result", default="result.json")
    package.set_defaults(func=command_package)

    checkpoint = modes.add_parser("checkpoint", help="CATS lifecycle checks")
    checkpoint.add_argument("--package", type=Path, required=True)
    checkpoint.add_argument("--cats", type=Path, required=True)
    checkpoint.add_argument("--cats-sha256", default="")
    checkpoint.set_defaults(func=command_checkpoint)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    args.blender = args.blender.resolve()
    args.work = Path(os.path.abspath(args.work))
    if not args.blender.is_file():
        raise SystemExit(f"Blender executable not found: {args.blender}")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
