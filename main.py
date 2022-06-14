from typing_extensions import Required
import discord  #pour interragir avec discord
from web3 import Web3  #pour gerer le wallet
import csv  #pour gerer le csv
from requests import Request, Session  #pour les requetes https
import tweepy  #pour interragir avec twitter
from random import randint  #pour l'aléatoire
from time import sleep, localtime, strftime  #pour le temps
from discord_slash import SlashCommand, SlashContext, ButtonStyle  #pour les slash commands
from discord.ext import commands  #pour les slash commands
from discord_components import DiscordComponents, Button, ButtonStyle  #pour les bouttons et les embed
from eth_account import Account  #pour générer des portefeuilles
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects  #pour gerer les erreurs dans les requetes
import secrets  #aléatoire sécurisé
from math import sqrt
import json  #permet de gerer les json
import const  #le fichier const
import asyncio  #permet de faire des actions asynchrone
from tradingview_ta import TA_Handler, Interval, Exchange  #permet de récuperer des indicateurs techniques
from liquidationStrat import runStratLiquidation, liquidateVault, vaultCount, checkLiquidation, vaultDebt, getBalance, MAIAddress, donateCharity  #importe les fonctions de liquidationstrat
from discord_slash.utils.manage_commands import create_option  #ajoute des options aux slash commandes
from qr import get_qrcode

token = str(input("token: "))
prefix = "!"

separator = ","
polygon = "https://polygon-rpc.com/"
web3 = Web3(Web3.HTTPProvider(polygon))
bot = commands.Bot(command_prefix=prefix, description="Stop being distraded")
slash = SlashCommand(bot, sync_commands=True)
channel = bot.get_channel(981181572151664760)

# quand le bot se lance
@bot.event
async def on_ready():  
    await bot.change_presence(activity=discord.Game(name="distrade")) # change l'activité du bot
    print(bot.user.name, "is ready")
    while True:  #baisse de la crypto dans la description
        priced = round(float(await get_price()), 2)
        priced = str(priced) + "%"
        await bot.change_presence(activity=discord.Game(name=priced))
        await asyncio.sleep(1800)

# analyse les positions liquidables
async def liquidStrat(_vaultName):
    channel = bot.get_channel(981181572151664760)
    vaultAddress = str(const.MAIVaultAddress[_vaultName])
    nb = vaultCount(const.MAIVaultAddress[_vaultName])
    msg = "Il ya "+str(nb)+" vaults à analyser..."
    await channel.send(msg) # envoie un message dans channel
    print(vaultCount(vaultAddress), "vault open") # recupere me nombre de positions à analyser
    liquidable = []
    for id in range(1, vaultCount(vaultAddress)):
        try: # permet de gerer et éviter les erreurs
            if checkLiquidation(id, vaultAddress) == True:
                debt = vaultDebt(id, vaultAddress)*10**-18
                if debt>0.50: #vérifie que la dette est superieur à 50c
                  liquidable.append(str(id))
                  msg = id, "is liquidable with",debt
                  await channel.send(msg)
        except Exception as e:
            pass # ne rien faire
    return liquidable


#requète hhtp de l'API pour avoir la baisse en 24h
async def get_price():
    url = 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest?id=1,2' # url de l'api coinmarketcap
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': '53271cbd-1543-4386-8c8e-baf78807188f',
    } #notre clef api
    session = Session()
    session.headers.update(headers)
    try: # requete les données
        response = session.get(url)
        data = json.loads(response.text)
        short = data['data']['2']['quote']['USD']['percent_change_24h'] # recupere les prix en usd du json
        return str(short)
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)


#exécution de la fonction et affichage de la baisse
@slash.slash(name="price")
async def price(ctx: SlashContext): # recupere le contexte de la commande dans ctx
    price = await get_price()
    await ctx.send(price)


# envoyer un message a un channel particulier
@slash.slash(name="send")
async def send(ctx: SlashContext, channel: discord.TextChannel, *,
               message: str):
    await channel.send(message)

