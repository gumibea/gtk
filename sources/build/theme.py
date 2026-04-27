import os
import shutil
import subprocess
import glob
import zipfile
from pathlib import Path
from .logger import logger
from .utils import find_and_replace, Subsitution
from .context import BuildContext, IS_DARK, IS_LIGHT, IS_WINDOW_NORMAL, DARK_LIGHT


def apply_tweaks(ctx: BuildContext):
    ctx.apply_tweak("theme", "'default'", f"'{ctx.accent.identifier}'")

    if ctx.size == "compact":
        ctx.apply_tweak("compact", "'false'", "'true'")

    find_and_replace(
        f"{ctx.colloid_src_dir}/sass/_tweaks-temp.scss",
        Subsitution(
            find="@import 'color-palette-default';",
            replace=f"@import 'color-palette-catppuccin-{ctx.flavor.identifier}';",
        ),
    )
    ctx.apply_tweak("colorscheme", "'default'", "'catppuccin'")

    if ctx.tweaks.has("black"):
        ctx.apply_tweak("blackness", "'false'", "'true'")

    if ctx.tweaks.has("rimless"):
        ctx.apply_tweak("rimless", "'false'", "'true'")

    if ctx.tweaks.has("normal"):
        ctx.apply_tweak("window_button", "'mac'", "'normal'")

    if ctx.tweaks.has("float"):
        ctx.apply_tweak("float", "'false'", "'true'")


SASSC_OPT = ["-M", "-t", "expanded"]


def _write_gtk4_settings_template(ctx: BuildContext) -> None:
    """GTK4/Libadwaita often needs ~/.config/gtk-4.0/settings.ini; gsettings alone is not always enough."""
    prefer_dark = "true" if ctx.flavor.dark else "false"
    path = Path(ctx.output_dir()) / "gtk-4.0-settings.ini.template"
    path.write_text(
        "# Merge the [Settings] block into ~/.config/gtk-4.0/settings.ini (back up first).\n"
        "# Libadwaita may ignore gtk-theme from gsettings when the desktop portal disagrees.\n"
        "# If themes still do not apply, try:  ADW_DISABLE_PORTAL=1  (e.g. in ~/.config/environment.d/*.conf)\n"
        "# Quick test:  GTK_THEME="
        f"{ctx.build_id()} gnome-text-editor\n"
        "\n"
        "[Settings]\n"
        f"gtk-theme-name={ctx.build_id()}\n"
        f"gtk-application-prefer-dark-theme={prefer_dark}\n",
        encoding="utf-8",
    )


def compile_sass(src: str, dest: str) -> subprocess.Popen:
    return subprocess.Popen(["sassc", *SASSC_OPT, src, dest])


