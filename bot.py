import discord
import os
import requests
import dotenv
from discord.ext import commands, tasks
import sqlite3

dotenv.load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='f.', intents=intents , help_command=None)

# da link to tetrio api
RANK_URL = "https://ch.tetr.io/api/users/{}/summaries/league"
DISCORD_ID_URL = "https://ch.tetr.io/api/users/{}"

# rank-role
rank_to_role = {
    'z': 'Unranked (lmao)',
    'd': 'D Rank',
    'd+': 'D+ Rank',
    'c-': 'C- Rank',
    'c': 'C Rank',
    'c+': 'C+ Rank',
    'b-': 'B- Rank',
    'b': 'B Rank',
    'b+': 'B+ Rank',
    'a-': 'A- Rank',
    'a': 'A Rank',
    'a+': 'A+ Rank',
    's-': 'S- Rank',
    's': 'S Rank',
    's+': 'S+ Rank',
    'ss': 'SS Rank',
    'u': 'U Rank',
    'x': 'X Rank',
    'x+': 'X+ Rank'
}

ALLOWED_CHANNEL_ID = [1170631780232077424, 857080587726487563]  #first one is bot channel in TAC, second is in my private server
ALLOWED_GUILDS_ID = [946060638231359588] #TAC server id

def connect_db():
    return sqlite3.connect('user-data.db')

