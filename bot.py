import discord.context_managers
from dotenv import load_dotenv
import discord
import sqlite3
import os
from discord.ext import commands, tasks
from discord import app_commands
import requests
import traceback
from datetime import datetime, timezone
from time import strftime, gmtime, time
from typing import Optional

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='f.', intents = intents, help_command = None)

SEARCH_URL = 'https://ch.tetr.io/api/users/search/discord:{}'
USER_URL   = "https://ch.tetr.io/api/users/{}/summaries"

TAC_GUILD_ID = 946060638231359588

MODS_ROLE = ["CEO of Stupid",
                "Tetris",
                "Temp.M"
                ]

def api_request(template, value):
    url = template.format(value)
    headers = {
        'User-Agent': 'funli bot',
        'From': 'funli',
        'X-Session-ID': '69420133780085',
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            return data
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
    conn = sqlite3.connect("user-data.db")
    conn.execute("PRAGMA foreign_keys = ON") #new for registration 
    return conn

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
            apm REAL,
            vs REAL,
            pps REAL,
            "40l" REAL,
            blitz INTEGER,
            zenith REAL,
            zenithbest REAL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registration_board (
            discord_id TEXT PRIMARY KEY ,
            tetrio_username TEXT NOT NULL,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (discord_id) REFERENCES users(discord_id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

def roles_check(member: discord.Member, ALLOWED_ROLES_NAMES: list[str]) -> bool:
    user_role_names = [role.name for role in member.roles]
    return any(role_name in user_role_names for role_name in ALLOWED_ROLES_NAMES)

#why are there 2 similar function, auto merge funni
#deleted btw (ensure-sigle-rank-role & remove-all-rank-role)


@bot.hybrid_command(name='link', description='Link your TETR.IO account to get your rank updated automatically')
@app_commands.guilds(discord.Object(id=TAC_GUILD_ID))
async def link(ctx: commands.Context):

    await ctx.defer() #no more error

    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT discord_id FROM users WHERE discord_id = ?", (ctx.author.id,))
        existing_user = cursor.fetchone()

        if existing_user: 
            await ctx.send ("Account already linked")
            #raise Exception("Account already linked")
            return

        response = api_request(SEARCH_URL, ctx.author.id)
        user = response.get("data", {}).get("user") if response and response.get("success") else None
        
        if not user:
            await ctx.send(f"User {ctx.author.display_name} has not connected Discord to TETR.IO.")
            return

        username = user["username"]
        rank = await update_user(cursor, ctx.author.id, username)

    rank_role = rank_to_role.get(rank)
    if not rank_role:
        await ctx.send (f"Rank '{rank}' is not recognized.")
        #raise Exception(f"Rank '{rank}' is not recognized.")
        return
    
    role = discord.utils.get(ctx.guild.roles, name = rank_role)
    if not role: 
        await ctx.send (f"Role '{rank_role}' not found. Please contact and admin.")
        #raise Exception(f"Role '{rank_role}' not found. Please contact and admin.")
        return

    await remove_all_rank_roles(ctx, ctx.guild)
    await ctx.author.add_roles(role)

@bot.hybrid_command(name = 'link_all', description = 'the name says it all')
@app_commands.guilds(discord.Object(id=TAC_GUILD_ID))
async def link_all(ctx: commands.Context):
    if not await roles_check(ctx.author, MODS_ROLE):
        await ctx.send(f'{ctx.author.display_name}, you do not have permission to use this command.')
        return
    
    conn = connect_db()
    cursor = conn.cursor()

    guild_id = TAC_GUILD_ID
    guild = bot.get_guild(guild_id)

    count = 0
    for member in guild.members:
        user = api_request(SEARCH_URL, member.id)["data"]
        if not user:
            continue 
        try:
            username = user["user"]["username"]
            await update_user(cursor, member.id, username) #should be updare-user instead of link-user
            #await ctx.send(f"Account linked successfully! Rank role '{rank_role}' assigned.")
            #idk how to fix kekw so archived
            count += 1
            await ctx.send(f"Account {member.name} linked successfully.")
        except Exception as e:
            await ctx.send(e)

    await ctx.send(f"Linked {count} members")
    conn.commit()
    conn.close()

# this is the name of column in users table mapped to
# a function that transfers object returned by tetrio API

# rank shouldn't be a leaderboard so change name probably
lbs = {
    "rank":      lambda result: result["league"].get("rank", -1),
    "tr":        lambda result: result["league"].get("tr",   -1),
    "apm":       lambda result: result["league"].get("apm",  -1),
    "vs":        lambda result: result["league"].get("vs",   -1),
    "pps":       lambda result: result["league"].get("pps",  -1),
    "past_rank": lambda result: result["league"].get("past", {}).get("1", {}).get("rank"),
    "past_tr":   lambda result: result["league"].get("past", {}).get("1", {}).get("tr"  ),

    "40l": lambda result: result["40l"].get("record",    {}
                                      ).get("results",   {}
                                      ).get("stats",     {}
                                      ).get("finaltime", -1),

    "blitz": lambda result: result["blitz"].get("record",  {}
                                          ).get("results", {}
                                          ).get("stats",   {}
                                          ).get("score",   -1),

    "zenith": lambda result: (result["zenith"]["record"] or {} 
                                            ).get("results", {}
                                            ).get("zenith",  {}
                                            ).get("score",   -1),

    "zenithbest": lambda result: result["zenith"].get("best",    {}
                                                ).get("result",  {}
                                                ).get("results", {}
                                                ).get("zenith",  {}
                                                ).get("score",   -1),
}

cached_at    = gmtime()
cached_until = time()

async def update_user(cursor, discord_id, tetrio_username): #idk
    values = []
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE discord_id = ?", (discord_id,))
        exists = cursor.fetchone()

        if not exists:
            tetrio_username = api_request(SEARCH_URL, discord_id)
            cursor.execute("INSERT INTO users (discord_id, tetrio_username) VALUES (?,?)", (discord_id, tetrio_username))
            conn.commit()

        response = api_request(USER_URL, tetrio_username)

        for lb in lbs:
            try:
                values.append(lbs[lb](response))
            except Exception as e:
                print(f"[update_user] Failed to extract {lb} for {tetrio_username}: {e}")
                values.append(None) #ye this is where the errors come from ig
    
        setstring = ', '.join(f'"{lb}" = ?' for lb in lbs)

        cursor.execute(f"UPDATE users SET {setstring} WHERE discord_id = ?",
                        values + [discord_id])
        global cached_until
        cached_until = response['cache']['cached_until'] // 1000
        return response['data']['league'].get('rank')

async def ensure_single_rank_role(member, guild, rank_from_db):  #idk what guild do but lets just keep it for now lol
    roles = member.roles
    rank_roles = [role for role in roles if role.name in rank_to_role.values()]

    if len(rank_roles) > 1:
        print(f"{member.name} has multiple rank roles. Removing incorrect roles.")
        for role in rank_roles:
            correct_role_name = rank_to_role.get(rank_from_db) 
            if role.name != correct_role_name:
                await member.remove_roles(role)
                print(f"Removed role {role.name} from {member.name}")
        print(' ')
    elif len(rank_roles) == 1:
        print("No other rank roles detected.\n")

@tasks.loop(hours=6)
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
                try:
                    member = guild.get_member(int(discord_id)) or await guild.fetch_member(int(discord_id)) #fix current error
                except discord.NotFound:
                    print(f"User {discord_id} left the server. Removing from DB.")
                    with connect_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM users WHERE discord_id = ?", (discord_id,))
                        conn.commit()
                        continue
                current_rank = rank
                new_rank = await update_user(cursor, discord_id, tetrio_username) #ah
                print(f"*Checking rank for {member.name} ({tetrio_username}):")
                print(f"Current rank in database: '{current_rank}'")
                print(f"Fetched rank from Tetr.io: '{new_rank}'")

                if new_rank != current_rank:  
                    #member = guild.get_member(int(discord_id)) or await guild.fetch_member(int(discord_id)) ---  moved upward
                    if not member:
                        continue

                    await remove_all_rank_roles(member, guild)

                    cursor.execute(
                        "UPDATE users SET rank = ? WHERE discord_id = ?",
                        (new_rank, discord_id)
                    )
                    print(f"Updated rank for {member.name} (<@{discord_id}>) to {new_rank}.")

                    new_role_name = rank_to_role.get(new_rank)
                    if not new_role_name:
                        print(f"Warning: No role mapping for rank '{new_rank}'.")
                        continue

                    new_role = discord.utils.get(guild.roles, name=new_role_name)
                    if not new_role:
                        print(f"Warning: Role '{new_role_name}' not found in guild.")
                        continue

                    if new_role not in member.roles:
                        print(f"Assigning new rank role '{new_role_name}' to {member.name}\n")
                        await member.add_roles(new_role)
                    else:
                        print(f"{member.name} already has the correct role '{new_role_name}'\n")
                else:
                    #member = guild.get_member(int(discord_id)) or await guild.fetch_member(int(discord_id))
                    if not member:
                        continue

                    current_role_name = rank_to_role.get(current_rank)
                    current_role = discord.utils.get(guild.roles, name=current_role_name)
                    if current_role and current_role not in member.roles:
                        print(f"{member.name} has the wrong role. Assigning '{current_role_name}' role")
                        await member.add_roles(current_role)
                    else:
                        print(f"{member.name} already has the correct role '{current_role_name}'")
                    
                    await ensure_single_rank_role(member, guild, current_rank)
            except Exception:
                print(f"Error updating rank for Discord ID {discord_id}: {traceback.format_exc()}.\n")
        global cached_at
        cached_at = gmtime()
        conn.commit()

    except Exception as e:
        print(f"Error during rank update: {e}")
    finally:
        conn.close()
        print(' ')

async def leaderboard(ctx, lbtype, fields, value_func, reverse_sort = False, amount = None):
    conn = connect_db()
    cursor = conn.cursor()

    string = f"{lbtype} leaderboard: ```"
    needs_update = False
    if time() > cached_until:
        needs_update = True
        message = await ctx.send("updating...")
        await update_users()

    cursor.execute(f"SELECT {'past_rank' if lbtype=='past_tr' else 'rank'}, tetrio_username, {','.join(fields)} FROM users" + (f" ORDER BY {lbtype} {'ASC' if reverse_sort else 'DESC'}" if len(fields) == 1 else ""))
    users = cursor.fetchall()
    users = tuple(filter(lambda fields: all(fields), users))
    if len(fields) > 1:
        users = sorted(users, key = value_func, reverse = not reverse_sort)

    if amount is None: 
        amount = len(users)

    amount = min(len(users), amount)
    for i in range(amount):
        user = users[i]
        value = value_func(user)
        formatstring = "{:<3}{:<3}{:<20}DNF\n" if value < 0 else  ("{:<3}{:<3}{:<20}{:.2f}\n" if type(value) == float else "{:<3}{:<3}{:<20}{}\n")
        string += formatstring.format(i+1, user[0], user[1], value)
  
    string += f"```\n-# {strftime('%c GMT', cached_at)}"
    if needs_update:
        await message.edit(content=string)
    else:
        await ctx.send(string)

    conn.close() #oh

@bot.hybrid_command(name='lb', description='Display a local leaderboard')
@app_commands.guilds(discord.Object(id=TAC_GUILD_ID))
async def lb(ctx: commands.Context, lbtype: str, amount: Optional[int] = None): 
    if lbtype in lbs:
        # eh
        sprint = lbtype == "40l"
        value_func = lambda user: (int(user[2]) if lbtype == "tr" else (user[2] / 1000 if sprint else user[2]))
        await leaderboard(ctx, lbtype, [lbtype], value_func, sprint, amount=amount)
    elif lbtype == "app":
        value_func = lambda user: user[2] / user[3] / 60
        await leaderboard(ctx, lbtype, ["apm", "pps"], value_func, amount=amount)
    elif lbtype == "vs/apm":
        value_func = lambda user: user[2] / user[3]
        await leaderboard(ctx, lbtype, ["vs", "apm"], value_func, amount=amount)
    else:
        await ctx.send(f"'{lbtype}' is not a valid leaderboard type")

@bot.hybrid_command(name='achievement_lb', description='Display a local achievement leaderboard')
@app_commands.guilds(discord.Object(id=TAC_GUILD_ID))
async def achlb(ctx: commands.Context, id: int, amount: Optional[int] = None): 
    info = api_request('https://ch.tetr.io/api/achievements/{}', id)
    if info == None:
        await ctx.send('no such achievement')
        return

    message = await ctx.send("updating...")

    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute('SELECT tetrio_username FROM users')
    users = cursor.fetchall()

    values = {} 
    for user in users:
        result = api_request(USER_URL, user[0])
        if not result:
            continue
        achievements = result['data']['achievements']
        ach = next(filter(lambda ach: ach['k'] == id, achievements), None)
        if not ach or 'v' not in ach:
            print('not found')
            continue
        values[user[0]] = ach['v']
        if not values[user[0]]:
            print('not found')

    values = sorted(values.items(), key=lambda item: item[1], reverse=True)

    if amount is None: 
        amount = len(values)

    amount = min(len(values), amount)

    name = info['data']['achievement']['name']
    vt   = info['data']['achievement']['vt']
    string = f'{name} leaderboard: ```'
    # invert for certain value types
    if vt in [3, 5, 6]:
        values = list(map(lambda item: [item[0], -item[1]], values))
    if vt in [2, 3]:
        values = list(map(lambda item: [item[0], item[1] / 1000], values))

    for i in range(amount):
        string += '{:<3}{:<20}{}\n'.format(i + 1, values[i][0], values[i][1])
    string += '```'

    await message.edit(content=string)

REG_START = int(datetime(2025, 4, 13, 0, 0, tzinfo=timezone.utc).timestamp()) # april 13
REG_END = int(datetime(2025, 4, 19, 23, 59, 59, tzinfo=timezone.utc).timestamp()) # april 19

@bot.hybrid_command(name = 'register', description = 'Register for the current tournament')
@app_commands.guilds(discord.Object(id=TAC_GUILD_ID))
async def register(ctx: commands.Context):

    await ctx.defer()

    allowed_roles =[
        "S- Rank",
        "S Rank",
        "S+ Rank",
        "SS Rank",
        "Lower Echelon's Pardon"
    ]
    if not roles_check(ctx.author, allowed_roles):
        await ctx.send("You are not qualified for this tournament.")
        return
    
    now = int(time())
    if now < REG_START or REG_END < now:
        utc_str = strftime("%Y-%m-%d %H:%M:%S", gmtime(now))
        await ctx.send(f"Registration is closed. Current UTC time: `{utc_str}`.\nRegistration is open from April 13 to April 19 (GMT +0).")
        return
    
    discord_id = str(ctx.author.id)
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tetrio_username FROM users WHERE discord_id = ?", (discord_id,))
        users_result = cursor.fetchone()

        if not users_result:
            await ctx.send("You have not linked your account yet. Please use /link.")
            return
        
        tetrio_username = users_result[0] #moved down 

        cursor.execute("SELECT * FROM registration_board WHERE discord_id =?", (discord_id,))
        register_result = cursor.fetchone()

        if register_result:
            await ctx.send("You have registered already.")
            return
        
        cursor.execute("INSERT INTO registration_board (discord_id, tetrio_username) VALUES (?, ?)",
              (discord_id, tetrio_username))
        conn.commit()
        
    await ctx.send("Registration completed. Use `/registration_show` to see a list of registered players.")

@bot.hybrid_command(name = 'registration_show', description = 'Show a list of registered player(s)')
@app_commands.guilds(discord.Object(id=TAC_GUILD_ID))
async def registration_show(ctx: commands.Context):
    await ctx.defer()

    with connect_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT registration_board.tetrio_username, registration_board.discord_id, users.rank, users.tr
            FROM registration_board
            JOIN users ON registration_board.discord_id = users.discord_id
            ORDER BY users.rank DESC
        ''')
        results = cursor.fetchall()

        if not results:
            await ctx.send("No players have registered yet.")
            return

        output = "**ACG Season 2 registration board:**\n```ini\n"  #change name each tourney ig
        output += f"{'Seed #':<7} {'Tetrio Username':<20} {'Discord ID':<30} {'Rank':<10} {'TR':<10}\n"
        output += "-" * 85 + "\n"

        for index, row in enumerate(results, start=1):
            tetrio_username = row[0]
            discord_id = f"@{row[1]}"
            rank = row[2] if row[2] else "Not found"
            tr = round(row[3], 2) if row[3] is not None else 0.00

    output += f"{index:<7} {tetrio_username:<20} {discord_id:<30} {rank:<10} {tr:<10.2f}\n"

    output += "```"
        
    await ctx.send(output)

@bot.hybrid_command(name='unregister', description='Unregister from the current tournament')
@app_commands.guilds(discord.Object(id=TAC_GUILD_ID))
async def unregister(ctx: commands.Context):
    await ctx.defer()

    discord_id = str(ctx.author.id)

    with connect_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM registration_board WHERE discord_id = ?", (discord_id,))
        if not cursor.fetchone():
            await ctx.send("You have not registered.")
            return

        cursor.execute("DELETE FROM registration_board WHERE discord_id = ?", (discord_id,))
        conn.commit()

    await ctx.send("You have been successfully unregistered from the tournament.")

def add_column(cursor, name, sqltype):
    try:
        cursor.execute(f"ALTER TABLE users ADD COLUMN {name} {sqltype}")
    except sqlite3.OperationalError:
        print(f"Column '{name}' already exists.")

def migrate_db():
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
    add_column(cursor, "40l",             "REAL")
    add_column(cursor, "blitz",           "INTEGER")
    add_column(cursor, "zenith",          "REAL")
    add_column(cursor, "zenithbest",      "REAL")
    
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

For issues or suggestions, contact @.funli. or @flleaf.```
"""
    await ctx.send(help_message)

@bot.event
async def on_member_join(member):
    try:
        update_user(member)
        print(f"Linked {member.name} who just joined the server.\n")
    except Exception as e:
        print(e)

@bot.event
async def on_member_remove(member):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE discord_id = ?", (member.id, ))
        conn.commit() #ah

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

@bot.event
async def on_ready():
    create_db()
    migrate_db()
    #update_users.start()
    
    #sync slash commands
    try:
        guild = discord.Object(id=TAC_GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f'Successfully synced {len(synced)} commands.\n')

    except Exception as e:
        print(f'Error syncing: {e}\n')

    print('Logged in.\nv3 beta')

load_dotenv()
bot.run(os.getenv("TOKEN"))