def execute_build(ctx: BuildContext):
    src_dir = ctx.colloid_src_dir
    output_dir = ctx.output_dir()

    logger.info(f"Building into '{output_dir}'...")

    apply_tweaks(ctx)

    os.makedirs(output_dir, exist_ok=True)
    with open(f"{output_dir}/index.theme", "w") as file:
        file.write("[Desktop Entry]\n")
        file.write("Type=X-GNOME-Metatheme\n")
        file.write(f"Name={ctx.build_id()}\n")
        file.write("Comment=An Flat Gtk+ theme based on Elegant Design\n")
        file.write("Encoding=UTF-8\n")
        file.write("\n")
        file.write("[X-GNOME-Metatheme]\n")
        file.write(f"GtkTheme={ctx.build_id()}\n")
        file.write(f"MetacityTheme={ctx.build_id()}\n")
        file.write(f"ShellTheme={ctx.build_id()}\n")
        file.write(f"IconTheme=Tela-circle{ctx.apply_suffix(IS_DARK)}\n")
        file.write(f"CursorTheme={ctx.flavor.name}-cursors\n")
        file.write("ButtonLayout=close,minimize,maximize:menu\n")

    sassc_tasks = []

    os.makedirs(f"{output_dir}/gnome-shell", exist_ok=True)
    shutil.copyfile(
        f"{src_dir}/main/gnome-shell/pad-osd.css",
        f"{output_dir}/gnome-shell/pad-osd.css",
    )

    sassc_tasks.append(
        compile_sass(
            f"{src_dir}/main/gnome-shell/gnome-shell{ctx.apply_suffix(DARK_LIGHT)}.scss",
            f"{output_dir}/gnome-shell/gnome-shell.css",
        )
    )

    os.makedirs(f"{output_dir}/gtk-3.0", exist_ok=True)
    sassc_tasks.append(
        compile_sass(
            f"{src_dir}/main/gtk-3.0/gtk{ctx.apply_suffix(DARK_LIGHT)}.scss",
            f"{output_dir}/gtk-3.0/gtk.css",
        )
    )
    sassc_tasks.append(
        compile_sass(
            f"{src_dir}/main/gtk-3.0/gtk-Dark.scss",
            f"{output_dir}/gtk-3.0/gtk-dark.css",
        )
    )

    os.makedirs(f"{output_dir}/gtk-4.0", exist_ok=True)
    sassc_tasks.append(
        compile_sass(
            f"{src_dir}/main/gtk-4.0/gtk{ctx.apply_suffix(DARK_LIGHT)}.scss",
            f"{output_dir}/gtk-4.0/gtk.css",
        )
    )
    sassc_tasks.append(
        compile_sass(
            f"{src_dir}/main/gtk-4.0/gtk-Dark.scss",
            f"{output_dir}/gtk-4.0/gtk-dark.css",
        )
    )

    os.makedirs(f"{output_dir}/cinnamon", exist_ok=True)
    sassc_tasks.append(
        compile_sass(
            f"{src_dir}/main/cinnamon/cinnamon{ctx.apply_suffix(DARK_LIGHT)}.scss",
            f"{output_dir}/cinnamon/cinnamon.css",
        )
    )

    for task in sassc_tasks:
        task.wait()

    _write_gtk4_settings_template(ctx)

    os.makedirs(f"{output_dir}/metacity-1", exist_ok=True)
    shutil.copyfile(
        f"{src_dir}/main/metacity-1/metacity-theme-3{ctx.apply_suffix(IS_WINDOW_NORMAL)}.xml",
        f"{output_dir}/metacity-1/metacity-theme-3.xml",
    )

    os.makedirs(f"{output_dir}/xfwm4", exist_ok=True)
    shutil.copyfile(
        f"{src_dir}/main/xfwm4/themerc{ctx.apply_suffix(IS_LIGHT)}",
        f"{output_dir}/xfwm4/themerc",
    )

    os.makedirs(f"{output_dir}-hdpi/xfwm4", exist_ok=True)
    shutil.copyfile(
        f"{src_dir}/main/xfwm4/themerc{ctx.apply_suffix(IS_LIGHT)}",
        f"{output_dir}-hdpi/xfwm4/themerc",
    )
    find_and_replace(
        f"{output_dir}-hdpi/xfwm4/themerc",
        Subsitution(find="button_offset=6", replace="button_offset=9"),
    )

    os.makedirs(f"{output_dir}-xhdpi/xfwm4", exist_ok=True)
    shutil.copyfile(
        f"{src_dir}/main/xfwm4/themerc{ctx.apply_suffix(IS_LIGHT)}",
        f"{output_dir}-xhdpi/xfwm4/themerc",
    )

    find_and_replace(
        f"{output_dir}-xhdpi/xfwm4/themerc",
        Subsitution(find="button_offset=6", replace="button_offset=12"),
    )

    if not ctx.flavor.dark:
        shutil.copytree(
            f"{src_dir}/main/plank/theme-Light-Catppuccin/",
            f"{output_dir}/plank",
            dirs_exist_ok=True,
        )
    else:
        shutil.copytree(
            f"{src_dir}/main/plank/theme-Dark-Catppuccin/",
            f"{output_dir}/plank",
            dirs_exist_ok=True,
        )


