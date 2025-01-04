from dotenv import load_dotenv
import discord
import sqlite3
import os
from discord.ext import commands, tasks
import requests
import traceback

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='f.', intents = intents, help_command = None)

SEARCH_URL = 'https://ch.tetr.io/api/users/search/discord:{}'
USER_URL   = "https://ch.tetr.io/api/users/{}"
LEAGUE_URL = "https://ch.tetr.io/api/users/{}/summaries/league"
SPRINT_URL = "https://ch.tetr.io/api/users/{}/summaries/40l"
BLITZ_URL  = "https://ch.tetr.io/api/users/{}/summaries/blitz"
ZENITH_URL = "https://ch.tetr.io/api/users/{}/summaries/zenith"
ZEN_URL    = "https://ch.tetr.io/api/users/{}/summaries/zen"

TAC_GUILD_ID = 946060638231359588

def api_request(template, value):
    url = template.format(value)
    headers = {
        'User-Agent': 'funli bot',
        'From': 'funli69',
    }
    response = requests.get(url, headers=headers)
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
            past_rank TEXT,
            tr REAL,
            past_tr REAL,
            oldtr REAL,
            apm REAL,
            vs REAL,
            pps REAL,
            sprint REAL,
            blitz INTEGER,
            zenith REAL,
            zenithbest REAL,
            zen INTEGER
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

async def ensure_single_rank_role(member, guild):
    roles = member.roles
    rank_roles = [role for role in roles if role.name in rank_to_role.values()]
    if len(rank_roles) > 1:
        print(f"{member.name} has multiple rank roles. Removing incorrect roles.")
        for role in rank_roles:
            correct_role_name = rank_to_role.get(member.rank) 
            if role.name != correct_role_name:
                await member.remove_roles(role)
                print(f"Removed role {role.name} from {member.name}")
    elif len(rank_roles) == 1:
        print(f"{member.name} already has the correct rank role '{rank_roles[0].name}'.")