# envoie amount à une association caritative
@slash.slash(name="donateToKlima")
async def donateToKlima(ctx: SlashContext, montant: float):
    channel = bot.get_channel(981181572151664760)
    autor = str(ctx.author.id)
    walletInfo = await getWalletInfo(autor)
    donateCharity(montant, MAIAddress, walletInfo[0], walletInfo[1])
    msg = str(montant)+" USD a été donné à l'association KlimaDAO luttant contre le réchauffement climatique"
    await channel.send(msg)

# execute la strategie passive RSIBollStrat
@slash.slash(name="RSIBollStrat")
async def RSIBollStrat(ctx: SlashContext):
    channel = bot.get_channel(981181572151664760)
    await ctx.send(
        "RSIBollStrat en cours d'execution => résultat postés dans <#981181572151664760>")
    # determiner combien de temps il faut attendre avant la prochaine bougie
    current_time = strftime("%H:%M:%S", localtime())
    sec = int(current_time[6:])
    time_to_wait = 60 - sec
    first = True

    while True: # choisie la paire BTCUSD
        target = TA_Handler(symbol="BTCUSDC",
                            screener="crypto",
                            exchange="COINBASE",
                            interval=Interval.INTERVAL_1_MINUTE)
        analys = target.get_analysis() # analyse le rsi et la BB
        if analys.indicators["RSI"] >= 69 and analys.indicators["BB.upper"] < analys.indicators["close"]:
            #SHORT jusqu'à ce que le range soit réintegré
            position = []
            position.append(analys.indicators["close"])
            position.append(strftime("%D:%H:%M:%S", localtime()))
            print("short")
            await channel.send("short signal")
            ranged = False
            await asyncio.sleep(60)
            while ranged == False:
                target = TA_Handler(symbol="BTCUSDC",
                                    screener="crypto",
                                    exchange="COINBASE",
                                    interval=Interval.INTERVAL_1_MINUTE)
                analys = target.get_analysis() # determine quand 
                if analys.indicators["BB.upper"] > analys.indicators["close"] and analys.indicators["RSI"] <= 69:
                    await channel.send("vente de la position dans 3 bougies")
                    await asyncio.sleep(180)
                    await channel.send("position vendue")
                    ranged = True
                    strat = open("strat.csv", "r+", newline='')
                    writer = csv.writer(strat)
                    position.append(analys.indicators["close"])
                    position.append(strftime("%D:%H:%M:%S", localtime()))
                    print(position)
                    msg = str(position[0]),str(position[1]),str(position[2]),str(position[3])
                    await channel.send(msg)
                    benef = position[0]-position[2]
                    benef = benef**2
                    benef = sqrt(benef)#Racine carré du bénéf
                    message = "Le trade a gagné "+str(benef)+" points" # calule le benefice
                    await channel.send(message)
                    writer.writerow(position) 
                    strat.close()
                else:
                    await asyncio.sleep(60)  # analyse le rsi et la BB
        elif analys.indicators["RSI"] <= 31 and analys.indicators["BB.lower"] < analys.indicators["close"]:
            #LONG jusqu'à ce que le range soit réintegré
            position = [] #cree une liste pour mettre les positions dedans
            position.append(analys.indicators["close"])
            position.append(strftime("%D:%H:%M:%S", localtime()))
            print(position)
            print("long")
            await channel.send("long signal")
            ranged = False
            while ranged == False:
                target = TA_Handler(symbol="BTCUSDC",
                                    screener="crypto",
                                    exchange="COINBASE",
                                    interval=Interval.INTERVAL_1_MINUTE)
                analys = target.get_analysis()
                if analys.indicators["BB.lower"] < analys.indicators["close"] and analys.indicators["RSI"] >= 31:
                    await channel.send("vente de la position dans 3 candles")
                    await asyncio.sleep(180)
                    await channel.send("position vendue")
                    ranged = True
                    strat = open("strat.csv", "r+", newline='')
                    writer = csv.writer(strat)
                    position.append(analys.indicators["close"])
                    position.append(strftime("%D:%H:%M:%S", localtime()))
                    print(position)
                    msg = str(position[0]),str(position[1]),str(position[2]),str(position[3])
                    await channel.send(msg)
                    benef = position[2]-position[0]
                    message = "Le trade a gagné "+str(benef)+" points"
                    await channel.send(message)
                    writer.writerow(position) #ecrit dans strat.csv 
                    writer.writerow("\n")
                    strat.close()
                else:
                    await asyncio.sleep(60)
        else:
            print("neutral range")
        if first == True:
            await asyncio.sleep(time_to_wait)
            first = False
        else:
            await asyncio.sleep(60)


