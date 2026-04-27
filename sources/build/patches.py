import os
import subprocess
from pathlib import Path
from .logger import logger

# Colloid’s theme() maps accent names to palette vars; we replace it with Catppuccin
# accents. Done programmatically so we do not depend on a specific Colloid git SHA
# (git apply on theme-func.patch breaks whenever upstream edits theme()).
_THEME_FUNC_MARKER = "@function theme($color) {"
_THEME_FUNC_REPLACEMENT = """@function theme($color) {
  @if ($theme == 'rosewater') { @return $rosewater; }
  @if ($theme == 'flamingo') { @return $flamingo; }
  @if ($theme == 'pink') { @return $pink; }
  @if ($theme == 'mauve') { @return $mauve; }
  @if ($theme == 'red') { @return $red; }
  @if ($theme == 'maroon') { @return $maroon; }
  @if ($theme == 'peach') { @return $peach; }
  @if ($theme == 'yellow') { @return $yellow; }
  @if ($theme == 'green') { @return $green; }
  @if ($theme == 'teal') { @return $teal; }
  @if ($theme == 'sky') { @return $sky; }
  @if ($theme == 'sapphire') { @return $sapphire; }
  @if ($theme == 'blue') { @return $blue; }
  @if ($theme == 'lavender') { @return $lavender; }
}
"""


def _rewrite_catppuccin_theme_function(colloid_dir: Path) -> None:
    colors_path = colloid_dir / "src/sass/_colors.scss"
    text = colors_path.read_text(encoding="utf-8")
    start = text.find(_THEME_FUNC_MARKER)
    if start == -1:
        raise RuntimeError(
            f"Could not find `{_THEME_FUNC_MARKER}` in {colors_path}. "
            "Upstream Colloid may have renamed theme(); update catppuccin-gtk."
        )
    body_start = start + len(_THEME_FUNC_MARKER)
    depth = 1
    k = body_start
    while k < len(text) and depth:
        c = text[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        k += 1
    if depth != 0:
        raise RuntimeError(f"Unbalanced `{{`/`}}` in theme() in {colors_path}")
    new_text = text[:start] + _THEME_FUNC_REPLACEMENT + text[k:]
    colors_path.write_text(new_text, encoding="utf-8")


def _apply_quick_settings_patch(colloid_dir: Path, patch_dir: str) -> None:
    """Colloid ships quick settings SCSS under widgets-46-0 and/or widgets-48-0 (GNOME Shell)."""
    base = Path(os.getcwd()) / colloid_dir
    gs = base / "src/sass/gnome-shell"
    qs46 = gs / "widgets-46-0/_quick-settings.scss"
    qs48 = gs / "widgets-48-0/_quick-settings.scss"
    rel_patch = Path(patch_dir).relative_to(os.getcwd())
    if not qs46.is_file() and not qs48.is_file():
        found = list(gs.glob("widgets-*-*/_quick-settings.scss")) if gs.is_dir() else []
        found_list = [str(p.relative_to(base)) for p in found]
        raise RuntimeError(
            "Cannot patch quick settings: need "
            "src/sass/gnome-shell/widgets-46-0/_quick-settings.scss and/or "
            "widgets-48-0/_quick-settings.scss. "
            f"Under {gs}, found: {found_list!r}. "
            "Your sources/colloid is almost certainly not "
            "vinceliuice/Colloid-gtk-theme (for example submodule origin is "
            "catppuccin/gtk). Fix with:\n"
            "  git submodule deinit -f sources/colloid\n"
            "  rm -rf sources/colloid\n"
            "  git submodule update --init sources/colloid\n"
            "  git -C sources/colloid remote get-url origin\n"
            "    # expect https://github.com/vinceliuice/Colloid-gtk-theme.git"
        )
    for patch_name, path in (
        ("quick-settings-gnome48.patch", qs46),
        ("quick-settings-widgets-48.patch", qs48),
    ):
        if path.is_file():
            patch_path = rel_patch / patch_name
            logger.info(f"Applying quick settings patch '{patch_name}'")
            subprocess.check_call(
                ["git", "apply", str(patch_path), "--directory", str(colloid_dir)]
            )


def apply_colloid_patches(colloid_dir, patch_dir):
    colloid_dir = Path(colloid_dir).relative_to(os.getcwd())
    if os.path.isfile(colloid_dir / ".patched"):
        logger.info(
            f'Patches seem to be applied, remove "{colloid_dir}/.patched" to force application (this may fail)'
        )
        return

    logger.info("Applying patches...")
    abs_colloid = (Path(os.getcwd()) / colloid_dir).resolve()
    if not (abs_colloid / "src/sass/_colors.scss").is_file():
        raise RuntimeError(
            f"Missing {abs_colloid / 'src/sass/_colors.scss'} — "
            "sources/colloid is not a Colloid-gtk-theme tree. "
            "Re-init the submodule (see quick-settings error text for commands)."
        )

    for patch in [
        "plank-dark.patch",
        "plank-light.patch",
        "sass-palette-frappe.patch",
        "sass-palette-mocha.patch",
        "sass-palette-latte.patch",
        "sass-palette-macchiato.patch",
    ]:
        path = (Path(patch_dir) / patch).relative_to(os.getcwd())
        logger.info(f"Applying patch '{patch}', located at '{path}'")
        subprocess.check_call(
            ["git", "apply", str(path), "--directory", str(colloid_dir)]
        )

    _apply_quick_settings_patch(colloid_dir, patch_dir)

    logger.info("Rewriting Colloid theme() for Catppuccin accents")
    _rewrite_catppuccin_theme_function(colloid_dir)

    with open(colloid_dir / ".patched", "w") as f:
        f.write("true")

    logger.info("Patching finished.")