def make_assets(ctx: BuildContext):
    output_dir = ctx.output_dir()
    src_dir = ctx.colloid_src_dir

    os.makedirs(f"{output_dir}/cinnamon/assets", exist_ok=True)
    for file in glob.glob(f"{src_dir}/assets/cinnamon/theme/*.svg"):
        shutil.copy(file, f"{output_dir}/cinnamon/assets")
    shutil.copy(
        f"{src_dir}/assets/cinnamon/thumbnail{ctx.apply_suffix(DARK_LIGHT)}.svg",
        f"{output_dir}/cinnamon/thumbnail.png",
    )

    os.makedirs(f"{output_dir}/gnome-shell/assets", exist_ok=True)
    for file in glob.glob(f"{src_dir}/assets/gnome-shell/theme/*.svg"):
        shutil.copy(file, f"{output_dir}/gnome-shell/assets")

    shutil.copytree(
        f"{src_dir}/assets/gtk/assets",
        f"{output_dir}/gtk-3.0/assets",
        dirs_exist_ok=True,
    )
    shutil.copytree(
        f"{src_dir}/assets/gtk/assets",
        f"{output_dir}/gtk-4.0/assets",
        dirs_exist_ok=True,
    )
    shutil.copyfile(
        f"{src_dir}/assets/gtk/thumbnail{ctx.apply_suffix(IS_DARK)}.svg",
        f"{output_dir}/gtk-3.0/thumbnail.png",
    )
    shutil.copyfile(
        f"{src_dir}/assets/gtk/thumbnail{ctx.apply_suffix(IS_DARK)}.svg",
        f"{output_dir}/gtk-4.0/thumbnail.png",
    )

    theme_color = ctx.accent.hex

    palette = ctx.flavor.colors
    background = palette.base.hex
    background_alt = palette.mantle.hex
    titlebar = palette.overlay0.hex

    for file in glob.glob(f"{output_dir}/cinnamon/assets/*.svg"):
        find_and_replace(
            file,
            Subsitution(find="#5b9bf8", replace=theme_color),
            Subsitution(find="#3c84f7", replace=theme_color),
        )

    for file in glob.glob(f"{output_dir}/gnome-shell/assets/*.svg"):
        find_and_replace(
            file,
            Subsitution(find="#5b9bf8", replace=theme_color),
            Subsitution(find="#3c84f7", replace=theme_color),
        )

    for file in glob.glob(f"{output_dir}/gtk-3.0/assets/*.svg"):
        find_and_replace(
            file,
            Subsitution(find="#5b9bf8", replace=theme_color),
            Subsitution(find="#3c84f7", replace=theme_color),
            Subsitution(find="#ffffff", replace=background),
            Subsitution(find="#2c2c2c", replace=background),
            Subsitution(find="#3c3c3c", replace=background_alt),
        )

    for file in glob.glob(f"{output_dir}/gtk-4.0/assets/*.svg"):
        find_and_replace(
            file,
            Subsitution(find="#5b9bf8", replace=theme_color),
            Subsitution(find="#3c84f7", replace=theme_color),
            Subsitution(find="#ffffff", replace=background),
            Subsitution(find="#2c2c2c", replace=background),
            Subsitution(find="#3c3c3c", replace=background_alt),
        )

    if ctx.flavor.dark:
        find_and_replace(
            f"{output_dir}/cinnamon/thumbnail.png",
            Subsitution(find="#2c2c2c", replace=background),
            Subsitution(find="#5b9bf8", replace=theme_color),
        )

        find_and_replace(
            f"{output_dir}/gtk-3.0/thumbnail.png",
            Subsitution(find="#5b9bf8", replace=theme_color),
            Subsitution(find="#2c2c2c", replace=background),
        )

        find_and_replace(
            f"{output_dir}/gtk-4.0/thumbnail.png",
            Subsitution(find="#5b9bf8", replace=theme_color),
            Subsitution(find="#2c2c2c", replace=background),
        )
    else:
        find_and_replace(
            f"{output_dir}/cinnamon/thumbnail.png",
            Subsitution(find="#ffffff", replace=background),
            Subsitution(find="#f2f2f2", replace=titlebar),
            Subsitution(find="#3c84f7", replace=theme_color),
        )

        find_and_replace(
            f"{output_dir}/gtk-3.0/thumbnail.png",
            Subsitution(find="#f2f2f2", replace=titlebar),
            Subsitution(find="#3c84f7", replace=theme_color),
        )

        find_and_replace(
            f"{output_dir}/gtk-4.0/thumbnail.png",
            Subsitution(find="#f2f2f2", replace=titlebar),
            Subsitution(find="#3c84f7", replace=theme_color),
        )

    for file in glob.glob(f"{src_dir}/assets/cinnamon/common-assets/*.svg"):
        shutil.copy(file, f"{output_dir}/cinnamon/assets")

    for file in glob.glob(
        f"{src_dir}/assets/cinnamon/assets{ctx.apply_suffix(IS_DARK)}/*.svg"
    ):
        shutil.copy(file, f"{output_dir}/cinnamon/assets")

    for file in glob.glob(f"{src_dir}/assets/gnome-shell/common-assets/*.svg"):
        shutil.copy(file, f"{output_dir}/gnome-shell/assets")

    for file in glob.glob(
        f"{src_dir}/assets/gnome-shell/assets{ctx.apply_suffix(IS_DARK)}/*.svg"
    ):
        shutil.copy(file, f"{output_dir}/gnome-shell/assets")

    for file in glob.glob(f"{src_dir}/assets/gtk/symbolics/*.svg"):
        shutil.copy(file, f"{output_dir}/gtk-3.0/assets")
        shutil.copy(file, f"{output_dir}/gtk-4.0/assets")

    for file in glob.glob(
        f"{src_dir}/assets/metacity-1/assets{ctx.apply_suffix(IS_WINDOW_NORMAL)}/*.svg"
    ):
        shutil.copy(file, f"{output_dir}/metacity-1/assets")
    shutil.copy(
        f"{src_dir}/assets/metacity-1/thumbnail{ctx.apply_suffix(IS_DARK)}.png",
        f"{output_dir}/metacity-1/thumbnail.png",
    )

    xfwm4_assets = f"{ctx.git_root}/patches/xfwm4/generated/assets-catppuccin-{ctx.flavor.identifier}"
    for file in glob.glob(xfwm4_assets + "/*"):
        shutil.copy(file, f"{output_dir}/xfwm4")

    xfwm4_assets = xfwm4_assets + "-hdpi/*"
    for file in glob.glob(xfwm4_assets):
        shutil.copy(file, f"{output_dir}-hdpi/xfwm4")

    xfwm4_assets = xfwm4_assets + "-xhdpi/*"
    for file in glob.glob(xfwm4_assets):
        shutil.copy(file, f"{output_dir}-xhdpi/xfwm4")


