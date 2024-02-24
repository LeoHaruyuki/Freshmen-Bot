from discord.ext import tasks, commands
from dotenv import load_dotenv

import discord
import gspread
import sqlite3
import time
import os

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
# I have no intelligent way to do this yet
last_row = 9

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
print(daily_messages, daily_seconds)
