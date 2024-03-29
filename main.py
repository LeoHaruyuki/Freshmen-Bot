# ---- 
# Hard rewrite of the originals
# ----
# I want to make the code look nicer, but that's something I'll do later

from discord.ext import commands, tasks
from discord.commands import Option
from dotenv import load_dotenv

import datetime
import discord
import gspread
import os
import sys
import sqlite3

ACTIVE_MEMBER_MESSAGES = 100

load_dotenv()
client = commands.Bot(command_prefix="y|", intents=discord.Intents.all())

conn = sqlite3.connect('RIT.db')
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS user_stats(
          id TEXT,
          date TEXT,
          message_count INTEGER,
          voice_duration INTEGER,
          voice_start TEXT,
          PRIMARY KEY (id, date)
);""")
# Ease of access, not technically needed
c.execute("""CREATE TABLE IF NOT EXISTS server_stats(
          date TEXT PRIMARY KEY,
          message_count INTEGER,
          voice_duration INTEGER
);""")
c.execute("""CREATE TABLE IF NOT EXISTS members(
          member_count INTEGER,
          time TEXT
);""")
conn.commit()

# Instantiate the application tracker variables
gc = gspread.service_account("service_account.json")
sh = gc.open("Brick City Bound Management (Responses)")
sheet = sh.get_worksheet(0)
titles = sheet.row_values(1)
last_row = 9

def before_shutdown():
    print("Shutdown requested")
    conn.commit()
    conn.close()
    print("Database closed\n\n")
    pass

@client.event
async def on_ready():
    global role, log_channel
    log_channel = client.get_channel(1191391556033335306)
    # Beta bot is not in server
    if client.get_guild(1190760871719338044):
        role = client.get_guild(1190760871719338044).get_role(1209635586609250324)
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=str(client.get_guild(1190760871719338044).member_count) + " Members' Every Move"))
    print("Logged in as " + client.user.name)
    c.execute("SELECT SUM(message_count), SUM(voice_duration) FROM server_stats")
    result = c.fetchone()
    print("Total messages retrieved as " + str(result[0]) + "\nTotal voice duration retrieved as " + str(result[1]))
    if not spreadsheet_loop.is_running():
        spreadsheet_loop.start()

@client.event
async def on_message(message):
    global role, log_channel
    # We HATE bots
    if message.author.bot:
        return
    c.execute("INSERT INTO user_stats (id, date, message_count, voice_duration) VALUES (?, ?, ?, ?) ON CONFLICT (id, date) DO UPDATE SET message_count = message_count + 1", (str(message.author.id), str(datetime.date.today()), 1, 0,))
    c.execute("INSERT INTO server_stats (date, message_count, voice_duration) VALUES (?, ?, ?) ON CONFLICT (date) DO UPDATE SET message_count = message_count + 1", (str(datetime.date.today()), 1, 0,))
    conn.commit()
    
    c.execute("SELECT SUM(message_count) FROM user_stats WHERE id = ?", (str(message.author.id),))
    result = c.fetchone()
    if result and result[0]:
        if result[0] == ACTIVE_MEMBER_MESSAGES:
            await message.author.add_roles(role)
            print("Gave " + message.author.display_name + " Active Member role")
            embed = discord.Embed(title="Role Assigned", color=0xffffff, description="Active Member role was assigned to " + message.author.display_name + " for reaching " + str(ACTIVE_MEMBER_MESSAGES) + " messages")
            await log_channel.send(embed=embed)
    await client.process_commands(message)

@client.event
async def on_voice_state_update(member, before, after):
    # Member joined a channel (Did not move channels)
    if not before.channel and after.channel:
        c.execute("INSERT INTO user_stats (id, date, message_count, voice_duration, voice_start) VALUES (?, ?, ?, ?, ?) ON CONFLICT (id, date) DO UPDATE SET voice_start = ?", 
                  (str(member.id), str(datetime.date.today()), 0, 0, datetime.datetime.now(), datetime.datetime.now(),))
        conn.commit()
    # Member left a join channel (Did not move channels)
    if before.channel and not after.channel:
        c.execute("SELECT voice_start FROM user_stats WHERE id = ? AND date = ?", (str(member.id), str(datetime.date.today()),))
        result = c.fetchone()
        if result and result[0]:
            start = datetime.datetime.fromisoformat(result[0])
            end = datetime.datetime.now()
            while start.date() != end.date():
                end_of_day = datetime.datetime(start.year, start.month, start.day, 23, 59, 59)
                voice_duration = int((end_of_day-start).total_seconds())+1
                c.execute("UPDATE user_stats SET voice_duration = voice_duration + ? WHERE id = ? AND date = ?", (voice_duration, str(member.id), str(start.date()),))
                c.execute("INSERT INTO server_stats (date, message_count, voice_duration) VALUES (?, ?, ?) ON CONFLICT (date) DO UPDATE SET voice_duration = voice_duration + ?", (str(start.date()), 0, voice_duration, voice_duration))
                conn.commit()
                start = end_of_day + datetime.timedelta(seconds=1)
            voice_duration = int((end - start).total_seconds())
            c.execute("UPDATE user_stats SET voice_duration = voice_duration + ? WHERE id = ? AND date = ?", (voice_duration, str(member.id), str(datetime.date.today()),))
            c.execute("INSERT INTO server_stats (date, message_count, voice_duration) VALUES (?, ?, ?) ON CONFLICT (date) DO UPDATE SET voice_duration = voice_duration + ?", (str(datetime.date.today()), 0, voice_duration, voice_duration))
            conn.commit()


@client.slash_command()
@commands.is_owner()
async def shutdown(ctx):
    before_shutdown()
    await ctx.respond("Shutting Down.", ephemeral=True)
    exit()

@client.slash_command()
@commands.is_owner()
async def restart(ctx):
    before_shutdown()
    await ctx.respond("Restarting.", ephemeral=True)
    # Works if you change python3 to be the thing you type in terminal (py, python, python3, python -3.11)
    os.execv(sys.executable, ['python3'] + sys.argv)

@client.slash_command()
@commands.is_owner()
async def force_update(ctx, datestr: str):
    global role, log_channel
    interaction = await ctx.respond("Force updating database for date " + datestr, ephemeral=True)
    async def update(datestr):    
        print("Force updating database for date " + datestr)
        channel_count, failed_count = 0, 0
        date = datetime.date(int(datestr[0:4]), int(datestr[5:7]), int(datestr[8:10]))
        messages = []
        for channel in ctx.guild.channels:
            if type(channel) == discord.TextChannel:
                channel_count += 1
                last_message = datetime.datetime(date.year, date.month, date.day) + datetime.timedelta(days=1)
                while True:
                    temp = datetime.datetime(date.year, date.month, date.day) - datetime.timedelta(days=1)
                    try:
                        h = await channel.history(limit=200, before=last_message, after=temp).flatten()
                        try:
                            last_message = h[0].created_at
                            messages += h
                        except IndexError as e:
                            break
                    except discord.errors.Forbidden:
                        failed_count += 1
                        break
        print("Found " + str(len(messages)) + " messages sent on " + datestr + ". Searched " + str(channel_count-failed_count) + " channels, and couldn't access " + str(failed_count) + " more channels.")
        for message in messages:
            c.execute("INSERT INTO user_stats (id, date, message_count, voice_duration) VALUES (?, ?, ?, ?) ON CONFLICT (id, date) DO UPDATE SET message_count = message_count + 1", (str(message.author.id), str(date), 1, 0,))
            c.execute("INSERT INTO server_stats (date, message_count, voice_duration) VALUES (?, ?, ?) ON CONFLICT (date) DO UPDATE SET message_count = message_count + 1", (str(date), 1, 0,))
            conn.commit()
            c.execute("SELECT SUM(message_count) FROM user_stats WHERE id = ?", (str(message.author.id),))
            result = c.fetchone()
            if result and result[0]:
                try:
                    if result[0] == ACTIVE_MEMBER_MESSAGES:
                        member = client.get_guild(1190760871719338044).get_member(message.author.id)
                        await member.add_roles(role)
                        print("Gave " + member.display_name + " Active Member role")
                        embed = discord.Embed(title="Role Assigned", color=0xffffff, description="Active Member role was assigned to " + member.display_name + " for reaching " + ACTIVE_MEMBER_MESSAGES + " messages")
                        await log_channel.send(embed=embed)
                except Exception as e:
                    print(e)
                    print(message.author.name)
    # Every single day since server open, for when you have to hard recount database, could take hours
    if datestr == "all":
        delta = datetime.date.today() - datetime.date(2023, 12, 31)
        for i in range(delta.days + 1):
            date = datetime.date(2023, 12, 31) + datetime.timedelta(days=i)
            await update(date.strftime("%Y-%m-%d"))
    else:
        await update(datestr)

@client.slash_command()
@commands.is_owner()
async def update_active_role(ctx):
    global role
    await ctx.respond("Updating Active Member Role", ephemeral=True)
    users = {}
    guild = client.get_guild(1190760871719338044)
    for member in guild.members:
        c.execute("SELECT SUM(message_count) FROM user_stats WHERE id = ?", (member.id,))
        message_count = c.fetchone()
        if message_count and message_count[0]:
            if message_count[0] >= ACTIVE_MEMBER_MESSAGES:
                if role in member.roles:
                    pass
                else:
                    await member.add_roles(role)
                    print("Gave " + member.display_name + " Active Member role")
                    embed = discord.Embed(title="Role Assigned", color=0xffffff, description="Active Member role was assigned to " + member.display_name + " for reaching " + str(ACTIVE_MEMBER_MESSAGES) + " messages")
                    await log_channel.send(embed=embed)
            if message_count[0] < ACTIVE_MEMBER_MESSAGES:
                if role in member.roles:
                    member.remove_roles(role)
                    print("Removed Active Role from " + member.display_name)
    print("Done!")

@client.slash_command()
async def stats(ctx, date: Option(str, "Date in YYYY-MM-DD Format", required = False, default = "Total"), user: discord.User = None): # type: ignore
    embed = discord.Embed(title="Requested Stats", color=0x00ff00)
    if user:
        if date == "Total":
            c.execute("SELECT SUM(message_count), SUM(voice_duration) FROM user_stats WHERE id = ?", (str(user.id),))
        else:
            try:
                date = datetime.date(int(date[0:4]), int(date[5:7]), int(date[8:10]))
                c.execute("SELECT message_count, voice_duration FROM user_stats WHERE id = ? AND date = ?", (str(user.id), str(date),))
            except ValueError as e:
                await ctx.respond("Date should look like YYYY-MM-DD, 2024-02-26", ephemeral=True)
                return
    else:
        if date == "Total":
            c.execute("SELECT SUM(message_count), SUM(voice_duration) FROM server_stats")
        else:
            try:
                date = datetime.date(int(date[0:4]), int(date[5:7]), int(date[8:10]))
                c.execute("SELECT message_count, voice_duration FROM server_stats WHERE date = ?", (str(date),))
            except ValueError as e:
                await ctx.respond("Date should look like YYYY-MM-DD, 2024-02-26", ephemeral=True)
                return
    result = c.fetchone()
    if result:
        embed.add_field(name="Date", value=str(date))
        embed.add_field(name="Message Count", value=result[0])
        embed.add_field(name="Voice Duration (seconds)", value=result[1])
    else:
        embed.description = "No stats found."
    await ctx.respond(embed=embed, ephemeral=True)
        
# TODO: REWRITE THIS PLEASE FOR THE LOVE OF GOD
@tasks.loop(seconds=10)
async def spreadsheet_loop():
    global last_row, bot_channel
    val = sheet.row_values(last_row+1)
    if val:
        last_row += 1
        try:
            embed=discord.Embed(title=val[1], color=0xffffff)
            embed.set_author(name="New Application", url="https://docs.google.com/spreadsheets/d/1oQvQGJpjB1G6rRtvoJp_XAcsUgKW_P2s4llFYpXKFSI/edit?usp=sharing")
            embed.add_field(name="Incoming:", value=val[5], inline=False)
            embed.add_field(name="Suggestion:", value=val[2], inline=False)
            embed.add_field(name="Experience:", value=val[3], inline=False)
            embed.add_field(name="Elaborate:", value=val[4], inline=False)
            embed.set_footer(text=val[0])
            await bot_channel.send(embed=embed)
        except:
            try:
                embed=discord.Embed(title=val[1], color=0xffffff)
                embed.set_author(name="New Application", url="https://docs.google.com/spreadsheets/d/1oQvQGJpjB1G6rRtvoJp_XAcsUgKW_P2s4llFYpXKFSI/edit?usp=sharing")
                embed.add_field(name="Incoming:", value=val[5], inline=False)
                embed.add_field(name="Suggestion:", value=val[2], inline=False)
                embed.add_field(name="Experience:", value=val[3], inline=False)
                embed.set_footer(text=val[0])
                await bot_channel.send(embed=embed)
                embed=discord.Embed(title=val[1], color=0xffffff)
                embed.add_field(name="Elaborate:", value=val[4], inline=False)
                await bot_channel.send("**Elaborate:**\n" + val[4])
            except:
                await bot_channel.send("# Too long to send")

@client.event
async def on_member_join(member):
    global log_channel
    if member.guild.id == 1190760871719338044:
        time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO members (member_count, time) VALUES (?, ?)", (member.guild.member_count, time,))
        conn.commit()

        c.execute("SELECT time FROM members ORDER BY member_count DESC LIMIT 3")
        result = c.fetchall()
        recent_joins = [datetime.datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S") for r in result]
        print(recent_joins)
        # if len(recent_joins) > 3 and datetime.datetime.now() - latest_entry < datetime.timedelta(seconds=60)
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=str(member.guild.member_count) + " Members' Every Move"))

@client.event
async def on_member_leave(member):
    # Same notes as 10 lines above
    if member.guild.id == 1190760871719338044:
        member_count = member.guild.member_count
        time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO members (member_count, time) VALUES (?, ?)", (member_count, time,))
        conn.commit()
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=str(member_count) + " Members' Every Move"))

if __name__ == '__main__':
    client.run(os.getenv('TOKEN'))