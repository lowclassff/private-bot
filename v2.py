# v2.py - The main script for the advanced Discord VPS creator bot.
# This bot uses Firebase Firestore to manage user resources and VPS state.

import os
import subprocess
import time
import asyncio
from dotenv import load_dotenv
import discord
from discord import app_commands
import firebase_admin
from firebase_admin import credentials, firestore, auth

# Load credentials from .env file
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID_STR = os.getenv('GUILD_ID')
ADMIN_ID_STR = os.getenv('ADMIN_ID')
HOST_IP = os.getenv('HOST_IP')

# Initialize Firebase
if not firebase_admin._apps:
    firebaseConfig = {
        "apiKey": "dummy_api_key",
        "authDomain": "dummy_auth_domain",
        "projectId": "dummy_project_id",
        "storageBucket": "dummy_storage_bucket",
        "messagingSenderId": "dummy_messaging_sender_id",
        "appId": "dummy_app_id",
        "measurementId": "dummy_measurement_id"
    }
    cred = credentials.Certificate("firebase-credentials.json")
    firebase_admin.initialize_app(cred, {
        'projectId': firebaseConfig['projectId']
    })

db = firestore.client()

if not all([DISCORD_TOKEN, GUILD_ID_STR, ADMIN_ID_STR, HOST_IP]):
    print("Error: Missing one or more environment variables in the .env file.")
    exit(1)

GUILD_ID = discord.Object(id=int(GUILD_ID_STR))
ADMIN_ID = int(ADMIN_ID_STR)

class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.tree.sync(guild=GUILD_ID)
        print('Slash commands synced.')

# Define the intents needed for the bot to function
intents = discord.Intents.default()
client = MyClient(intents=intents)

# --- Utility Functions ---
def is_admin(user_id):
    return user_id == ADMIN_ID

async def get_user_vps_slots(user_id):
    doc_ref = db.collection('users').document(str(user_id))
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get('vps_slots', 0)
    return 0

async def find_available_vps_id(user_id):
    query = db.collection('vps').where('user_id', '==', str(user_id)).where('status', '==', 'available').limit(1)
    docs = query.get()
    if docs:
        return docs[0].id
    return None