# commmande servant à savoir si une liquidation est possible en regardant si le prix à changé de 8% ou plus
@slash.slash(name="liquidationPassiveStrat", description="Strategie passive de liquidation")
async def liquidationPassiveStrat(ctx: SlashContext):
    channel = bot.get_channel(981181572151664760)
    await ctx.send("strategie activé pour les heures creuses (22h=>10h)")
    while True:
        current_time = strftime("%H:%M:%S", localtime())
        hour = int(current_time[:2])
        if hour > 22 or hour < 10: #Entre 22H et 10H du matin
          print("inactivité détécté => analyse possible")
          pourcent = float(await get_price())
          if pourcent <= -5:
              await channel.send(
                  "liquidation potentiellement possible => analyse en cours")
              liquidable = await liquidStrat("WETH") #analyse des positions
              await channel.send(liquidable)
          else:
            await asyncio.sleep(600)
        else:
          await asyncio.sleep(120)
          

# se déclenche lorsque un message est envoyé (utilisé pour test le bot au début) => obsolete
@bot.event
async def on_message(message):
    # pour ne pas repondre à lui meme
    if message.author.id == bot.user.id:
        return

    if message.content.endswith("quoi"):
        if randint(1, 4) == 1:
            await message.channel.send("CHI")
        else:
            await message.channel.send("FEUR")

    if message.content.startswith(prefix + 'hello'):
        await message.channel.send('Hello {0.author.mention}'.format(message))

    if message.content.startswith(prefix + 'token'):
        msg = await message.channel.send(token)
        sleep(5)
        await msg.delete()

    if message.content.startswith(prefix + 'copyright'):
        await message.channel.send('jojo')


# permet de liquider la position choisit
@slash.slash(name="liquideVault", description="test")
async def liquideVault(ctx: SlashContext, name: str, *, id: int):
    autor = str(ctx.author.id)
    msg = "En train de liquider le vault "+str(id)+"=> temps estimé : 30sec"
    await ctx.send(msg)
    channel = bot.get_channel(981181572151664760)
    walletInfo = await getWalletInfo(autor)
    print(walletInfo[1])
    address = const.MAIVaultAddress[name]
    liquidResult = liquidateVault(
        address,
        id,
        walletInfo[0],
        walletInfo[1],
    )
    print(liquidResult)
    await channel.send(str(liquidResult))

# lance l'analyse 
@slash.slash(name="liquidation_available", description="Analyse des vaults liquidable")
async def liquidation_available(ctx: SlashContext, name: str):
    await ctx.send("les liquidations possibles seront envoyés dans #strat")
    liquidable = await liquidStrat(name)
    print(liquidable)
    await ctx.send(str(liquidable))

# récupérer les données de wallet.csv
async def getWalletInfo(_id):
    autor = _id
    found = False
    wallet = open("wallet.csv", "r+") #récpuration des donnés csv
    content = wallet.readlines()
    for line in content:
        line_part = line.split(separator)
        id = line_part[0]
        if (id == autor):
            found = True
            break
    if found == False: #pour créer un id si il n'y en a pas déja d'existant 
        writer = csv.writer(wallet)
        prvkey = "0x" + secrets.token_hex(32) #genere un hexadécimal aleatoire sécurisé
        pbl_address = Account.from_key(prvkey)
        pbladdress = pbl_address.address # recupere l'adresse publique depuis la clef privé
        print(pbladdress)
        wallet_info = []
        wallet_info.append(autor)
        wallet_info.append(str(pbladdress))
        wallet_info.append(prvkey[2:].strip())
        writer.writerow(wallet_info)
        print(wallet_info)
        return [pbladdress.strip(), prvkey.strip()]
    else:
        return [line_part[1].strip(), line_part[2].strip()] #retourne l'adresse publique et la clef privée


