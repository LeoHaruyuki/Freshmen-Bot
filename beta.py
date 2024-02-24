from discord.ext import tasks, commands
from dotenv import load_dotenv

import asyncio
import discord
import gspread
import signal
import sqlite3
import sys
import time
import os
import pickle

# TODO: Make sqlite stuff into functions rather than copying and pasting in multiple functions
# TODO: Error catching
# TODO: Beautify printing
# TODO: Command to view specific stats

# Instantiate some variables used later
bot_channel, log_channel, role, join_list, voice_dict = None, None, None, [], {}
cur_day = int(time.strftime('%Y%m%d', time.localtime()))

# Load environment that token is stored in
load_dotenv()
client = commands.Bot(command_prefix="y|", intents=discord.Intents.all())

# Instantiate the application tracker variables
gc = gspread.service_account("service_account.json")
sh = gc.open("Brick City Bound Management (Responses)")
sheet = sh.get_worksheet(0)
titles = sheet.row_values(1)

# Create tables (Useless after first ever run)
# TODO: Make the column order consistent
conn = sqlite3.connect('RIT.db')
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS count (
id INTEGER,
messages INTEGER,
voice_seconds INTEGER
);""")
c.execute("""CREATE TABLE IF NOT EXISTS totals (
day INTEGER,
voice_seconds INTEGER,
messages INTEGER
);""")
conn.commit()

# Instantiate the daily counts to be in order with database
c.execute("SELECT messages, voice_seconds FROM totals WHERE day = ?", (cur_day,))
result = c.fetchone()
daily_messages = result[0] if result else 0
daily_seconds = result[1] if result else 0

# https://stackoverflow.com/questions/66271284/saving-and-reloading-variables-in-python-preserving-names
def save(filename, *args):
    # Get global dictionary
    glob = globals()
    d = {}
    for v in args:
        # Copy over desired values
        d[v] = glob[v]
    with open(filename, 'wb') as f:
        # Put them in the file 
        pickle.dump(d, f)

def load(filename):
    # Get global dictionary
    glob = globals()
    with open(filename, 'rb') as f:
        for k, v in pickle.load(f).items():
            # Set each global variable to the value from the file
            glob[k] = v

# Load specific variables that need to work through resets
load("variables")

def sigint_handler(sig, frame):
    global voice_dict, last_row
    print('Force shutdown detected, cleaning up')
    save("variables", "voice_dict", "last_row")
    print("Saved variables")
    conn.close()
    print("Closed sqlite")
    sys.exit(0)




@client.event
async def on_ready():
    global bot_channel, log_channel, role
    print(f"Logged in with {client.user}. Daily message count retrieved as {daily_messages}, VC seconds as {daily_seconds}")
    bot_channel = client.get_channel(1209271549237002310)
    log_channel = client.get_channel(1191391556033335306)
    role = client.get_guild(1190760871719338044).get_role(1209635586609250324)
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=str(client.get_guild(1190760871719338044).member_count) + " Members' Every Move"))
    if not spreadsheet_loop.is_running():
        spreadsheet_loop.start()


@client.event
async def on_message(message):
    global role, cur_day, daily_messages, log_channel
    if message.author.bot == False:
        temp_day = int(time.strftime('%y%m%d', time.localtime()))
        
        # First message in that day
        if temp_day > cur_day:
            daily_messages = 0
            cur_day = temp_day
        daily_messages += 1
        # Update daily message count
        c.execute('SELECT messages FROM totals WHERE day = ?', (cur_day,))
        result = c.fetchone()
        if not result:
            c.execute("INSERT INTO totals (day, voice_hours, messages) VALUES (?, ?, ?)", (cur_day, 0, 1))
            conn.commit()
        c.execute("UPDATE totals SET messages = ? WHERE day = ?", (daily_messages, cur_day,))
        conn.commit()

        # Update user message count
        c.execute("SELECT id FROM count WHERE id = ?", (message.author.id,))
        result = c.fetchone()
        if not result:
            c.execute("INSERT INTO count (id, messages, voice_seconds) VALUES (?, 1, 0)", (message.author.id,))
            conn.commit()
        c.execute("SELECT messages FROM count WHERE id = ?", (message.author.id,))
        result = c.fetchone()
        count = result[0]
        c.execute("UPDATE count SET messages = ? WHERE id = ?", (count+1, message.author.id,))
        conn.commit()

        # If user message count is 250, assign active user role (Using == instead of >= avoids pointless assigning)
        if count+1 == 250:
            await message.author.add_roles(role)
            print("Gave " + message.author.global_name + " Active Member role")
            embed = discord.Embed(title="Role Assigned", color=0xffffff, description="Active Member role was assigned to " + message.author.global_name + " for reaching 250 messages")
            await log_channel.send(embed=embed)
    await client.process_commands(message)


@client.event
async def on_member_join(member):
    global join_list, log_channel
    # Cycle the join list, only if three join times are already defined
    try:
        join_list[2]
        join_list[0] = join_list[1]
        join_list[1] = join_list[2]
        join_list[2] = int(time.time())
        # TODO: dm me as well, used to ping me in a channel, better if it dmed
        if join_list[2]-join_list[0] < 60:
            embed = discord.Embed(title="Suspicious Join Activity", color=0xffffff, description="Three new members have joined in " + str(join_list[2]-join_list[0]) + " seconds.")
            await log_channel.send(embed=embed)
    except IndexError:
        join_list.append(int(time.time()))
    # Bot is also in my server, this avoids counting that
    if member.guild.id == 1190760871719338044:
        member_count = member.guild.member_count
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=str(member_count) + " Members' Every Move"))
        # TODO: Store this in a file rather than a discord channel
        await client.get_channel(1209592495890108456).send(str(member_count))


@client.event
async def on_member_leave(member):
    # Same notes as 10 lines above
    if member.guild.id == 1190760871719338044:
        member_count = member.guild.member_count
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=str(member_count) + " Members' Every Move"))
        await client.get_channel(1209592495890108456).send(str(member_count))


@client.event
async def on_voice_state_update(member, before, after):
    global voice_dict, daily_seconds, cur_day
    # User joined voice channel
    if before.channel == None and after.channel != None:
        voice_dict[member.id] = int(time.time())
    # User left voice channel
    # TODO: Split time spent by days if it goes past midnight
    elif before.channel != None and after.channel == None:
        try:
            cur_time = time.localtime()
            if int(time.strftime('%Y%m%d', cur_time)) > cur_day:
                print("First time processing Voice Activity in a new day")
                daily_seconds = 0
                cur_day = int(time.strftime('%Y%m%d', cur_day))
            daily_seconds += (int(time.time()) - voice_dict[member.id])
            c.execute('SELECT voice_seconds FROM totals WHERE day = ?', (cur_day,))
            result = c.fetchone()
            if not result:
                c.execute("INSERT INTO totals (day, voice_seconds, messages) VALUES (?, ?, ?)", (cur_day, daily_seconds, 0))
                conn.commit()
            c.execute("UPDATE totals SET voice_seconds = ? WHERE day = ?", (daily_seconds, cur_day,))
            conn.commit()

            c.execute("SELECT voice_seconds FROM count WHERE id = ?", (member.id,))
            result = c.fetchone()
            if not result:
                c.execute("INSERT INTO count (id, messages, voice_seconds) VALUES (?, 0, 0)", (message.author.id,))
                conn.commit()
            c.execute("SELECT voice_seconds FROM count WHERE id = ?", (member.id,))
            result = c.fetchone()
            count = result[0] if result[0] else 0
            c.execute("UPDATE count SET voice_seconds = ? WHERE id = ?", (count+(int(time.time()) - voice_dict[member.id]), member.id,))
            conn.commit()
        except Exception as e:
            print(e)
            print("Error in Voice Channel tracking (Did you reboot the bot recently?)")


# TODO: Make this recursive for every 1999 characters instead of arbitrarily splitting it
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

# Catch all for shutdown, since pycord has horrible shutdown handling, and ubuntu doesn't want to catch sigint specifically for this file
@spreadsheet_loop.after_loop
async def on_shutdown():
    global voice_dict, last_row
    print('Force shutdown detected, cleaning up')
    save("variables", "voice_dict", "last_row")
    print("Saved variables")
    conn.close()
    print("Closed sqlite")

@client.slash_command(name="stats")
async def stats(ctx, user: discord.User, stat: discord.Option(str, choices=["Messages", "VC Seconds"])):
    if stat.lower() == "messages":
        c.execute('SELECT messages FROM count WHERE id = ?', (user.id,))
        await ctx.send(user.display_name + " has " + str(c.fetchone()[0]) + " messages in this server")
    else:
        c.execute('SELECT voice_seconds FROM count WHERE id = ?', (user.id,))
        await ctx.send(user.display_name + " has " + str(c.fetchone()[0]) + " seconds in voice call")
                

if __name__ == '__main__':
    client.run(os.getenv('TOKEN'))