async def run_docker_command(command_list, interaction):
    """Executes a Docker command and handles output."""
    try:
        result = subprocess.run(command_list, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        await interaction.followup.send(f"An error occurred with Docker:\n```{e.stderr}```", ephemeral=True)
        return None
    except Exception as e:
        await interaction.followup.send(f"An unexpected error occurred: ```{e}```", ephemeral=True)
        return None

# --- Slash Commands ---

@client.tree.command(name="create", description="[Admin Only] Allocates VPS slots to a user.", guild=GUILD_ID)
@app_commands.describe(user="The user to grant resources to.", slots="Number of VPS slots.")
async def create(interaction: discord.Interaction, user: discord.Member, slots: int):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return

    user_ref = db.collection('users').document(str(user.id))
    user_ref.set({'vps_slots': slots}, merge=True)
    await interaction.response.send_message(f"Successfully granted {slots} VPS slots to {user.mention}.", ephemeral=True)

@client.tree.command(name="deploy", description="Deploys a new VPS container from an available slot.", guild=GUILD_ID)
async def deploy(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    await interaction.response.send_message("Checking for available VPS slots...", ephemeral=True)
    
    available_vps_id = await find_available_vps_id(user_id)

    if not available_vps_id:
        await interaction.followup.send("You have no available VPS slots. Use `/resources` to check your status.", ephemeral=True)
        return

    await interaction.followup.send("Deploying a new VPS...", ephemeral=True)
    await deploy_container(interaction, "ubuntu-tmate", available_vps_id)

async def deploy_container(interaction: discord.Interaction, image_name: str, vps_id: str):
    """Internal function to deploy a container and update Firestore."""
    container_id = await run_docker_command(["docker", "run", "-d", "--rm", image_name, "tmate", "-F"], interaction)
    if not container_id:
        return

    await asyncio.sleep(5) # Wait for tmate to start

    log_result = await run_docker_command(["docker", "logs", container_id], interaction)
    if not log_result:
        return

    connection_string = None
    for line in log_result.split('\n'):
        if "ssh " in line and HOST_IP in line:
            connection_string = line.strip()
            break

    if connection_string:
        vps_ref = db.collection('vps').document(vps_id)
        vps_ref.set({
            'container_id': container_id,
            'image': image_name,
            'status': 'running',
            'connection_string': connection_string,
            'deployed_at': firestore.SERVER_TIMESTAMP
        }, merge=True)

        embed = discord.Embed(title=f"VPS Deployed! ({image_name}) 🚀", description="Your new VPS is ready.", color=0x4f46e5)
        embed.add_field(name="VPS ID", value=f"```\n{vps_id}\n```", inline=False)
        embed.add_field(name="Connection Command", value=f"```\n{connection_string}\n```", inline=False)
        embed.set_footer(text=f"Use /stop {vps_id} to stop it.")
        
        await interaction.user.send(embed=embed)
        await interaction.followup.send(f"VPS `{vps_id}` is ready. Check your DMs for details!", ephemeral=True)
    else:
        await interaction.followup.send("Failed to get tmate connection string.", ephemeral=True)

@client.tree.command(name="deploy-ubuntu", description="[Admin Only] Deploys a specific Ubuntu VPS.", guild=GUILD_ID)
@app_commands.describe(vps_id="The Firestore ID of the VPS to deploy.")
async def deploy_ubuntu_admin(interaction: discord.Interaction, vps_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return
    
    await interaction.response.send_message(f"Deploying Ubuntu VPS with ID `{vps_id}`...", ephemeral=True)
    await deploy_container(interaction, "ubuntu-tmate", vps_id)

@client.tree.command(name="deploy-debian", description="[Admin Only] Deploys a specific Debian VPS.", guild=GUILD_ID)
@app_commands.describe(vps_id="The Firestore ID of the VPS to deploy.")
async def deploy_debian_admin(interaction: discord.Interaction, vps_id: str):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return
    
    await interaction.response.send_message(f"Deploying Debian VPS with ID `{vps_id}`...", ephemeral=True)
    await deploy_container(interaction, "debian-tmate", vps_id)

@client.tree.command(name="stop", description="Stops a running VPS container.", guild=GUILD_ID)
@app_commands.describe(vps_id="The ID of the VPS to stop.")
async def stop(interaction: discord.Interaction, vps_id: str):
    vps_ref = db.collection('vps').document(vps_id)
    vps_doc = vps_ref.get()

    if not vps_doc.exists or vps_doc.to_dict().get('user_id') != str(interaction.user.id):
        await interaction.response.send_message("You do not own this VPS or it does not exist.", ephemeral=True)
        return

    container_id = vps_doc.to_dict().get('container_id')
    await interaction.response.send_message(f"Attempting to stop VPS `{vps_id}`...", ephemeral=True)

    await run_docker_command(["docker", "stop", container_id], interaction)
    vps_ref.update({'status': 'stopped'})
    await interaction.followup.send(f"VPS `{vps_id}` has been stopped successfully.", ephemeral=True)

@client.tree.command(name="start", description="Starts a stopped VPS container.", guild=GUILD_ID)
@app_commands.describe(vps_id="The ID of the VPS to start.")
async def start(interaction: discord.Interaction, vps_id: str):
    await interaction.response.send_message("This command is not yet fully implemented. Please wait for an update.", ephemeral=True)

@client.tree.command(name="restart", description="Restarts a running VPS container.", guild=GUILD_ID)
@app_commands.describe(vps_id="The ID of the VPS to restart.")
async def restart(interaction: discord.Interaction, vps_id: str):
    await interaction.response.send_message("This command is not yet fully implemented. Please wait for an update.", ephemeral=True)

@client.tree.command(name="reinstall", description="Reinstalls the OS on a VPS.", guild=GUILD_ID)
@app_commands.describe(vps_id="The ID of the VPS to reinstall.")
async def reinstall(interaction: discord.Interaction, vps_id: str):
    await interaction.response.send_message("This command is not yet fully implemented. Please wait for an update.", ephemeral=True)

@client.tree.command(name="resources", description="Displays your available VPS resources.", guild=GUILD_ID)
async def resources(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    vps_slots = await get_user_vps_slots(user_id)
    
    await interaction.response.send_message(f"You have **{vps_slots}** available VPS slots.", ephemeral=True)

@client.tree.command(name="sendvps", description="[Admin Only] Sends VPS connection details to a user.", guild=GUILD_ID)
@app_commands.describe(vps_id="The ID of the VPS to send.", user="The user to send the VPS to.")
async def sendvps(interaction: discord.Interaction, vps_id: str, user: discord.Member):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return
    
    vps_ref = db.collection('vps').document(vps_id)
    vps_doc = vps_ref.get()
    
    if not vps_doc.exists:
        await interaction.response.send_message(f"VPS with ID `{vps_id}` does not exist.", ephemeral=True)
        return
        
    vps_data = vps_doc.to_dict()
    connection_string = vps_data.get('connection_string', 'Not available')
    
    embed = discord.Embed(title=f"VPS Received! ({vps_data.get('image', 'N/A')}) 🎁", description="A new VPS has been sent to you!", color=0x4f46e5)
    embed.add_field(name="VPS ID", value=f"```\n{vps_id}\n```", inline=False)
    embed.add_field(name="Connection Command", value=f"```\n{connection_string}\n```", inline=False)
    
    try:
        await user.send(embed=embed)
        vps_ref.update({'user_id': str(user.id)})
        await interaction.response.send_message(f"VPS `{vps_id}` has been sent to {user.mention}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Could not DM the user. They may have DMs disabled.", ephemeral=True)

@client.tree.command(name="node", description="[Admin Only] Placeholder for node management.", guild=GUILD_ID)
async def node(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return
    await interaction.response.send_message("This is a placeholder for a more advanced node management system.", ephemeral=True)

@client.tree.command(name="nodedim", description="[Admin Only] Placeholder for node dimensions.", guild=GUILD_ID)
async def nodedim(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return
    await interaction.response.send_message("This is a placeholder for a more advanced node management system.", ephemeral=True)

@client.tree.command(name="sharedipv4", description="[Admin Only] Placeholder for shared IPv4.", guild=GUILD_ID)
async def sharedipv4(interaction: discord.Interaction):
    if not is_admin(interaction.user.id):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return
    await interaction.response.send_message("This is a placeholder for network configuration and shared IPs.", ephemeral=True)

if __name__ == '__main__':
    if not os.path.exists("venv"):
        subprocess.run(["python3", "-m", "venv", "venv"])
        print("Created virtual environment.")
        
    try:
        import discord
        import dotenv
        import firebase_admin
    except ImportError:
        print("Installing required Python libraries...")
        subprocess.run(["pip3", "install", "discord.py", "python-dotenv", "firebase-admin"])
        print("Installation complete. Please restart the bot.")
        exit(1)
    
    client.run(DISCORD_TOKEN)