#Fonction permettant d'afficher le wallet de la personne qui fait la requète et celà lui transmet un code QR generé à partir du code
@slash.slash(
    name="wallet",
    description=
    "Permet d'afficher le QR Code du wallet, et la somme dans celui-ci")
async def wallet(ctx: SlashContext):
    try:
      autor = str(ctx.author.id)
      walletInfo = await getWalletInfo(autor)
      pbladdress = str(walletInfo[0])
      get_qrcode(pbladdress)
      embed = discord.Embed(title="Tableau de bord de votre portefeuille",
                            description="",
                            color=discord.Color.blue())
      file = discord.File(pbladdress + ".png")
      embed.set_image(url="attachment://" + pbladdress + ".png")
      usdBalance = getBalance(MAIAddress, pbladdress) * 10 **-18 #recupere le montant d'usd
      msg2 = "USD balance : " + str(usdBalance)
      msg1 = pbladdress
      embed.add_field(name="Votre wallet est à l'adresse:", value=msg1, inline=False)
      embed.add_field(name="USD balance ", value=msg2, inline=True)
      await ctx.send(file=file, embed=embed) #envoie l'embed 
    except Exception as e:
      pass


#afficher pendant un periode momentanée le token du Bot
@slash.slash(name="tokenPLS")
async def tokenPLS(ctx: SlashContext):
    msg = await ctx.send(token)
    await asyncio.sleep(5)
    await msg.delete()

#utilisation de l'API tweetpy pour recuperer des tweets et regarder si il y a le mot clé "doge" apparait dans le dernier tweet
@slash.slash(name="twitterStrat")
async def twitterStrat(ctx: SlashContext):
    channel = bot.get_channel(981181572151664760)
    consumer_key = "jsuZQxVMkQLtp1DNodocI00df" #clef api
    consumer_secret= "zfja0coQsUuB4rOs0AsPUYxYh3tduDMkuvG4UabwvGhVb4QJWg"
    ACCESS_KEY = "1445427428076163082-AXFNDGVU1RSappLd7lNcl8boEjDuSB"
    ACCESS_SECRET = "vbqTQo3wn1RGvz2Rn6y1iuxhRz5KpnG2xeDhm5t3NN2eQ"
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(ACCESS_KEY, ACCESS_SECRET)
    api = tweepy.API(auth)
    conitnuetrade = True
    lastone = api.search_tweets("(from:elonmusk) doge") # recupere lrecupere les derniers tweets contenant le mot doge
    lastone = str(lastone)[117:136] # extrait l'id du dernier tweet
    while conitnuetrade == True:
      await asyncio.sleep(120)
      elontweets = api.search_tweets("(from:elonmusk) doge")
      lasttweetid = str(elontweets)[117:136]
      print(lasttweetid) #compare l'id du dernier et dj nouveau pour déterminer si c'edt jn nouveau tweet
      if lasttweetid != lastone:
        await channel.send(
                "Une personne influente vient de tweeter sur le dogecoin => un ordre d'achat a été placé")
        print("LONG DOGE")
        conitnuetrade = False #arrete le trade

