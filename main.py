#!/usr/bin/python3

import nextcord, nextcord.ext.commands
from nextcord import SlashOption as Option

from time import time
from asyncio import create_task as unawait
import json
import re
import random

import settings as config  # also api keys

log = print
if not config.debug: log = lambda *_: None  # disable log on release

############# CLIENT INITIALIZATION #############

# intents: [Intents.FLAGS.GUILDS, Intents.FLAGS.GUILD_MESSAGES, Intents.FLAGS.GUILD_MEMBERS, Intents.FLAGS.GUILD_MESSAGE_REACTIONS, Intents.FLAGS.GUILD_VOICE_STATES],
intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True
# intents.presences = True
# intents.typing = False

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

def generateThreadName( name: str ):
  maxlen = config.max_threadname_length
  ellipsis = "…"
  wordellipsiswindow = maxlen//10
  
  # replace discord emojis (<:name:id>) with :name:
  name = re.sub(r"<(:[^:]+:)\d{10,}>", r"\1", name)
  
  # only use first 'paragraph'
  if '\n' in name:
    name = name[:name.find('\n')]
  
  # shorten to set max length if longer than that
  if len(name) > maxlen:
    name = name[:maxlen-len(ellipsis)]
    
    # if you find a space in the last section of the string, ellipse after that (to not break words)
    if ' ' in name[-wordellipsiswindow:]:
      name = name[:name.rfind(' ')+1]
    
    name += ellipsis
  
  if not name:
    name = "_"
  
  return name

async def open_thread( message, reason="4D Bot" ):
  await message.channel.create_thread( message=message, name=generateThreadName(message.content), reason=reason )

def update_tags( startup=False ):
  global tags
  
  if not startup:
    with open('tags.json', 'w') as tagsfile:
      json.dump(tags, tagsfile)
  
  try:
    with open('tags.json', 'r') as tagsfile:
      tags = json.load(tagsfile)
  except:
    tags = {}
  
  global tag, deletetag
  
  async def new_tag( interaction, tag: str = Option(description="Choose a tag",choices=tuple(tags)) ):
    await printtag(interaction,tag)
  new_tag.__name__ = 'tag'
  tag.from_callback(new_tag)
  
  async def new_deletetag( interaction, tag: str = Option(description="Choose a tag",choices=tuple(tags)) ):
    await dodeletetag(interaction,tag)
  new_deletetag.__name__ = 'deletetag'
  deletetag.from_callback(new_deletetag)
  
  if not startup:
    unawait( client.sync_all_application_commands(register_new=startup) )

############# CREATE ANNOUNCEMENT COMMAND #############

@client.slash_command(description="Create an announcement")
async def announcement(interaction, title: str = Option(description="Set a title"), description: str = Option(description="Set a description ( New line = ///)") ):
  log(f'/announcement {repr(title)} {repr(description)}')
  
  if not interaction.user.guild_permissions.manage_messages:
    return error( interaction )
  
  description = description.replace("///", "\n")
  
  embed = nextcord.Embed( title=title, colour=color('#fee65c'), description=description )
  embed.set_footer( text=f"Made by: {interaction.user}", icon_url=interaction.user.avatar.url )
  await interaction.send(embed=embed)

############# CREATE POLL COMMAND #############

@client.slash_command(description="Create a poll")
async def poll(interaction, question: str = Option(description="Set a question") ):
  log(f'/poll {repr(question)}')
  
  if not interaction.user.guild_permissions.manage_messages:
    return error( interaction )
  
  embed = nextcord.Embed( title="4D Poll", colour=color('#00c8c8'), description=question )
  embed.set_footer( text=f"Made by: {interaction.user}", icon_url=interaction.user.avatar.url )
  
  message = await (await interaction.send( embed=embed )).fetch()
  
  await react( message, config.poll_default_emoji )

############# CREATE TAG COMMAND #############

@client.slash_command(description="Add a premade message")
async def createtag(interaction, name: str = Option(description="Choose a tag name"), text: str = Option(description="Choose a tag output") ):
  log(f'/createtag {repr(name)} {repr(text)}')
  
  if not interaction.user.guild_permissions.manage_messages:
    return error(interaction)
  
  # name = name.lower()
  
  if name in tags:
    return error( interaction, "❎ This tagname is already taken. Try setting a different name." )
  
  tags[name] = text
  update_tags()
  
  await interaction.send( f"✅ Tag **{name}** has been successfully created." )

############# PRINT & DELETE TAG COMMANDS (WITH DYNAMIC SELECTION DROPDOWN) #############

# split off into separate functions to make updating the commands definitions easier
async def printtag(interaction, tag ):
  log(f'/tag {repr(tag)}')
  
  await interaction.send( tags[tag].replace('---', '\n') )

