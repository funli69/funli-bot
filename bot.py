import discord.context_managers
from dotenv import load_dotenv
import discord
import sqlite3
import os
from discord.ext import commands, tasks
from discord import app_commands
import requests
import traceback
from time import strftime, gmtime, time
from typing import Optional

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='f.', intents = intents, help_command = None)

SEARCH_URL = 'https://ch.tetr.io/api/users/search/discord:{}'
USER_URL   = "https://ch.tetr.io/api/users/{}/summaries"

TAC_GUILD_ID = 946060638231359588

MODS_ROLE_ID = [1246417236046905387,
                946061277183230002,
                1308704910409207869,
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
            apm REAL,
            vs REAL,
            pps REAL,
            sprint REAL,
            blitz INTEGER,
            zenith REAL,
            zenithbest REAL
        )
    ''')
    conn.commit()
    conn.close()

#why are there 2 similar function, auto merge funni
#deleted btw (ensure-sigle-rank-role & remove-all-rank-role)


@bot.hybrid_command(name='link', description='Link your TETR.IO account to get your rank updated automatically')
@app_commands.guilds(discord.Object(id=TAC_GUILD_ID))
async def link(ctx: commands.Context):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT discord_id FROM users WHERE discord_id = ?", (ctx.author.id, ))
        existing_user = cursor.fetchone()

        if existing_user: raise Exception("Account already linked")

        user = api_request(SEARCH_URL, ctx.author.id)['data']
        
        if not user:
            await ctx.send(f"User {ctx.author.display_name} has not connected Discord to TETR.IO.")
            return

        username = user["user"]["username"]
        rank = update_user(cursor, ctx.author.id, username)

    rank_role = rank_to_role.get(rank)
    if not rank_role: raise Exception(f"Rank '{rank}' is not recognized.")
    
    role = discord.utils.get(ctx.guild.roles, name = rank_role)
    if not role: raise Exception(f"Role '{rank_role}' not found. Please contact and admin.")

    await remove_all_rank_roles(ctx, ctx.guild)
    await ctx.add_roles(role)

async def mods_check(ctx: discord.Member) -> bool:
    user_role_ids = [role.id for role in ctx.roles]
    return any(role_id in user_role_ids for role_id in MODS_ROLE_ID)

@bot.hybrid_command(name = 'link_all', description = 'the name says it all')
@app_commands.guilds(discord.Object(id=TAC_GUILD_ID))
async def link_all(ctx: commands.Context):
    if not await mods_check(ctx):
        await ctx.send(f'{ctx.author.display_name}, you do not have permission to use this command.')
        return
    
    conn = connect_db()
    cursor = conn.cursor()

    guild_id = TAC_GUILD_ID
    guild = bot.get_guild(guild_id)

    count = 0
    for member in guild.members:
        user = api_request(SEARCH_URL, member.id)['data']
        if not user:
            continue 
        try:
            username = user["user"]["username"]
            await update_user(cursor, guild, username) #should be updare-user instead of link-user
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

    "sprint": lambda result: result["40l"].get("record",    {}
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

def update_user(cursor, discord_id, tetrio_username):
    values = []
    response = api_request(USER_URL, tetrio_username)
    for lb in lbs:
        values.append(lbs[lb](response['data']))
    
    setstring = ', '.join(f'{lb} = ?' for lb in lbs)

    cursor.execute(f"UPDATE users SET {setstring} WHERE tetrio_username = ?",
                    values + [tetrio_username])
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
                current_rank = rank
                new_rank = update_user(cursor, discord_id, tetrio_username)
                print(f"*Checking rank for {member.name} ({tetrio_username}):")
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
                    member = guild.get_member(int(discord_id)) or await guild.fetch_member(int(discord_id))
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

@bot.hybrid_command(name='lb', description='Display a local leaderboard')
@app_commands.guilds(discord.Object(id=TAC_GUILD_ID))
async def lb(ctx: commands.Context, lbtype: str, amount: Optional[int] = None): 
    if lbtype in lbs:
        # eh
        sprint = lbtype == "sprint"
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
    add_column(cursor, "sprint",          "REAL")
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
        cursor.execute("DELETE FROM users WHERE discord_id = ?", (id, ))

@bot.event
async def on_ready():
    create_db()
    migrate_db()
    update_users.start()
    
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