def zip_dir(path, zip_file):
    for root, _, files in os.walk(path):
        for file in files:
            zip_file.write(
                os.path.join(root, file),
                os.path.relpath(os.path.join(root, file), os.path.join(path, "..")),
            )


def zip_artifacts(dir_list, zip_name, remove=True):
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zipf:
        for dir in dir_list:
            zip_dir(dir, zipf)

    if remove:
        for dir in dir_list:
            shutil.rmtree(dir)


def build_with_context(ctx: BuildContext):
    build_info = f"""Build info:
    build_root: {ctx.output_root}
    src_root:   {ctx.colloid_src_dir}
    theme_name: {ctx.theme_name}
    flavor:     {ctx.flavor.identifier}
    accent:     {ctx.accent.identifier}
    size:       {ctx.size}
    tweaks:     {ctx.tweaks}"""
    logger.info(build_info)

    execute_build(ctx)
    logger.info("Main build complete")

    logger.info("Bundling assets...")
    make_assets(ctx)
    logger.info("Asset bundling done")

    logger.info(
        "Theme install: copy to ~/.local/share/themes/ then in GNOME Tweaks set "
        f"Applications (and Shell) to '{ctx.build_id()}'. "
        f"If GTK4 apps still look like Adwaita, merge '{ctx.build_id()}/gtk-4.0-settings.ini.template' "
        "into ~/.config/gtk-4.0/settings.ini and re-login (Libadwaita + portal often needs this). "
        "Try: GTK_THEME="
        f"{ctx.build_id()} gnome-text-editor — if that works, use settings.ini / ADW_DISABLE_PORTAL=1. "
        "User Themes extension may be required for Shell. Flatpak: allow xdg-data/themes."
    )

    if ctx.output_format == "zip":
        zip_artifacts(
            [
                ctx.output_dir(),
                f"{ctx.output_dir()}-hdpi",
                f"{ctx.output_dir()}-xhdpi",
            ],
            f"{ctx.output_root}/{ctx.build_id()}.zip",
            True,
        )


def gnome_shell_version(src_dir):
    """Pick the newest Colloid widget bundle present (48-0 for GNOME 47+, 46-0 older)."""
    sass_gs = Path(src_dir) / "sass/gnome-shell"
    gs_version = "40-0"
    for ver in ("48-0", "46-0", "44-0", "42-0", "40-0"):
        if (sass_gs / f"_widgets-{ver}.scss").is_file():
            gs_version = ver
            break

    logger.info(f"Using Colloid gnome-shell widget bundle: widgets-{gs_version}")

    shutil.copyfile(
        f"{src_dir}/sass/gnome-shell/_common.scss",
        f"{src_dir}/sass/gnome-shell/_common-temp.scss",
    )
    find_and_replace(
        f"{src_dir}/sass/gnome-shell/_common-temp.scss",
        Subsitution(
            find="@import 'widgets-40-0';",
            replace=f"@import 'widgets-{gs_version}';",
        ),
    )
