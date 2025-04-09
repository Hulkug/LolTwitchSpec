import requests
import subprocess
import time
import asyncio
from twitchio.ext import commands
from threading import Thread
from dotenv import load_dotenv
import os

load_dotenv()

# ========= CONFIGURATION ==========
API_KEY = os.getenv("RIOT_API_KEY")
ACCOUNT_REGION = os.getenv("ACCOUNT_REGION")
GAME_REGION = os.getenv("GAME_REGION")
LEAGUE_CLIENT_PATH = os.getenv("LEAGUE_CLIENT_PATH")
REFRESH_INTERVAL = 30  # en secondes
POST_GAME_COOLDOWN = 60  # pause après chaque partie

# game_id, summoner_id, display_name
WATCHED_PLAYERS = [
    ("G2 SkewMond", "3327", "G2 Skewmond"),
    ("G2 Hans Sama", "12838", "G2 Hans Sama"), 
    ("G2 Caps", "1323", "G2 Caps"),
    ("G2 Labrov", "8085", "G2 Labrov"),
    ("G2 BrokenBlade", "1918", "G2 BrokenBlade"),
    ("Thumbs Down", "4847", "Parus")
]

TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL")
TWITCH_TOKEN = os.getenv("TWITCH_TOKEN")
TWITCH_NICK = os.getenv("TWITCH_NICK")

# ========= TWITCH VOTE SYSTEM ==========
vote_counts = {}
vote_options = []
vote_active = False
twitch_bot = None  # stocke l'instance pour envoyer des messages


class TwitchBot(commands.Bot):
    def __init__(self):
        super().__init__(token=TWITCH_TOKEN, prefix="!", initial_channels=[TWITCH_CHANNEL])

    async def event_ready(self):
        print(f"✅ Connecté à Twitch en tant que {self.nick}")

    async def event_message(self, message):
        global vote_counts, vote_active, vote_options

        if message.echo:
            return

        content = message.content.strip()
        if vote_active and content.isdigit():
            choice = int(content)
            if 1 <= choice <= len(vote_options):
                user = message.author.name
                vote_counts[user] = choice
                print(f"🗳️ {user} a voté pour {vote_options[choice-1][0]}")


def start_twitch_bot():
    global twitch_bot
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    twitch_bot = TwitchBot()
    loop.run_until_complete(twitch_bot.start())


async def send_chat_message(message):
    if twitch_bot and twitch_bot.connected_channels:
        channel = twitch_bot.connected_channels[0]
        await channel.send(message)


def launch_vote(players, duration=30):
    global vote_counts, vote_active, vote_options

    vote_counts.clear()
    vote_options = players
    vote_active = True

    print("\n🗳️ VOTE TIME ! Les viewers peuvent voter en tapant le numéro du joueur à spectate :")
    vote_lines = []
    for idx, (name, _) in enumerate(players):
        line = f"  {idx+1}. {name}"
        vote_lines.append(line)
        print(line)

    print(f"⌛ Vote pendant {duration} secondes...")

    # 🔁 Message Twitch : début du vote
    message = (
        "🗳️ Le vote pour le prochain joueur à spectate a commencé ! "
        "Tapez un chiffre dans le chat pour voter :" +
        " ".join([f"{i+1}. {player[2]}" for i, (player, _) in enumerate(players)])
    )
    asyncio.run(send_chat_message(message))

    time.sleep(duration)
    vote_active = False

    results = {}
    for vote in vote_counts.values():
        results[vote] = results.get(vote, 0) + 1

    if not results:
        print("❌ Aucun vote reçu.")
        asyncio.run(send_chat_message("❌ Aucun vote reçu. On relance la détection dans un instant..."))
        return None

    sorted_votes = sorted(results.items(), key=lambda x: x[1], reverse=True)
    winner_idx = sorted_votes[0][0] - 1
    winner = players[winner_idx]
    winner_name = winner[0]

    print(f"🎉 {winner_name} a gagné le vote avec {sorted_votes[0][1]} votes !")
    asyncio.run(send_chat_message(f"🎉 On part spectate {winner_name} !"))

    return winner


# ========= RIOT API ==========
HEADERS = {"X-Riot-Token": API_KEY}
SUMMONER_URL = f"https://{ACCOUNT_REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
GAME_URL = f"https://{GAME_REGION}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/"


def get_summoner_id(name):
    (game_id, tag) = next(((p[0], p[1]) for p in WATCHED_PLAYERS if p[2] == name), ("", ""))
    print(game_id, tag)
    res = requests.get(SUMMONER_URL + game_id + "/" + tag, headers=HEADERS)
    # Format the game_id (summoner name) to handle spaces
    formatted_game_id = game_id.replace(" ", "%20")
    res = requests.get(SUMMONER_URL + formatted_game_id + "/" + tag, headers=HEADERS)
    if res.status_code == 200:
        return res.json()["puuid"]
    return None


def get_active_game(summoner_id):
    res = requests.get(GAME_URL + summoner_id, headers=HEADERS)
    if res.status_code == 200:
        return res.json()
    return None


def spectate_game(game_data):
    game_id = game_data["gameId"]
    platform_id = game_data["platformId"]
    encryption_key = game_data["observers"]["encryptionKey"]
    spectator_server = f"lolspectator-{platform_id.lower()}.leagueoflegends.com"
    spectator_port = 80

    command = [
        LEAGUE_CLIENT_PATH,
        "--spectator",
        f"{spectator_server}:{spectator_port}",
        encryption_key,
        str(game_id),
        platform_id
    ]

    print(f"\n🎥 Lancement du spectate pour la game {game_id}...")
    subprocess.run(command)


# ========= MAIN LOOP ==========
def main():
    print("🔄 Surveillance des joueurs...")
    while True:
        active_players = []

        for player in WATCHED_PLAYERS:
            print(f"🔍 Vérification de {player}...")
            summoner_id = get_summoner_id(player[2])
            if not summoner_id:
                print(f"⚠️  Impossible de récupérer l'ID de {player}")
                continue

            game_data = get_active_game(summoner_id)
            if game_data:
                print(f"✅ {player} est en game !")
                active_players.append((player, game_data))

        if len(active_players) == 1:
            print(f"\n🎯 Un seul joueur en game : {active_players[0][0]}")
            spectate_game(active_players[0][1])
            print("📴 Partie terminée. Retour à la recherche dans quelques secondes...")
            asyncio.run(send_chat_message("📴 Partie terminée ! Recherche d'une nouvelle game en cours..."))
            time.sleep(POST_GAME_COOLDOWN)
            continue

        elif len(active_players) > 1:
            gagnant = launch_vote(active_players, duration=30)
            if gagnant:
                spectate_game(gagnant[1])
                print("📴 Partie terminée. Retour à la recherche dans quelques secondes...")
                asyncio.run(send_chat_message("📴 Partie terminée ! Recherche d'une nouvelle game en cours..."))
                time.sleep(POST_GAME_COOLDOWN)
                continue
            else:
                print("❌ Pas de gagnant, nouvelle vérification dans quelques secondes...")

        else:
            print("⏳ Aucun joueur n'est en game. Nouvelle vérification dans quelques secondes...")

        time.sleep(REFRESH_INTERVAL)


# ========= LANCEMENT ==========
if __name__ == "__main__":
    Thread(target=start_twitch_bot, daemon=True).start()
    main()
