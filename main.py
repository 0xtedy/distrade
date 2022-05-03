import discord
import web3
token = "OTY0NDI5NTY0NjM1OTMwNjg0.YlkhBg.z14XjGwIcCOmUMGk7aADtoQGRso"
prefix = "/"
class MyClient(discord.Client):
    async def on_ready(self):
        print(self.user.name)

    async def on_message(self, message):
        # pour ne pas repondre à lui meme
        if message.author.id == self.user.id:
            return
    
        if message.content.startswith(prefix + 'hello'):
            await message.channel.send('Hello {0.author.mention}'.format(message))
          
        if message.content.startswith(prefix + 'token'):
          await message.channel.send(token)
        
client = MyClient()
client.run(token)