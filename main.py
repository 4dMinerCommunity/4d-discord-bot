#!/usr/bin/python3

import nextcord, nextcord.ext.commands
from nextcord import SlashOption as Option

from time import time
from asyncio import create_task as unawait, gather
import json
import re
import unicodedata
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
client = nextcord.ext.commands.Bot( command_prefix='!', intents=intents, default_guild_ids=config.server_ids )

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

def get_partial_channel(channel_id):
  return client.get_partial_messageable(channel_id,type=nextcord.ChannelType.text)

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

def save_tags():
  global tags
  with open('tags.json', 'w') as tagsfile:
    json.dump(tags, tagsfile)

def read_tags():
  try:
    with open('tags.json', 'r') as tagsfile:
      tags = json.load(tagsfile)
  except:
    tags = {}
  
  if config.suggestions_info_msg_tagname not in tags:
    tags[config.suggestions_info_msg_tagname] = 'Placeholder.'
  
  return tags

def update_tags( startup=False ):
  global tags
  
  # skip writing tags to file on startup (as current tags will be empty)
  if not startup:
    save_tags()
  
  tags = read_tags()
  
  async def tag( interaction, tag: str = Option(description="Choose a tag",choices=tuple(tags)) ):
    await printtag(interaction,tag)
  globals()['tag'].from_callback(tag)
  
  async def edittag( interaction, tag: str = Option(description="Choose a tag",choices=tuple(tags)), text: str = Option(description="Choose the new tag output") ):
    await do_edittag(interaction,tag,text)
  globals()['edittag'].from_callback(edittag)
  
  async def deletetag( interaction, tag: str = Option(description="Choose a tag",choices=tuple(tags)) ):
    await dodeletetag(interaction,tag)
  globals()['deletetag'].from_callback(deletetag)
  
  
  if not startup:
    unawait( client.sync_all_application_commands(register_new=False) )

############# CREATE ANNOUNCEMENT COMMAND #############

@client.slash_command(description="Create an announcement")
async def announcement(interaction, title: str = Option(description="Set a title"), description: str = Option(description="Set a description ( New line = ///)") ):
  log(f'/announcement {repr(title)} {repr(description)}')
  
  if not interaction.user.guild_permissions.manage_messages:
    return error( interaction )
  
  description = description.replace("///", "\n")
  
  embed = nextcord.Embed( title=title, colour=color('#fee65c'), description=description )
  embed.set_footer( text=f"Made by: {interaction.user.name}", icon_url=interaction.user.avatar.url )
  await interaction.send(embed=embed)

############# CREATE POLL COMMAND #############

@client.slash_command(description="Create a poll")
async def poll(interaction, question: str = Option(description="Set a question") ):
  log(f'/poll {repr(question)}')
  
  if not interaction.user.guild_permissions.manage_messages:
    return error( interaction )
  
  embed = nextcord.Embed( title="4D Poll", colour=color('#00c8c8'), description=question )
  embed.set_footer( text=f"Made by: {interaction.user.name}", icon_url=interaction.user.avatar.url )
  
  message = await ( await interaction.send(embed=embed) ).fetch()
  
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
  
  text = text.replace('---', '\n')
  
  tags[name] = text
  update_tags()
  
  await interaction.send( f"✅ Tag **{name}** has been successfully created." )

############# PRINT, EDIT, DELETE TAG COMMANDS (WITH DYNAMIC SELECTION DROPDOWN) #############

# split off into separate functions to make updating the commands definitions easier
async def printtag(interaction, tag ):
  log(f'/tag {repr(tag)}')
  
  await interaction.send( tags[tag] )

async def do_edittag(interaction, tag, text ):
  log(f'/edittag {repr(tag)} {repr(text)}')
  
  if not interaction.user.guild_permissions.manage_messages:
    return error(interaction)
  
  tags[tag] = text
  save_tags()
  
  if tag == config.suggestions_info_msg_tagname:
    unawait( refresh_info_msg() )
  
  await interaction.send( f"✅ Tag **{tag}** has been successfully edited." )

async def dodeletetag(interaction, tag ):
  log(f'/deletetag {repr(tag)}')
  
  if not interaction.user.guild_permissions.manage_messages:
    return error(interaction)
  
  if tag == config.suggestions_info_msg_tagname:
    return error(interaction,msg=f"❎ You can't delete the {config.suggestions_info_msg_tagname}!")
  
  tags.pop(tag)
  update_tags()
  
  await interaction.send( f"✅ Tag **{tag}** has been successfully removed." )

# these dummy functions will get overwritten, only the SlashApplicationCommand objects are permanent
@client.slash_command(description="Send premade messages")
async def tag(): pass
@client.slash_command(description="Edit a premade message")
async def edittag(): pass
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

############# PIN COMMENT IN THREAD COMMAND #############

@client.command(help="Pin the replied to message (only in 4D Bot created threads)")
async def pin(context):
  log(f'!pin')
  
  thread = context.channel
  if not isinstance( thread, nextcord.Thread ):
    return
    # return error( context, "❎ Command can only be used in threads!" )
  
  if thread.owner != client.user:
    return
    # return error( context, "❎ Command can only be used in threads opened by 4D Bot!" )
  
  if not context.message.reference:
    return
    # return error( context, "Please reply to a message to pin it." )
  
  unawait( context.message.delete() )
  
  target = await thread.fetch_message(context.message.reference.message_id)
  
  if not target.pinned:
    await target.pin()
  else:
    unawait( target.unpin() )
    await thread.send(f'<@{context.author.id}> unpinned a message ({target.jump_url}) from this channel.',allowed_mentions=nextcord.AllowedMentions.none())