async def dodeletetag(interaction, tag ):
  log(f'/deletetag {repr(tag)}')
  
  if not interaction.user.guild_permissions.manage_messages:
    return error(interaction)
  
  tags.pop(tag)
  update_tags()
  
  await interaction.send( f"✅ Tag **{tag}** has been successfully removed." )

# these dummy functions will get overwritten, only the SlashApplicationCommand objects are permanent
@client.slash_command(description="Send premade messages")
async def tag(): pass
@client.slash_command(description="Delete a premade message")
async def deletetag(): pass

update_tags(True)  # fill the callback and options


############# RENAME THREAD COMMAND #############

@client.slash_command(description="Rename a thread created by 4D Bot")
async def rename_thread(interaction, name: str = Option(description="New name") ):
  log(f'/rename_thread {repr(name)}')
  
  if not isinstance( interaction.channel, nextcord.Thread ):
    return error( interaction, "❎ Command can only be used in threads!" )
  thread = interaction.channel
  
  if thread.owner != client.user:
    return error( interaction, "❎ Command can only be used in threads opened by 4D Bot!" )
  
  name = generateThreadName(name)
  
  unawait( interaction.send( f"✎ Thread renamed from '{thread.name}' to '{name}'\n(hopefully - discord thread renaming is unreliable )" ) )
  
  await thread.edit(name=name)

############# CREATE THREAD ON 🧵 EMOJI #############

# """
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
  
  await open_thread( message=message, reason="4D Bot - 🧵 emoji" )
# """

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

############# ADD VOTE EMOJI AND THREAD FOR SUGGESTIONS #############

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
  
  await open_thread( message=message, reason="4D Bot - autoThread in #suggestions" )

############# REMOVE THREAD CREATION NOTICES #############

@client.listen('on_message')
async def remove_thread_creation_notices(message):
  
  if message.type == nextcord.MessageType.thread_created:
    await message.delete()
    return
  
  # if message.type == nextcord.MessageType.channel_name_change:
  #   if message.author == client.user:
  #     await message.delete()
  #   return

############# WELCOME NEW 4D PEOPLE #############

@client.listen('on_member_join')
async def welcome_new(member):
  await client.get_partial_messageable(config.welcome_channel).send( random.choice(config.welcome_messages).format(member) )

############# BACKUP FOR MOST IMPORTANT SYSTEM OF THE 4D LEVELING BOT #############

@client.listen('on_message')
async def operationCounterEEP(message):
  eep = f'{chr(0x6d)}eep'  # the accursed word
  allowedEEPpercent = 0.15
  
  # # only affect anith and test acount
  # if not ( message.author.id == 411317904081027072 or message.author.id == 933495055895912448 ):
  #   return
  
  content = message.content
  content = re.sub("<:"+eep+":\\d{10,}>", eep, content)  # replace eep emojis with normal eeps for more realistic evaluation
  
  # only affect messages that are primarily (>20%) eeps
  if not len(content) < 4/allowedEEPpercent * content.lower().count( eep ):
    return
  
  try:
    emoji = [ emoji for emoji in await message.guild.fetch_emojis() if emoji.name == 'shut' ][0]
  except: return
  
  await message.add_reaction(emoji)
  log('Shut')

############# CRON #############

cron_minfreq = 60  # cron checks for due tasks every this many seconds
cronjobs = [
  { 'name': "update activity", 'frequencySeconds': 60, 'function': lambda: unawait(
    client.change_presence(activity=nextcord.Activity( type=nextcord.ActivityType.watching, name=f"{sum(guild.member_count for guild in client.guilds)} players" ))
  )},
]

@client.listen('on_ready')
async def cron():
  client.remove_listener( cron, 'on_ready' )  # stop more crons spawning on connection loss & restore
  
  print('Ready. Starting internal Cron')
  
  while not client.is_closed():  # check is_closed in case we missed the on_close event
    
    for cronjob in cronjobs:
      if cronjob.get('nextrun',0) <= time():
        cronjob['nextrun'] = time() + cronjob['frequencySeconds'] - cron_minfreq/10  # some leeway for rounding etc.
        cronjob['function']()
        log(f"ran {cronjob['name']}")
    
    try:
      if not client.is_closed(): await client.wait_for( 'close', timeout=cron_minfreq )
      break
    except: pass
  
  print('Stopping internal Cron')

############# STARTUP AND SHUTDOWN #############

client.run(config.bot_api_key)


"""
  TODO:
    - When reportet ask the mod for a reason and then inform the user of the report with the reason or after a 1h timeout
    - smarter thread names
    - thread pin message command
    - check if that command chapter thing makes the command parameter visible when invoked
      -> seem to show up individually in the command list. Look for way to not have that happen
"""
