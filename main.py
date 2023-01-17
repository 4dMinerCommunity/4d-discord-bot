import nextcord, nextcord.ext.commands

import time
from asyncio import create_task as unawait
import json

import settings as config  # also api keys
try:
  with open('tags.json', 'r') as tagsfile:
    tags = json.load(tagsfile)
except:
  tags = {}

log = print
if not config.debug: log = lambda *_: None  # disable log on release

############# CLIENT INITIALIZATION #############

# intents: [Intents.FLAGS.GUILDS, Intents.FLAGS.GUILD_MESSAGES, Intents.FLAGS.GUILD_MEMBERS, Intents.FLAGS.GUILD_MESSAGE_REACTIONS, Intents.FLAGS.GUILD_VOICE_STATES],
intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True
# intents.presences = True
intents.typing = False

log(list(intents))
client = nextcord.ext.commands.Bot( intents=intents, default_guild_ids=config.server_ids )

############# LIBRARY #############

async def get_channel(channel_id):
  channel_id = int(channel_id)  # jsut to make sure after the get_user() disaster
  
  # get from cache
  channel = client.get_channel(channel_id)
  
  # get fresh
  if not channel:
    try:
      log(f'trying to fetch unknown channel {channel_id}')
      channel = await client.fetch_channel(channel_id)
    except: pass
  
  return channel

async def react( message, emoji_names ):
  
  emojis = await message.guild.fetch_emojis()
  
  # async with asyncio.TaskGroup() as doReactions:
  for emoji_name in emoji_names:
    try:
      emoji = [ emoji for emoji in emojis if emoji.name == emoji_name ][0]
    except: return
    
    # doReactions.create_task( message.add_reaction(emoji) )
    await message.add_reaction(emoji)

def color( hexstr ):
  hexstr = hexstr.replace('#','')
  
  if len(hexstr) == 3: # 4bit color
    hexstr = ''.join( char*2 for char in hexstr )  # this duplicates the characters, not the amount
  
  return nextcord.Colour(int(hexstr,base=16))

def error( interaction, msg = "❎ You don't have permissions to execute this command!" ):
  unawait( interaction.send( embed=nextcord.Embed( title=msg, colour=color('#c800c8') ), ephemeral=True ) )

############# CREATE ANNOUNCEMENT COMMAND #############

@client.slash_command(description="Create an announcement")
async def announcement( interaction,
  title: str = nextcord.SlashOption(description="Set a title", required=True),
  description: str = nextcord.SlashOption(description="Set a description ( New line = ///)", required=True),
):
  log(f'/announcement {title.__repr__()} {description.__repr__()}')
  
  if not interaction.user.guild_permissions.manage_messages:
    return error( interaction )
  
  description = description.replace("///", "\n")
  
  embed = nextcord.Embed( title=title, colour=color('#fee65c'), description=description )
  embed.set_footer( text=f"Made by: {interaction.user}", icon_url=interaction.user.avatar.url )
  await interaction.send(embed=embed)

############# CREATE POLL COMMAND #############

@client.slash_command(description="Create a poll")
async def poll( interaction, question: str = nextcord.SlashOption(description="Set a question", required=True) ):
  log(f'/poll {question.__repr__()}')
  
  if not interaction.user.guild_permissions.manage_messages:
    return error( interaction )
  
  embed = nextcord.Embed( title="4D Poll", colour=color('#00c8c8'), description=question )
  embed.set_footer( text=f"Made by: {interaction.user}", icon_url=interaction.user.avatar.url )
  
  message = await interaction.send( embed=embed )
  
  await react( message, config.poll_default_emoji )

############# CREATE TAG COMMAND #############

@client.slash_command(description="Add a premade message")
async def createtag( interaction,
  name: str = nextcord.SlashOption(description="Choose a tag name", required=True),
  text: str = nextcord.SlashOption(description="Choose a tag output", required=True),
):
  log(f'/createtag {name.__repr__()} {text.__repr__()}')
  
  if not interaction.user.guild_permissions.manage_messages:
    return error(interaction)
  
  name = name.lower()
  
  if name in tags:
    return error( interaction, "❎ This tag name is already taken. Try setting a different name." )
  
  tags[name] = text
  with open('tags.json', 'w') as tagsfile:
    json.dump(tags, tagsfile)
  
  await interaction.send( f"✅ Tag with name **{name}** has been successfully created." )

############# DELETE TAG COMMAND #############

@client.slash_command(description="Delete a premade message")
async def deletetag( interaction, name: str = nextcord.SlashOption(description="Choose a tag name", required=True) ):
  log(f'/deletetag {name.__repr__()}')
  
  if not interaction.user.guild_permissions.manage_messages:
    return error(interaction)
  
  name = name.lower()
  
  if name not in tags:
    return error( interaction, "❎ Invalid tag provided. You can view tags using **/taglist**!" )
  
  tags.pop(name)
  with open('tags.json', 'w') as tagsfile:
    json.dump(tags, tagsfile)
  
  await interaction.send( f"✅ Tag with name **{name}** has been successfully removed." )

