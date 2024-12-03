from dotenv import load_dotenv
import discord
import sqlite3
import os
from discord.ext import commands, tasks
import requests


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='f.', intents = intents, help_command = None)

LEAGUE_URL = "https://ch.tetr.io/api/users/{}/summaries/league"
USER_URL = "https://ch.tetr.io/api/users/{}"
def api_request(template, value):
    url = template.format(value)
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            return data['data']
    return None

async def remove_all_rank_roles(member, guild):
    for rank_name in rank_to_role.values():
        role = discord.utils.get(guild.roles, name=rank_name)
        if role and role in member.roles:
            await member.remove_roles(role)
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

def connect_db():
    return sqlite3.connect('user-data.db')

def create_db():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            discord_id TEXT PRIMARY KEY,
            tetrio_username TEXT,
            rank TEXT,
            tr REAL,
            apm REAL,
            vs REAL,
            pps REAL
        )
    ''')
    conn.commit()
    conn.close()

async def remove_all_rank_roles(member, guild):
    """Remove all rank roles from a member."""
    for rank_name in rank_to_role.values():
        role = discord.utils.get(guild.roles, name=rank_name)
        if role and role in member.roles:
            await member.remove_roles(role)

@bot.command()
async def link(ctx, username: str):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT discord_id FROM users WHERE discord_id = ?", (str(ctx.author.id),))
        existing_user = cursor.fetchone()

        if existing_user:
            await ctx.send("Your account is already linked. Use 'f.rank_update' to refresh your rank.")
            return
        
        user = api_request(USER_URL, username)
        if not user:
            await ctx.send(f"User '{username}' not found")
            return

        connections = user['connections']
        if 'discord' not in connections:
            await ctx.send("Your TETR.IO account is not linked to a Discord account. This is needed for verification.")
            return

        if connections['discord']['id'] != str(ctx.author.id):
            await ctx.send("Your Discord ID does not match the provided TETR.IO username.")
            return

        league_info = api_request(LEAGUE_URL, username)
        if not league_info:
            await ctx.send(f"Could not fetch rank data for '{username}'.")
            return
        
        rank = league_info.get("rank")
        tr = league_info.get("tr")
        apm = league_info.get("apm")
        vs = league_info.get("vs")
        pps = league_info.get("pps")
        
        cursor.execute("INSERT INTO users (discord_id, tetrio_username, rank, tr, apm, vs, pps) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (str(ctx.author.id), username, rank, tr, apm, vs, pps))
        
    rank_role = rank_to_role.get(rank)
    if not rank_role:
        await ctx.send(f"Rank '{rank}' is not recognized.")
        return
    
    role = discord.utils.get(ctx.guild.roles, name = rank_role)
    if not role:
        await ctx.send(f"Role '{rank_role}' not found. Please contact and admin.")
        return
    await remove_all_rank_roles(ctx.author, ctx.guild)
    await ctx.author.add_roles(role)
    await ctx.send(f"Account linked successfully! Rank role '{rank_role}' assigned.")

@bot.command()
async def link_other(ctx, discord_name: str, tetrio_name: str):
    members = ctx.guild.members
    member = None
    for m in members:
        if m.name == discord_name:
            member = m
            break
    if not member:
        await ctx.send(f"No user '{discord_name}' in this server.")
        return
    # might aswell 've done for other function but 2lazy4this
    discord_id = str(member.id)
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT discord_id FROM users WHERE discord_id = {discord_id}")
        existing_user = cursor.fetchone()

        if existing_user:
            await ctx.send("Your account is already linked. Use 'f.rank_update' to refresh your rank.")
            return
        
        user = api_request(USER_URL, tetrio_name)
        if not user:
            await ctx.send(f"User '{tetrio_name}' not found")
            return

        connections = user['connections']
        if 'discord' not in connections:
            await ctx.send("Your TETR.IO account is not linked to a Discord account. This is needed for verification.")
            return

        if connections['discord']['id'] != discord_id:
            await ctx.send("Your Discord ID does not match the provided TETR.IO username.")
            return

        league_info = api_request(LEAGUE_URL, tetrio_name)
        if not league_info:
            await ctx.send(f"Could not fetch rank data for '{tetrio_name}'.")
            return
        
        rank = league_info.get("rank")
        tr = league_info.get("tr")
        apm = league_info.get("apm")
        vs = league_info.get("vs")
        pps = league_info.get("pps")
        
        cursor.execute("INSERT INTO users (discord_id, tetrio_username, rank, tr, apm, vs, pps) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (discord_id, tetrio_name, rank, tr, apm, vs, pps))
        
    rank_role = rank_to_role.get(rank)
    if not rank_role:
        await ctx.send(f"Rank '{rank}' is not recognized.")
        return
    
    role = discord.utils.get(ctx.guild.roles, name = rank_role)
    if not role:
        await ctx.send(f"Role '{rank_role}' not found. Please contact and admin.")
        return
    await remove_all_rank_roles(ctx.author, ctx.guild)
    await ctx.author.add_roles(role)
    await ctx.send(f"Account linked successfully! Rank role '{rank_role}' assigned.")

lbtypes = ["tr", "apm", "vs", "pps"]

def leaderboard(lbtype, fields, value_func):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(f"SELECT rank, tetrio_username, {','.join(fields)} FROM users" + (f" ORDER BY {lbtype} DESC" if len(fields) == 1 else ""))
    users = cursor.fetchall()
    if len(fields) > 1:
        users = sorted(users, key = value_func, reverse = True)

    conn.close()

    string = f"{lbtype} leaderboard: ```"
    for i in range(len(users)):
        user = users[i]
        string += "{:<3}{:<3}{:<20}{:.2f}\n".format(i+1, user[0], user[1], value_func(user))
    string += "```"
    return string

@bot.command()
async def lb(ctx, lbtype: str):
    if lbtype in lbtypes:
        value_func = lambda user: user[2]
        lbstring = leaderboard(lbtype, [lbtype], value_func)
    elif lbtype == "app":
        value_func = lambda user: user[2] / user[3] / 60
        lbstring = leaderboard(lbtype, ["apm", "pps"], value_func)
    elif lbtype == "vs/apm":
        value_func = lambda user: user[2] / user[3]
        lbstring = leaderboard(lbtype, ["vs", "apm"], value_func)
    else:
        await ctx.send(f"'{lbtype}' is not a valid leaderboard type")
        return
    await ctx.send(lbstring)

TAC_GUILD_ID = 946060638231359588

@tasks.loop(minutes=5)
async def update_rank_roles():
    conn = connect_db()
    cursor = conn.cursor()
    try:
        print('Change logs:\n')
        cursor.execute("SELECT discord_id, tetrio_username, rank FROM users")
        users = cursor.fetchall()

        guild_id = TAC_GUILD_ID
        guild = bot.get_guild(guild_id)
        if not guild:
            print(f"Error: Guild with ID {guild_id} not found.")
            return

        # Check each user in the database
        for discord_id, tetrio_username, rank in users:
            try:
                current_rank = rank
                league_info = api_request(LEAGUE_URL, tetrio_username)
                if not league_info:
                    print(f"Failed to fetch rank data for username '{tetrio_username}'.\n")
                    continue

                new_rank = league_info.get('rank')
                print(f"*Checking rank for {tetrio_username}:")
                print(f"Current rank in database: '{current_rank}'")
                print(f"Fetched rank from Tetr.io: '{new_rank}'")

                # Step 1: Compare the ranks
                if new_rank != current_rank:  # If the ranks are different, update the database and role
                    member = guild.get_member(int(discord_id)) or await guild.fetch_member(int(discord_id))
                    if not member:
                        continue

                    # Step 2: Remove all existing rank roles first (before assigning new role)
                    await remove_all_rank_roles(member, guild)

                    # Update the database with the new rank
                    cursor.execute(
                        "UPDATE users SET rank = ? WHERE discord_id = ?",
                        (new_rank, discord_id)
                    )
                    print(f"Updated rank for {tetrio_username} (<@{discord_id}>) to {new_rank}.")

                    # Assign the new role based on the new rank
                    new_role_name = rank_to_role.get(new_rank)
                    if not new_role_name:
                        print(f"Warning: No role mapping for rank '{new_rank}'.")
                        continue

                    new_role = discord.utils.get(guild.roles, name=new_role_name)
                    if not new_role:
                        print(f"Warning: Role '{new_role_name}' not found in guild.")
                        continue

                    if new_role not in member.roles:
                        print(f"Assigning new rank role '{new_role_name}' to {member.name}")
                        await member.add_roles(new_role)
                    else:
                        print(f"{member.name} already has the correct role '{new_role_name}'.")
                else:  # Step 2: If the rank matches, check if the role is correct
                    member = guild.get_member(int(discord_id)) or await guild.fetch_member(int(discord_id))
                    if not member:
                        continue

                    current_role_name = rank_to_role.get(current_rank)
                    current_role = discord.utils.get(guild.roles, name=current_role_name)
                    if current_role and current_role not in member.roles:
                        print(f"{member.name} has the wrong role. Assigning '{current_role_name}' role.")
                        await member.add_roles(current_role)
                    else:
                        print(f"{member.name} already has the correct role '{current_role_name}'.")
                    # Ensure that the member only has one rank role
                    await ensure_single_rank_role(member, guild, current_rank)
            except Exception as e:
                print(f"Error updating rank for Discord ID {discord_id}: {e}.\n")

        conn.commit()

    except Exception as e:
        print(f"Error during rank update: {e}")
    finally:
        conn.close()
        print(' ')

def add_column(cursor, name, sqltype):
    try:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {name} {sqltype}")
    except sqlite3.OperationalError:
        print(f"Column '{name}' already exists.")

def migrate_db():
    """Handles database schema migrations, ensuring necessary columns exist."""
    conn = connect_db()
    cursor = conn.cursor()
    print(' ')

    add_column(cursor, "tetrio_username", "TEXT")
    add_column(cursor, "rank",            "TEXT")
    add_column(cursor, "tr",              "REAL")
    add_column(cursor, "apm",             "REAL")
    add_column(cursor, "vs",              "REAL")
    add_column(cursor, "pps",             "REAL")
    
    conn.commit()
    conn.close()
    print("Database migration completed.\n")

@bot.command()
async def help(ctx):
    print('helped')
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
    create_db()
    migrate_db()
    # update_rank_roles.start()
    print('Logged in.\nv1.3 test')

load_dotenv()
bot.run(os.getenv("TOKEN"))
