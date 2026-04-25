# Foundry UI KIAUH Extension

This repository packages Foundry UI as a KIAUH extension.

KIAUH discovers extensions from local folders under `kiauh/extensions`, so this
repo includes a helper script that installs the `foundry_ui` extension folder
into an existing KIAUH checkout without requiring a permanent fork of KIAUH.

## What It Does

- adds `Foundry UI` to the KIAUH `Extensions` menu
- installs Linux dependencies needed to build and serve Foundry UI
- installs or upgrades Node.js when the host version is too old
- clones the Foundry UI repository
- writes a production `.env.production` for Moonraker proxying
- builds the app with `npm`
- deploys the static site to `/var/www/foundryui`
- creates an nginx site config that proxies `/moonraker` to Moonraker
- supports update and removal from the same KIAUH extension menu

## Install The Extension Into KIAUH

```bash
git clone <this-repo-url> foundry-kiauh-extension
cd foundry-kiauh-extension
chmod +x install_into_kiauh.sh
./install_into_kiauh.sh ~/kiauh
```

If your KIAUH checkout lives somewhere else, pass that path instead.

After that:

```bash
cd ~/kiauh
./kiauh.sh
```

Then open:

```text
Extensions -> Foundry UI -> Install
```

## Defaults Used By The Installer

- Foundry repo: `https://github.com/devinsheppard/foundry-ui.git`
- Default branch: `codex/step-10-2-live-moonraker-bootstrap`
- App checkout path: `~/foundry-ui`
- Web root: `/var/www/foundryui`
- nginx config: `foundry-ui.conf`
- Default listen port: `7137`
- Default Moonraker upstream: `127.0.0.1:7125`

The installer prompts before using those values so you can override them.

## Update And Remove

Once the extension is installed into KIAUH, use the same submenu:

```text
Extensions -> Foundry UI -> Update
Extensions -> Foundry UI -> Remove
```

Update rebuilds and redeploys the existing installation using the saved install
manifest from the first run.

## Development Workflow

To reinstall the extension into a local KIAUH checkout after edits:

```bash
./install_into_kiauh.sh ~/kiauh
```

To remove only the extension loader files from KIAUH:

```bash
chmod +x uninstall_from_kiauh.sh
./uninstall_from_kiauh.sh ~/kiauh
```