############# PRINT TAG COMMAND #############

@client.slash_command(description="Premade messages")
async def tag( interaction, tag: str = nextcord.SlashOption(description="Choose a tag", required=True) ):
  log(f'/tag {tag.__repr__()}')
  
  tag = tag.lower()
  
  if tag not in tags:
    return error( interaction, "❎ Invalid tag provided. You can view tags using **/taglist**!" )
  
  await interaction.send( tags[tag].replace('---', '\n') )

############# LIST TAGS COMMAND #############

@client.slash_command(description="View list of premade messages")
async def taglist( interaction ):
  log(f'/taglist')
  
  str = ""
  for tagid, tagname in enumerate(tags, start=1):
    str += f'**#{tagid}** {tagname}\n'
  
  embed = nextcord.Embed( title="Tag List", colour=color('#00c8c8'), description=str )
  await interaction.send(embed=embed)

############# CREATE THREAD ON 🧵 EMOJI #############

@client.listen('on_raw_reaction_add')
async def create_tread_on_tread_emoji(reaction):
  
  if (reaction.emoji.name != '🧵'):
    return
  
  # in suggestions channel only
  if reaction.channel_id != config.suggestions_channel:
    return
  
  channel = await get_channel(reaction.channel_id)
  message = await channel.fetch_message(reaction.message_id)
  
  # we already have a thread
  if not message.thread is None:
    return
  
  unawait( message.remove_reaction(reaction.emoji,reaction.member) )
  unawait( message.add_reaction(reaction.emoji) )
  
  await channel.create_thread( message=message, name=message.content[:96] +"...", reason="4D Bot - 🧵 emoji" )

############# REPORT ON 🚨 EMOJI #############

@client.listen('on_raw_reaction_add')
async def report_on_alarm_emoji(reaction):
  
  if (reaction.emoji.name != '🚨'):
    return
  
  # only act when a mod adds the emoji
  if not reaction.member.guild_permissions.manage_messages:
    return
  
  # don't act on bots
  if reaction.member.bot:
    return
  
  message = client.get_partial_messageable(reaction.channel_id,type=nextcord.ChannelType.news_thread).get_partial_message(reaction.message_id)  # we lie about the channel type
  
  unawait( message.remove_reaction(reaction.emoji,reaction.member) )
  unawait( message.add_reaction(reaction.emoji) )
  
  message = await message.fetch()
  
  embed = nextcord.Embed( title="Reported Message", description=f"[Message link]({message.jump_url})", colour=None )
  embed.add_field( name="Message Author", value=str(message.author) )
  embed.add_field( name="Reported by", value=str(reaction.member) )
  await client.get_partial_messageable(config.reports_channel).send(embed=embed)

############# ADD VOTE EMOJI FOR SUGGESTIONS #############

# add default emoji reactions
@client.listen('on_message')
async def suggestions_default_emoji(message):
  
  # only in suggestions channel
  if message.channel.id != config.suggestions_channel:
    return
  
  # only act on normal messages
  if message.type != nextcord.MessageType.default:
    return
  
  # don't act on bot messages
  if message.author.bot:
    return
  
  unawait( react( message, config.suggestions_default_emoji ) )
  
  # await message.channel.create_thread( message=message, name=message.content[:96] +"...", reason="4D Bot - autoThread in #suggestions" )

############# REMOVE THREAD CREATION NOTICES #############

usr_cooldowns = {}
@client.listen('on_message')
async def remove_thread_creation_notices(message):
  if message.type == nextcord.MessageType.thread_created:
    await message.delete()

############# CRON #############

# minimum frequency is 1 minute
cronjobs = [
  { 'name': "update activity", 'frequencySeconds': 60, 'nextrun': 0, 'function': lambda:
    unawait( client.change_presence(activity=nextcord.Activity( name=f"{len(client.guilds[0].members)} players", type=nextcord.ActivityType.watching )) ) },
]

@client.listen('on_ready')
async def cron():
  print('Ready. Starting internal Cron')
  
  while not client.is_closed():  # check is_closed in case we missed the on_close event
    
    for cronjob in cronjobs:
      if cronjob['nextrun'] <= time.time():
        cronjob['nextrun'] = time.time() + cronjob['frequencySeconds']
        cronjob['function']()
        log(f"ran {cronjob['name']}")
    
    try:
      if not client.is_closed(): await client.wait_for( 'close', timeout=60 )
      break
    except: pass
  
  print('Stopping internal Cron')

############# STARTUP AND SHUTDOWN #############

client.run(config.bot_api_key)
