import lightbulb

bot = lightbulb.Bot(token='MTMxODcxNjc2ODMxNDcyNDM2Mg.GIktX7.0YGoCoWckGrbQXmi_ValEx0dEK8LS3QMNWZHuA', prefix='!')

# Load the menu plugin
from menu import load
load(bot)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.me.username}')

bot.run()


