from dotenv import load_dotenv
from discord.ext import tasks, commands

import discord
import time
import sqlite3
import os
import gspread

bot_channel, log_channel, role, join_list, daily_messages, daily_seconds, voice_dict = None, None, None, [], 0, 0, {}

load_dotenv()
client = commands.Bot(command_prefix="y?!|", intents=discord.Intents.all())

last_row = 9
gc = gspread.service_account("service_account.json")
sh = gc.open("Brick City Bound Management (Responses)")
sheet = sh.get_worksheet(0)
titles = sheet.row_values(1)
cur_day = int(time.strftime('%Y%m%d', time.localtime()))

conn = sqlite3.connect('RIT.db')
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS count (
id INTEGER,
messages INTEGER,
voice_seconds INTEGER
);""")
c.execute("""CREATE TABLE IF NOT EXISTS totals (
day INTEGER,
voice_hours INTEGER,
messages INTEGER
);""")
conn.commit()

c.execute('SELECT messages FROM totals WHERE day = ?', (cur_day,))
result = c.fetchone()
daily_messages = result[0] if result else 0
c.execute('SELECT voice_seconds FROM totals WHERE day = ?', (cur_day,))
result = c.fetchone()
daily_seconds = result[0] if result else 0


@client.event
async def on_ready():
    global bot_channel, role
    print(f"{client.user} is ready and online!")
    print(f"Loaded with {daily_messages} messages and {daily_seconds} VC seconds")
    bot_channel = client.get_channel(1209271549237002310)
    log_channel = client.get_channel(1191391556033335306)
    personal_channel = client.get_channel(1210398539855695923)
    role = client.get_guild(1190760871719338044).get_role(1209635586609250324)
    guild = client.get_guild(1190760871719338044)
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=str(guild.member_count) + " Members' Every Move"))
    spreadsheet_loop.start()

@client.event
async def on_message(message):
    global role, cur_day, daily_messages
    cur_time = time.localtime()
        
    if message.author.bot == False:
        if int(time.strftime('%Y%m%d', cur_time)) > cur_day:
            daily_messages = 0
            cur_day = int(time.strftime('%Y%m%d', cur_day))
        daily_messages += 1
        c.execute('SELECT messages FROM totals WHERE day = ?', (cur_day,))
        result = c.fetchone()
        if not result:
            c.execute("INSERT INTO totals (day, voice_hours, messages) VALUES (?, ?, ?)", (cur_day, 0, 1))
            conn.commit()
        c.execute("UPDATE totals SET messages = ? WHERE day = ?", (daily_messages, cur_day,))
        conn.commit()

        
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
        if count+1 == 250:
            await message.author.add_roles(role)
            print("Gave " + message.author.global_name + " Active Member role")
            embed = discord.Embed(title="Role Assigned", color=0xffffff, description="Active Member role was assigned to " + message.author.global_name + " for reaching 250 messages")
            await log_channel.send(embed=embed)
    await client.process_commands(message)

@client.event
async def on_member_join(member):
    try:
        join_list[2]
        join_list[0] = join_list[1]
        join_list[1] = join_list[2]
        join_list[2] = int(time.time())
        if join_list[2]-join_list[0] < 60:
            embed = discord.Embed(title="Suspicious Join Activity", color=0xffffff, description="Three new members have joined in " + str(join_list[2]-join_list[0]) + " seconds.")
            await log_channel.send(embed=embed)
            await personal_channel.send("<@803766890023354438>", embed=embed)
    except IndexError:
        join_list.append(int(time.time()))
    if member.guild.id == 1190760871719338044:
        member_count = member.guild.member_count
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=str(member_count) + " Members' Every Move"))
        await client.get_channel(1209592495890108456).send(str(member_count))

@client.event
async def on_member_leave(member):
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
            # TODO: Save voice_dict on reboot
            print(e)
            print("Error in Voice Channel tracking (Did you reboot the bot recently?)")

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

client.run(os.getenv('TOKEN'))
conn.close()
