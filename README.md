# Advanced Discord VPS Creator Bot (V3)

This is an advanced private Discord bot for creating and managing VPS containers. It uses Firebase Firestore to manage user resources and track VPS instances.

## New Features
- **Resource Management**: `/create` to allocate resources based on invites and boosts.
- **Full VPS Lifecycle**: `/deploy`, `/stop`, `/start`, `/restart`, `/reinstall` to manage containers.
- **Node Management**: Placeholder commands for `/node` and `/nodedim` for future expansion.
- **Resource Checking**: `/resources` to view available VPS slots.
- **Admin-Only Commands**: Many commands are restricted to a single admin user.

## Commands
- `/create`: **Admin only**. Creates a user profile with resources.
- `/deploy`: Deploys a VPS using an available resource slot.
- `/stop `: Stops a running VPS.
- `/start `: Starts a stopped VPS.
- `/restart `: Restarts a running VPS.
- `/reinstall `: Reinstalls the OS on a VPS.
- `/resources`: Displays the user's available VPS slots.
- `/sharedipv4`: Placeholder command.
- `/node` & `/nodedim`: Placeholder commands for host node management.
- `/deploy-ubuntu `: **Admin only**. Deploys a specific Ubuntu VPS.
- `/deploy-debian `: **Admin only**. Deploys a specific Debian VPS.
- `/sendvps  `: **Admin only**. Sends an existing VPS to a user.

## Setup
Follow the step-by-step instructions in the guide to get your bot running.
