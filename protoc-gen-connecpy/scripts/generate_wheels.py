import json
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    base_dir = Path(__file__).parent / ".." / ".."
    with (base_dir / "out" / "artifacts.json").open() as f:
        artifacts: list[dict[str, str]] = json.load(f)
    for artifact in artifacts:
        if artifact["type"] != "Binary":
            continue
        # Check https://go.dev/wiki/MinimumRequirements#operating-systems for
        # minimum OS versions
        platform = ""
        match artifact["goos"]:
            case "darwin":
                match artifact["goarch"]:
                    case "amd64":
                        platform = "macosx_11_0_x86_64"
                    case "arm64":
                        platform = "macosx_11_0_arm64"
            case "linux":
                # While manylinux1 is considered legacy versus the more
                # precise manylinux_x_y, our binaries are statically compiled
                # so we go with it for maximum compatibility. We also use the
                # same wheel for musl.
                match artifact["goarch"]:
                    case "amd64":
                        platform = "manylinux1_x86_64"
                    case "arm64":
                        platform = "manylinux1_aarch64"
            case "windows":
                match artifact["goarch"]:
                    case "amd64":
                        platform = "win_amd64"
                    case "arm64":
                        platform = "win_arm64"
        if not platform:
            msg = f"Unsupported platform: {artifact['goos']}/{artifact['goarch']}"
            raise ValueError(msg)
        exe_path = base_dir / artifact["path"]
        bin_dir = Path(__file__).parent / ".." / "out" / "bin"
        shutil.rmtree(bin_dir, ignore_errors=True)
        bin_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(exe_path, bin_dir / exe_path.name)
        subprocess.run(["uv", "build", "--wheel"], check=True)  # noqa: S607
        dist_dir = Path(__file__).parent / ".." / "dist"
        built_wheel = next(dist_dir.glob("*-py3-none-any.whl"))
        base_name = built_wheel.name[: -len("-py3-none-any.whl")]
        wheel_name = f"{base_name}-py3-none-{platform}.whl"
        built_wheel.rename(dist_dir / wheel_name)
        if platform.startswith("manylinux1"):
            shutil.copyfile(
                dist_dir / wheel_name,
                dist_dir / wheel_name.replace("manylinux1", "musllinux_1_0"),
            )


if __name__ == "__main__":
    main()
