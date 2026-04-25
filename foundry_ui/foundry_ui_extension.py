import json
import re
import shutil
from pathlib import Path
from subprocess import PIPE, CalledProcessError, run

from components.webui_client.client_utils import generate_nginx_cfg_from_template
from core.constants import NGINX_SITES_AVAILABLE, NGINX_SITES_ENABLED
from core.logger import DialogType, Logger
from extensions.base_extension import BaseExtension
from utils.common import check_install_dependencies
from utils.fs_utils import create_symlink, remove_with_sudo
from utils.input_utils import get_confirm, get_number_input, get_string_input
from utils.sys_utils import cmd_sysctl_service, set_nginx_permissions

MODULE_PATH = Path(__file__).resolve().parent
FOUNDRY_DIR = Path.home().joinpath("foundry-ui")
FOUNDRY_WEB_ROOT = Path("/var/www/foundryui")
FOUNDRY_REPO = "https://github.com/devinsheppard/foundry-ui.git"
FOUNDRY_BRANCH = "codex/step-10-2-live-moonraker-bootstrap"
FOUNDRY_CFG_NAME = "foundry-ui.conf"
FOUNDRY_MANIFEST = FOUNDRY_DIR.joinpath(".kiauh-foundry-install.json")
DEFAULT_PORT = 7137
DEFAULT_MOONRAKER_HOST = "127.0.0.1"
DEFAULT_MOONRAKER_PORT = 7125
DEFAULT_PRINTER_ID = "printer"
DEFAULT_PRINTER_NAME = "Foundry"
DEFAULT_PRINTER_HOST = "Moonraker"
MIN_NODE_MAJOR = 20
TARGET_NODE_MAJOR = 24
SYSTEM_PACKAGES = {
    "nginx",
    "git",
    "curl",
    "ca-certificates",
    "gnupg",
    "rsync",
    "build-essential",
}