############# EXPORT DATA COMMAND #############

files = ['tags.json']

@client.slash_command(description="Export the datafiles of 4D Bot")
async def export(interaction):
  log(f'/export')
  
  for filename in files:
    with open(filename,'rb') as file:
      dcfile = nextcord.File(file,force_close=True)
    
    await interaction.send(file=dcfile)

@client.command(help="Export the datafiles of 4D Bot")
async def export(context):
  log(f'!export')
  
  for filename in files:
    with open(filename,'rb') as file:
      dcfile = nextcord.File(file,force_close=True)
    
    await context.reply(file=dcfile)

############# CREATE THREAD ON 🧵 EMOJI #############

@client.listen('on_raw_reaction_add')
async def create_thread_on_thread_emoji(reaction):
  
  if (reaction.emoji.name != '🧵'):
    return
  
  # in suggestions channel only
  if reaction.channel_id != config.suggestions_channel:
    return
  
  # not the bot itself (to stop infinite loops)
  if reaction.member == client.user:
    return
  
  channel, message = await gather(
    get_channel(reaction.channel_id),  # needed for create_thread
    client.get_partial_messageable(reaction.channel_id,type=nextcord.ChannelType.text).fetch_message(reaction.message_id),
  )
  message.channel = channel
  
  # we already have a thread
  if not message.thread is None:
    return
  
  unawait( message.remove_reaction(reaction.emoji,reaction.member) )
  unawait( message.add_reaction(reaction.emoji) )
  
  await open_thread( message=message, reason="4D Bot - 🧵 emoji" )

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
  embed.add_field( name="Message Author", value=f'<@{message.author.id}>' )
  embed.add_field( name="Reported by", value=f'<@{reaction.member.id}>' )
  await client.get_partial_messageable(config.reports_channel).send(embed=embed,allowed_mentions=nextcord.AllowedMentions.none())

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
  log(f'New member: {member}')
  
  await client.get_partial_messageable(config.welcome_channel).send( random.choice(config.welcome_messages).format(f'<@{member.id}>'), allowed_mentions=nextcord.AllowedMentions.none() )

############# KEEP INFO MESSAGE AT BOTTOM OF SUGGESTIONS CHANNEL #############

# holder of current infomessage
suggestions_info_msg = None

# fetch message id on startup
@client.listen('on_ready')
async def getLastInfomsg():
  global suggestions_info_msg
  
  suggestions_info_msg = await get_partial_channel(config.suggestions_channel).history(limit=100).get(author=client.user,content=tags[config.suggestions_info_msg_tagname])
  if suggestions_info_msg is None:
    print("Couldn't find last info message, might create duplicate!")
  else:
    log(f"Found last infomessage: {suggestions_info_msg.id}")

async def refresh_info_msg():
  global suggestions_info_msg
  
  # Delete the old info message if it exists
  if suggestions_info_msg is not None:
    unawait( suggestions_info_msg.delete() )
  
  # Send the new info message
  suggestions_info_msg = await get_partial_channel(config.suggestions_channel).send(tags[config.suggestions_info_msg_tagname])

@client.listen('on_message')
async def suggInfo(message):
  
  # Only in suggestions channel
  if message.channel.id != config.suggestions_channel:
    return
  
  # Ignore what will be deleted
  if message.type == nextcord.MessageType.thread_created:
    return
  
  if message.flags.ephemeral:
    return
  
  # Ignore this message itself
  if message == suggestions_info_msg or (message.author == client.user and message.content == tags[config.suggestions_info_msg_tagname]):
    return
  
  unawait( refresh_info_msg() )

############# BACKUP FOR MOST IMPORTANT SYSTEM OF THE 4D LEVELING BOT #############

@client.listen('on_message')
async def operationCounterEEP(message):
  eep = f'{chr(0x6d)}eep'  # the accursed word
  allowedEEPpercent = 0.15
  
  content = message.content
  content = re.sub("<:"+eep+":\\d{10,}>", eep, content)  # replace eep emojis with normal eeps for more realistic evaluation
  content = "".join(ch for ch in content if unicodedata.category(ch) not in {'Cf','Mn'})  # remove zero width characters
  content = content.lower().replace('е','e').replace('р','p')  # don't get fooled by cyrillics
  
  # only affect messages that are primarily (> allowedEEPpercent) eeps
  if not len(content)*allowedEEPpercent < len(eep) * content.count( eep ):
    return
  
  await message.add_reaction( nextcord.utils.get(message.guild.emojis,name='shut') )
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
    - When reported, ask the mod for a reason and then inform the user of the report with the reason or after a 1h timeout
    - smarter thread names
      -> look for sentence end markers
    - prevent sending links in useraccessible texts, like thread names from user messages
    - 6d chess
    
  TODO (far future, recheck periodically):
    - check if that command chapter thing makes the command parameter visible when invoked
      -> seem to show up individually in the command list. Look for way to not have that happen
        -> probably not possible rn :(
"""