# fonction pour tester et faire une simulation de la stratégie twitter
@slash.slash(name="testtwitterStrat")
async def testtwitterStrat(ctx: SlashContext):
    channel = bot.get_channel(981181572151664760)
    consumer_key = "jsuZQxVMkQLtp1DNodocI00df"
    consumer_secret = "zfja0coQsUuB4rOs0AsPUYxYh3tduDMkuvG4UabwvGhVb4QJWg"
    ACCESS_KEY = "1445427428076163082-AXFNDGVU1RSappLd7lNcl8boEjDuSB"
    ACCESS_SECRET = "vbqTQo3wn1RGvz2Rn6y1iuxhRz5KpnG2xeDhm5t3NN2eQ"
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(ACCESS_KEY, ACCESS_SECRET)
    api = tweepy.API(auth) # utilisation de l'API
    conitnuetrade = True
    lastone = api.search_tweets("(from:Max38251) doge")
    lastone = str(lastone)[117:136] #partie de l'id désiré
    while conitnuetrade == True:
        await asyncio.sleep(20)
        elontweets = api.search_tweets("(from:Max38251) doge")
        lasttweetid = str(elontweets)[117:136]
        print(lasttweetid)#Affiche l'ID du dernier Tweet 
        if lasttweetid != lastone: # voir si un autre tweet a apparu
            print("LONG DOGE")
            conitnuetrade = False
            await channel.send("achat du doge en cours...")
            await asyncio.sleep(5)
            await channel.send("achat")
            await asyncio.sleep(25)
            await channel.send("préparation à la vente...") #envoie les ordres dans strat
            await asyncio.sleep(5)
            await channel.send("vente")
        else:
            print("nothing")


#Initialisation de la commande /help, la variable guild_ids permet d'envoyer la réponse de l'éxécution de la commande dans un salon bien précis. La variable description permet d'indiquer à quoi sert la commande dès le menu déroulant qui apparait quand on tape /
@slash.slash(name="help", description="Menu contenant toutes les commandes de Distrade")
#Définition de la fonction embed
async def embed(ctx: SlashContext):
    #Définition du titre de l'embed, ainsi que de la couleur de celui-ci
    embed = discord.Embed(title="> Liste des commandes : ",
                          color=discord.Color.dark_purple())
    #Ajout d'un champ dans l'embed, le variable name est le nom du champ, et la variable value est le contenu de ce champ
    embed.add_field(
        name="/help :",
        value=":arrow_right: Cette commande permet d'afficher ce menu.",
        inline=True)
    embed.add_field(
        name="/wallet :",
        value=
        ":arrow_right: Cette commande permet d'afficher votre portefeuille.",
        inline=False)
    embed.add_field(
        name="/price :",
        value=
        ":arrow_right: Cette commande permet d'afficher le  pourcentage de changement journalier du Bitcoin.",
        inline=False)
    embed.add_field(
        name="/tokenpls :",
        value=
        ":arrow_right: Cette commande permet d'afficher le Token du bot, attention, le message reste 5s.",
        inline=False)
    embed.add_field(
        name="/helpstratliquid :",
        value=
        ":arrow_right: Cette commande permet d'expliquer clairement en quoi consiste la stratégie de liquidation et comment l'éxecuter",
        inline=False)
    embed.add_field(
        name="/helpstrattwiter :",
        value=
        ":arrow_right: Cette commande permet d'expliquer clairement en quoi consiste la stratégie Twitter. ",
        inline=False)
    embed.add_field(
        name="/twitterStrat:",
        value=
        ":arrow_right: Cette commande permet d'éxecuter la stratégie Twitter. ",
        inline=False)
    embed.add_field(
        name="/liquidationPassiveStrat :",
        value=
        ":arrow_right: Cette commande permet d'éxecuter la stratégie dîte de liquidation passive",
        inline=False)
    #Ajout d'une image dans l'embed
    embed.set_image(url="https://images.assetsdelivery.com/compings_v2/blankstock/blankstock1904/blankstock190401711.jpg")
    #Envoi de l'embed finalisé
    await ctx.send(embed=embed)


@slash.slash(name="strate", description="it's a strate")
async def strate(ctx: SlashContext):
    await ctx.send("test")