class FoundryUiExtension(BaseExtension):
    def install_extension(self, **kwargs) -> None:
        Logger.print_status("Installing Foundry UI ...")
        Logger.print_dialog(
            DialogType.ATTENTION,
            [
                "Foundry UI will be built locally with npm and served through nginx.",
                "The installer can add Node.js if the system version is missing or too old.",
                "Choose a free port unless you intentionally want to replace another web UI.",
            ],
        )

        install_config = self._prompt_install_config()
        if install_config is None:
            Logger.print_info("Foundry UI installation aborted.")
            return

        try:
            check_install_dependencies(SYSTEM_PACKAGES)
            self._ensure_nodejs()
            self._sync_repository(
                install_config["repo_url"],
                install_config["branch"],
                refresh_existing=install_config["refresh_existing"],
            )
            self._write_env_file(install_config)
            self._install_npm_dependencies()
            self._build_app()
            self._deploy_dist()
            self._create_nginx_config(install_config)
            self._write_manifest(install_config)

            log = (
                f"Open Foundry UI now on: "
                f"http://{self._get_local_ipv4()}:{install_config['port']}"
            )
            Logger.print_ok("Foundry UI installation complete!", start="\n")
            Logger.print_ok(log, prefix=False, end="\n\n")
        except Exception as e:
            Logger.print_error(f"Error during Foundry UI installation: {e}")

    def update_extension(self, **kwargs) -> None:
        Logger.print_status("Updating Foundry UI ...")
        try:
            install_config = self._read_manifest()
            if install_config is None:
                Logger.print_error(
                    "No install manifest found. Re-run the installer first."
                )
                return

            check_install_dependencies(SYSTEM_PACKAGES)
            self._ensure_nodejs()
            self._sync_repository(
                install_config["repo_url"],
                install_config["branch"],
                refresh_existing=True,
            )
            self._write_env_file(install_config)
            self._install_npm_dependencies()
            self._build_app()
            self._deploy_dist()
            self._create_nginx_config(install_config)
            self._write_manifest(install_config)

            Logger.print_ok("Foundry UI update complete!")
        except Exception as e:
            Logger.print_error(f"Error during Foundry UI update: {e}")

    def remove_extension(self, **kwargs) -> None:
        if not get_confirm(
            "Remove the Foundry UI deployment from this machine",
            default_choice=False,
        ):
            Logger.print_info("Skipping Foundry UI removal ...")
            return

        try:
            Logger.print_status("Removing Foundry UI ...")

            if FOUNDRY_DIR.exists():
                shutil.rmtree(FOUNDRY_DIR)
                Logger.print_ok(f"Removed repository at '{FOUNDRY_DIR}'.")

            remove_with_sudo(
                [
                    FOUNDRY_WEB_ROOT,
                    NGINX_SITES_AVAILABLE.joinpath(FOUNDRY_CFG_NAME),
                    NGINX_SITES_ENABLED.joinpath(FOUNDRY_CFG_NAME),
                ]
            )
            cmd_sysctl_service("nginx", "restart")

            Logger.print_ok("Foundry UI removed!")
        except Exception as e:
            Logger.print_error(f"Error during Foundry UI removal: {e}")

    def _prompt_install_config(self) -> dict | None:
        port = get_number_input(
            "On which port should Foundry UI run",
            min_value=80,
            default=DEFAULT_PORT,
            allow_go_back=True,
        )
        if port is None:
            return None

        repo_url = get_string_input(
            "Foundry UI git repository",
            allow_special_chars=True,
            default=FOUNDRY_REPO,
        )
        branch = get_string_input(
            "Foundry UI git branch",
            regex=r"^[A-Za-z0-9._/-]+$",
            default=FOUNDRY_BRANCH,
        )
        moonraker_host = get_string_input(
            "Moonraker host or IP",
            regex=r"^[A-Za-z0-9._-]+$",
            default=DEFAULT_MOONRAKER_HOST,
        )
        moonraker_port = get_number_input(
            "Moonraker port",
            min_value=1,
            max_value=65535,
            default=DEFAULT_MOONRAKER_PORT,
        )
        enable_writes = get_confirm(
            "Enable printer write actions in Foundry UI",
            default_choice=True,
        )
        printer_id = get_string_input(
            "Printer ID label",
            regex=r"^[A-Za-z0-9._-]+$",
            default=DEFAULT_PRINTER_ID,
        )
        printer_name = get_string_input(
            "Printer display name",
            allow_special_chars=True,
            default=DEFAULT_PRINTER_NAME,
        )
        printer_host = get_string_input(
            "Printer host label",
            allow_special_chars=True,
            default=DEFAULT_PRINTER_HOST,
        )

        refresh_existing = True
        if FOUNDRY_DIR.exists():
            refresh_existing = get_confirm(
                f"Refresh the existing checkout at '{FOUNDRY_DIR}'",
                default_choice=True,
            )

        return {
            "repo_url": repo_url,
            "branch": branch,
            "port": port,
            "moonraker_host": moonraker_host,
            "moonraker_port": moonraker_port,
            "enable_writes": bool(enable_writes),
            "printer_id": printer_id,
            "printer_name": printer_name,
            "printer_host": printer_host,
            "refresh_existing": bool(refresh_existing),
        }

    def _ensure_nodejs(self) -> None:
        current_major = self._get_node_major_version()
        if current_major is not None and current_major >= MIN_NODE_MAJOR:
            Logger.print_info(f"Using installed Node.js v{current_major}.")
            return

        Logger.print_status("Installing Node.js ...")
        self._run_command(
            ["bash", "-lc", f"curl -fsSL https://deb.nodesource.com/setup_{TARGET_NODE_MAJOR}.x | sudo -E bash -"],
            "Configuring NodeSource repository",
        )
        self._run_command(
            ["sudo", "apt-get", "install", "-y", "nodejs"],
            "Installing Node.js",
        )

        current_major = self._get_node_major_version()
        if current_major is None or current_major < MIN_NODE_MAJOR:
            raise RuntimeError("Node.js installation did not produce a usable version.")

        Logger.print_ok(f"Node.js v{current_major} ready.")

    def _get_node_major_version(self) -> int | None:
        try:
            result = run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            match = re.match(r"^v(\d+)", result.stdout.strip())
            if match:
                return int(match.group(1))
            return None
        except (CalledProcessError, FileNotFoundError):
            return None

    def _sync_repository(
        self, repo_url: str, branch: str, refresh_existing: bool
    ) -> None:
        if FOUNDRY_DIR.exists() and not FOUNDRY_DIR.joinpath(".git").exists():
            if refresh_existing:
                Logger.print_warn(
                    f"'{FOUNDRY_DIR}' exists but is not a git repository. "
                    "Removing it before cloning Foundry UI."
                )
                shutil.rmtree(FOUNDRY_DIR)
            else:
                raise RuntimeError(
                    f"'{FOUNDRY_DIR}' exists but is not a git repository."
                )

        if not FOUNDRY_DIR.exists():
            self._run_command(
                [
                    "git",
                    "clone",
                    "--filter=blob:none",
                    repo_url,
                    FOUNDRY_DIR.as_posix(),
                ],
                "Cloning Foundry UI repository",
            )
        else:
            if refresh_existing:
                self._run_command(
                    ["git", "remote", "set-url", "origin", repo_url],
                    "Updating Foundry UI origin",
                    cwd=FOUNDRY_DIR,
                )
                self._run_command(
                    ["git", "fetch", "origin"],
                    "Fetching Foundry UI updates",
                    cwd=FOUNDRY_DIR,
                )
            else:
                Logger.print_info("Reusing existing Foundry UI checkout without fetch.")

        self._run_command(
            ["git", "checkout", branch],
            f"Checking out branch '{branch}'",
            cwd=FOUNDRY_DIR,
        )
        if refresh_existing:
            self._run_command(
                ["git", "pull", "--ff-only", "origin", branch],
                f"Pulling branch '{branch}'",
                cwd=FOUNDRY_DIR,
            )

    def _write_env_file(self, install_config: dict) -> None:
        Logger.print_status("Writing production environment file ...")
        env_lines = [
            "VITE_FOUNDRY_DEV_MOONRAKER_ENABLED=true",
            "VITE_FOUNDRY_DEV_MOONRAKER_URL=/moonraker",
            "VITE_FOUNDRY_DEV_MOONRAKER_WS_URL=/moonraker/websocket",
            (
                "VITE_FOUNDRY_DEV_ENABLE_WRITES="
                + ("true" if install_config["enable_writes"] else "false")
            ),
            f"VITE_FOUNDRY_DEV_PRINTER_ID={install_config['printer_id']}",
            f"VITE_FOUNDRY_DEV_PRINTER_NAME={install_config['printer_name']}",
            f"VITE_FOUNDRY_DEV_PRINTER_HOST={install_config['printer_host']}",
        ]
        env_path = FOUNDRY_DIR.joinpath(".env.production")
        env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
        Logger.print_ok("Production environment file written.")

    def _install_npm_dependencies(self) -> None:
        if FOUNDRY_DIR.joinpath("package-lock.json").exists():
            self._run_command(
                ["npm", "ci"],
                "Installing npm dependencies",
                cwd=FOUNDRY_DIR,
            )
        else:
            self._run_command(
                ["npm", "install"],
                "Installing npm dependencies",
                cwd=FOUNDRY_DIR,
            )

    def _build_app(self) -> None:
        self._run_command(
            ["npm", "run", "build"],
            "Building Foundry UI",
            cwd=FOUNDRY_DIR,
        )

    def _deploy_dist(self) -> None:
        dist_dir = FOUNDRY_DIR.joinpath("dist")
        if not dist_dir.exists():
            raise FileNotFoundError("Build output directory 'dist' was not created.")

        self._run_command(
            ["sudo", "mkdir", "-p", FOUNDRY_WEB_ROOT.as_posix()],
            "Creating web root directory",
        )
        self._run_command(
            [
                "sudo",
                "rsync",
                "-a",
                "--delete",
                f"{dist_dir.as_posix()}/",
                f"{FOUNDRY_WEB_ROOT.as_posix()}/",
            ],
            "Deploying Foundry UI assets",
        )

    def _create_nginx_config(self, install_config: dict) -> None:
        Logger.print_status("Creating nginx config for Foundry UI ...")
        generate_nginx_cfg_from_template(
            FOUNDRY_CFG_NAME,
            template_src=MODULE_PATH.joinpath(f"assets/{FOUNDRY_CFG_NAME}"),
            ROOT_DIR=FOUNDRY_WEB_ROOT,
            PORT=install_config["port"],
            MOONRAKER_HOST=install_config["moonraker_host"],
            MOONRAKER_PORT=install_config["moonraker_port"],
        )
        create_symlink(
            NGINX_SITES_AVAILABLE.joinpath(FOUNDRY_CFG_NAME),
            NGINX_SITES_ENABLED.joinpath(FOUNDRY_CFG_NAME),
            True,
        )
        set_nginx_permissions()
        cmd_sysctl_service("nginx", "restart")
        Logger.print_ok("nginx config ready.")

    def _write_manifest(self, install_config: dict) -> None:
        manifest = {
            "repo_url": install_config["repo_url"],
            "branch": install_config["branch"],
            "port": install_config["port"],
            "moonraker_host": install_config["moonraker_host"],
            "moonraker_port": install_config["moonraker_port"],
            "enable_writes": install_config["enable_writes"],
            "printer_id": install_config["printer_id"],
            "printer_name": install_config["printer_name"],
            "printer_host": install_config["printer_host"],
        }
        FOUNDRY_MANIFEST.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

    def _read_manifest(self) -> dict | None:
        if not FOUNDRY_MANIFEST.exists():
            return None

        with open(FOUNDRY_MANIFEST, "r", encoding="utf-8") as manifest_file:
            return json.load(manifest_file)

    def _run_command(
        self, command: list[str], status: str, cwd: Path | None = None
    ) -> None:
        Logger.print_status(f"{status} ...")
        try:
            run(command, cwd=cwd, stderr=PIPE, check=True)
            Logger.print_ok("OK!")
        except CalledProcessError as e:
            details = e.stderr.decode() if e.stderr else str(e)
            raise RuntimeError(details.strip()) from e

    def _get_local_ipv4(self) -> str:
        try:
            result = run(
                ["hostname", "-I"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip().split()[0]
        except (CalledProcessError, IndexError):
            return "localhost"