def create_db():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            discord_id TEXT PRIMARY KEY,
            tetrio_username TEXT,
            rank TEXT
        )
    ''')
    conn.commit()
    conn.close()


def get_user_rank(username):
    url = RANK_URL.format(username.lower())
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            return data['data']
    return None


def get_discord_id(username):
    url = DISCORD_ID_URL.format(username.lower())
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            return data['data']['connections']['discord']['id']
    return None

async def remove_all_rank_roles(member, guild):
    """Remove all rank roles from a member."""
    for rank_name in rank_to_role.values():
        role = discord.utils.get(guild.roles, name=rank_name)
        if role and role in member.roles:
            await member.remove_roles(role)

@bot.command()
async def link(ctx, username: str):
    if ctx.guild.id not in ALLOWED_GUILDS_ID:
        await ctx.send("This bot is not usable in this server.")
        return
    if ctx.channel.id not in ALLOWED_CHANNEL_ID:
        await ctx.send(f"Wrong channel! Please use #{ctx.guild.get_channel(ALLOWED_CHANNEL_ID[0]).name}.")
        return

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT discord_id FROM users WHERE discord_id = ?", (str(ctx.author.id),))
    existing_user = cursor.fetchone()

    if existing_user:
        await ctx.send("Your account is already linked. Use `f.rank_update` to refresh your rank.")
        conn.close()
        return

    user_info = get_user_rank(username)
    if user_info:
        rank = user_info.get('rank')
        discord_id_from_tetrio = get_discord_id(username)

        if discord_id_from_tetrio == str(ctx.author.id):
            cursor.execute("INSERT INTO users (discord_id, tetrio_username, rank) VALUES (?, ?, ?)",
                           (str(ctx.author.id), username, rank))
            conn.commit()
            conn.close()

            
            rank_role = rank_to_role.get(rank)
            if rank_role:
                role = discord.utils.get(ctx.guild.roles, name=rank_role)
                if role:
                    await remove_all_rank_roles(ctx.author, ctx.guild)
                    await ctx.author.add_roles(role)
                    await ctx.send(f"Account linked successfully! Rank role '{rank_role}' assigned.")
                else:
                    await ctx.send(f"Role '{rank_role}' not found. Contact an admin.")
            else:
                await ctx.send(f"Rank '{rank}' is not recognized.")
        else:
            await ctx.send("Your Discord ID does not match the provided Tetr.io username.")
    else:
        await ctx.send(f"Could not fetch rank data for '{username}'.")
        conn.close()

@bot.command()
async def rank_update(ctx):
    if ctx.guild.id not in ALLOWED_GUILDS_ID:
        await ctx.send("This bot is not usable in this server.")
        return
    if ctx.channel.id not in ALLOWED_CHANNEL_ID:
        await ctx.send(f"Wrong channel! Please use #{ctx.guild.get_channel(ALLOWED_CHANNEL_ID[0]).name}.")
        return

    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT tetrio_username, rank FROM users WHERE discord_id = ?", (str(ctx.author.id),))
    user_data = cursor.fetchone()

    if not user_data:
        await ctx.send("Your account is not linked yet. Use `f.link <username>` first.")
        conn.close()
        return

    tetrio_username, current_rank = user_data
    user_info = get_user_rank(tetrio_username)

    if user_info:
        new_rank = user_info.get('rank')
        if new_rank != current_rank:
            await remove_all_rank_roles(ctx.author, ctx.guild)  

            rank_role = rank_to_role.get(new_rank)
            if rank_role:
                new_role = discord.utils.get(ctx.guild.roles, name=rank_role)
                if new_role:
                    await ctx.author.add_roles(new_role)
                    await ctx.send(f"Rank updated! New rank role '{rank_role}' assigned.")
                else:
                    await ctx.send(f"New rank role '{rank_role}' not found. Contact an admin.")
            
            
            cursor.execute("UPDATE users SET rank = ? WHERE discord_id = ?", (new_rank, str(ctx.author.id)))
            conn.commit()
        else:
            await ctx.send("Your rank has not changed.")
    else:
        await ctx.send("Could not fetch your rank data. Please try again later.")
    
    conn.close()

@tasks.loop(minutes=5)
async def update_rank_roles():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT discord_id, tetrio_username, rank FROM users")
    users = cursor.fetchall()

    for discord_id, tetrio_username, current_rank in users:
        try:
            user_info = get_user_rank(tetrio_username)
            if user_info:
                new_rank = user_info.get('rank')
                if new_rank and new_rank != current_rank:
                    guild = bot.guilds[0]
                    member = guild.get_member(int(discord_id))

                    if member:
                        await remove_all_rank_roles(member, guild)
                        rank_role = rank_to_role.get(new_rank)
                        if rank_role:
                            new_role = discord.utils.get(guild.roles, name=rank_role)
                            if new_role:
                                await member.add_roles(new_role)
                                await guild.get_channel(ALLOWED_CHANNEL_ID[0]).send(
                                    f"{member.mention}'s rank updated to '{rank_role}'."
                                )

                        cursor.execute("UPDATE users SET rank = ? WHERE discord_id = ?", (new_rank, discord_id))
                        conn.commit()
        except Exception as e:
            print(f"Error updating rank for {discord_id}: {e}")

    conn.close()

def migrate_db():
    """Handles database schema migrations, ensuring necessary columns exist."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN tetrio_username TEXT")
    except sqlite3.OperationalError:
        print("Column 'tetrio_username' already exists.")
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN rank TEXT")
    except sqlite3.OperationalError:
        print("Column 'rank' already exists.")
    
    conn.commit()
    conn.close()
    print("Database migration completed.")


@bot.command()
async def help(ctx):
    if ctx.guild.id not in ALLOWED_GUILDS_ID:
        await ctx.send("This bot is not usable in this server.")
        return
    if ctx.channel.id not in ALLOWED_CHANNEL_ID:
        allowed_channel = ctx.guild.get_channel(ALLOWED_CHANNEL_ID[0])
        if allowed_channel:
            await ctx.send(f"Wrong channel! Please use {f'<#{allowed_channel.id}>'}.")
        else:
            await ctx.send("Could not find the allowed channel. Please contact an admin.")
        return

    help_message = """
```Description: The bot assigns rank roles based on your Tetr.io rank and updates them periodically. Use the f.link command to link your Tetr.io account first.

Commands: 
f.help - Show this help message.
f.link <username> - Link your Tetr.io account to get your rank updated automatically. 
f.rank_update - Refresh your rank manually (if you can't wait lol). 

For issues or suggestions, contact funli.```
"""
    await ctx.send(help_message)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    create_db()
    migrate_db()  
    update_rank_roles.start()


# Run the bot
bot.run(os.getenv('TOKEN'))