#Initialisation de la commande /helpstrat, la variable guild_ids permet d'envoyer la réponse de l'éxécution de la commande dans un salon bien précis. La variable description permet d'indiquer à quoi sert la commande dès le menu déroulant qui apparait quand on tape /
@slash.slash(name="helpstratliquid", description="embed")
#Définition de la fonction embed
async def embed(ctx: SlashContext):
    #Définition du titre de l'embed, ainsi que de la couleur de celui-ci
    embed = discord.Embed(title="> La stratégie de liquidation c'est quoi ?",
                          color=discord.Color.dark_blue(),
                          inline=False)
    #Ajout d'un champ dans l'embed, le variable name est le nom du champ, et la variable value est le contenu de ce champ
    embed.add_field(
        name="Explications :",
        value=
        "La stratégie de liquidation est simple : un client met une somme X de crypto-actifs, et emprunte en les utilisant jusqu'à 50% de cette somme. La valeur de ses crypto-actifs étant volatile, si sa valeur chute, le client aura emprunté trop d'argent contrairement au ratio initial de 50%. La stratégie de liquidation consiste à rembourser la dette de client, et, en contrepartie, de prendre le reste de crypto-actifs avec une prime de 10%. \r Pour liquider un vault il faut faire la commande /liquideVault et remplir en indiquant l'id et le collateral",
        inline=True)
    embed.set_image(
        url=
        "https://lh6.googleusercontent.com/ZchlZJe6ws4Ll56HQ_qQxWTX9f1s3ikrzN-oizemHFFpBimBWzkJ_DDVC49hax4ynW7svByxCiy4Olf-xIZZMqmVNrUJzfxte0dNgfEXqAaCHhNZXC9l1wgSl4SQ0dnDVSr5fQfr"
    )
    #Envoi de l'embed finalisé
    await ctx.send(embed=embed)


@slash.slash(name="helpStratTwitter", description="embed")
#Définition de la fonction embed
async def bembed(ctx: SlashContext):
    #Définition du titre de l'embed, ainsi que de la couleur de celui-ci
    embed = discord.Embed(title="> La stratégie Twitter c'est quoi ?",
                          color=discord.Color.dark_blue(),
                          inline=False)
    #Ajout d'un champ dans l'embed, le variable name est le nom du champ, et la variable value est le contenu de ce champ
    embed.add_field(
        name=" Quelques explications :",
        value=
        "La stratégie Twitter, une stratégie qui puise son potentiel dans le fait d'être en avance sur tout le monde, analyse les Tweets de personnes influentes content le mot clé doge, qui est une crypto : le DogeCoin. Nous constatons que lorsque une personne influente Tweet dessus, la valeur de la crypto grimpe en fléche. La stratégie consiste à acheter du DogeCoin au moment pile de la publication du Tweet, pour être en avance et pouvoir revendre lorsque la valeur du Doge est élevée. "
    )
    embed.set_image(
        url=
        "https://cdn.discordapp.com/attachments/981180735551569934/981324023818489907/unknown.png"
    )
    await ctx.send(embed=embed)

@slash.slash(name="helpStratRSIBoll", description="embed")
#Définition de la fonction embed  
async def aembed(ctx: SlashContext):
    #Définition du titre de l'embed, ainsi que de la couleur de celui-ci
    embed = discord.Embed(title="> La stratégie RSIBoll c'est quoi ?",
                          color=discord.Color.dark_blue(),
                          inline=False)
    #Ajout d'un champ dans l'embed, le variable name est le nom du champ, et la variable value est le contenu de ce champ
    embed.add_field(
        name=" Quelques explications :",
        value=
        "La stratégie RSIBoll, une stratégie qui puise son potentiel dans l'analyse technique de deux indicateurs: le RSI et les bandes de Bollinger. Lorsque ces indicateurs indiquent une periode de surachat ou de survente le bot va trader dans la direction inverse pour tirer profit de ces mouvements 'irrationnels'.")
    file = discord.File("boll.png")
    embed.set_image(url="attachment://"+"boll.png")
    await ctx.send(embed=embed, file=file)


bot.run(token)