def update_user(cursor, discord_id, username):
    league_info = api_request(LEAGUE_URL, username)
    rank      = league_info.get("rank")
    tr        = league_info.get("tr")
    apm       = league_info.get("apm")
    vs        = league_info.get("vs")
    pps       = league_info.get("pps")
    past_tr   = league_info["past"]["1"]["tr"]
    past_rank = league_info["past"]["1"]["rank"]

    record = api_request(SPRINT_URL, username)
    if record:
        sprint = record["record"]["results"]["stats"]["finaltime"]
    else:
        sprint = -1

    record = api_request(BLITZ_URL, username)
    if record:
        blitz = record["record"]["results"]["stats"]["score"]
    else:
        blitz = -1

    record = api_request(ZENITH_URL, username)
    record = record.get("record")
    if record:
        zenith = record["results"]["stats"]["zenith"]["altitude"]
    else:
        zenith = -1

    record = api_request(ZENITH_URL, username)
    record = record["best"].get("record")
    if record:
        zenithbest = record["results"]["stats"]["zenith"]["altitude"]
    else:
        zenithbest = -1

    record = api_request(ZEN_URL, username)
    if record:
        zen = record["level"]
    else:
        zen = -1
    
    cursor.execute("SELECT * FROM users WHERE discord_id == ?", (discord_id,))
    if cursor.fetchone():
        cursor.execute("UPDATE users SET rank = ?, past_rank = ?, tr = ?, past_tr = ?, apm = ?, vs = ?, pps = ?, sprint = ?, blitz = ?, zenith = ?, zenithbest = ?, zen = ? WHERE tetrio_username = ?",
                       (rank, past_rank, tr, past_tr, apm, vs, pps, sprint, blitz, zenith, zenithbest, zen, username))
    else:
        print(username)
        cursor.execute("INSERT INTO users (discord_id, tetrio_username, rank, past_rank, tr, past_tr, apm, vs, pps, sprint, blitz, zenith, zenithbest, zen) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (str(discord_id), username, rank, past_rank, tr, past_tr, apm, vs, pps, sprint, blitz, zenith, zenithbest, zen))

    return rank


@bot.command()
async def link(ctx):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT discord_id FROM users WHERE discord_id = ?", (str(ctx.author.id),))
        existing_user = cursor.fetchone()

        if existing_user:
            await ctx.send("Your account is already linked.")
            return

        user = api_request(SEARCH_URL, ctx.author.id)
        
        if not user:
            await ctx.send(f"User {ctx.author.name} has not connected Discord to TETR.IO.")
            return 
        username = user["user"]["username"]
        rank = update_user(cursor, ctx.author.id, username)

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
async def link_other(ctx, discord_name: str):
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
            await ctx.send(f"Account '{member.name}' is already linked. Use 'f.rank_update' to refresh your rank.")
            return
        
        user = api_request(SEARCH_URL, discord_id)
        username = user["user"]["username"]

        if not user:
            await ctx.send(f"User {member.name} has not connected Discord to TETR.IO.")
            return 
        
        rank = update_user(cursor, discord_id, username)

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
async def link_all(ctx):
    conn = connect_db()
    cursor = conn.cursor()

    guild_id = TAC_GUILD_ID
    guild = bot.get_guild(guild_id)

    count = 0
    for member in guild.members:
        user = api_request(SEARCH_URL, member.id)
        if not user:
            continue 

        username = user["user"]["username"]
        update_user(cursor, member.id, username)
        count += 1
        await ctx.send(f"Account {member.name} linked successfully.")

    await ctx.send(f"Linked {count} members")
    conn.commit()
    conn.close()


lbtypes = ["tr", "past_tr", "apm", "vs", "pps", "sprint", "blitz", "zenith", "zenithbest", "zen"]

def leaderboard(lbtype, fields, value_func, reverse_sort = False):
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute(f"SELECT {'past_rank' if lbtype=='past_tr' else 'rank'}, tetrio_username, {','.join(fields)} FROM users" + (f" ORDER BY {lbtype} {'ASC' if reverse_sort else 'DESC'}" if len(fields) == 1 else ""))
    users = cursor.fetchall()
    users = tuple(filter(lambda fields: all(fields), users))
    if len(fields) > 1:
        users = sorted(users, key = value_func, reverse = not reverse_sort)

    conn.close()

    string = f"{lbtype} leaderboard: ```"
    for i in range(len(users)):
        user = users[i]
        value = value_func(user)
        formatstring = "{:<3}{:<3}{:<20}DNF\n" if value < 0 else  ("{:<3}{:<3}{:<20}{:.2f}\n" if type(value) == float else "{:<3}{:<3}{:<20}{}\n")
        string += formatstring.format(i+1, user[0], user[1], value)
    string += "```"
    return string

@bot.command()
async def lb(ctx, lbtype: str):
    if lbtype in lbtypes:
        # eh
        sprint = lbtype == "sprint"
        value_func = lambda user: (int(user[2]) if lbtype == "tr" else (user[2] / 1000 if sprint else user[2]))
        lbstring = leaderboard(lbtype, [lbtype], value_func, sprint)
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

async def ensure_single_rank_role(member, guild, rank_from_db):
    # Get all roles the member currently has
    roles = member.roles
    rank_roles = [role for role in roles if role.name in rank_to_role.values()]

    if len(rank_roles) > 1:
        print(f"{member.name} has multiple rank roles. Removing incorrect roles.")
        for role in rank_roles:
            # Determine the correct role for this member based on the rank in the database
            correct_role_name = rank_to_role.get(rank_from_db)  # Get the correct role based on the rank
            if role.name != correct_role_name:
                await member.remove_roles(role)
                print(f"Removed role {role.name} from {member.name}")
        print(' ')
    elif len(rank_roles) == 1:
        print("No other rank roles detected.\n")

@tasks.loop(minutes=5)
async def update_users():
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

        for discord_id, tetrio_username, rank in users:
            try:
                current_rank = rank
                new_rank = update_user(cursor, discord_id, tetrio_username)
                print(f"*Checking rank for {tetrio_username}:")
                print(f"Current rank in database: '{current_rank}'")
                print(f"Fetched rank from Tetr.io: '{new_rank}'")

                if new_rank != current_rank:  
                    member = guild.get_member(int(discord_id)) or await guild.fetch_member(int(discord_id))
                    if not member:
                        continue

                    await remove_all_rank_roles(member, guild)

                    cursor.execute(
                        "UPDATE users SET rank = ? WHERE discord_id = ?",
                        (new_rank, discord_id)
                    )
                    print(f"Updated rank for {tetrio_username} (<@{discord_id}>) to {new_rank}.")

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
                else:
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
                    
                    await ensure_single_rank_role(member, guild, current_rank)
            except Exception:
                print(f"Error updating rank for Discord ID {discord_id}: {traceback.format_exc()}.\n")

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
    add_column(cursor, "past_rank",       "TEXT")
    add_column(cursor, "tr",              "REAL")
    add_column(cursor, "past_tr",         "REAL")
    add_column(cursor, "apm",             "REAL")
    add_column(cursor, "vs",              "REAL")
    add_column(cursor, "pps",             "REAL")
    add_column(cursor, "sprint",          "REAL")
    add_column(cursor, "blitz",           "INTEGER")
    add_column(cursor, "zenith",          "REAL")
    add_column(cursor, "zenithbest",      "REAL")
    add_column(cursor, "zen",             "INT")
    
    conn.commit()
    conn.close()
    print("Database migration completed.\n")

@bot.command()
async def help(ctx):
    help_message = """
```Description: The bot assigns rank roles based on your TETR.IO rank and updates them periodically. Use the f.link command to link your Tetr.io account first.

Commands: 
f.help <command> - Show a command usage. (not available now :LMFAOOMFGHAHAH:)
f.link - Link your TETR.IO account to get your rank updated automatically. 
f.lb - Display a local leaderboard.

For issues or suggestions, contact @funli or @fleaf.```
"""
    await ctx.send(help_message)

#2
@bot.event
async def on_ready():
    create_db()
    migrate_db()
    # update_users.start()
    print('Logged in.\nv2 beta')

load_dotenv()
bot.run(os.getenv("TOKEN"))