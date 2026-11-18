
import os
import sqlite3
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, InlineKeyboardMarkup,
    InlineKeyboardButton
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
BKASH_NUMBER = os.getenv("BKASH_NUMBER", "ADMIN_BKASH_NUMBER")
REFERRAL_BONUS = 10
MIN_DEPOSIT = 100

if not TOKEN or ADMIN_ID == 0:
    raise SystemExit("BOT_TOKEN and ADMIN_ID are required")

bot = telebot.TeleBot(TOKEN)
DB = "bot.db"
flows = {}

SERVICES = [
    "Facebook Promotion",
    "Instagram Promotion",
    "YouTube Promotion",
    "TikTok Promotion",
    "Telegram Channel Promotion",
    "Telegram Group Promotion"
]

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def setup():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            uid INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            referrer INTEGER,
            bonus_paid INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS deposits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER,
            amount INTEGER,
            trx TEXT UNIQUE,
            status TEXT DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid INTEGER,
            service TEXT,
            details TEXT,
            status TEXT DEFAULT 'pending'
        );
        """)

setup()

def menu():
    k = ReplyKeyboardMarkup(resize_keyboard=True)
    k.row("📱 Services", "🛒 New Order")
    k.row("💳 Deposit", "👛 My Wallet")
    k.row("📦 My Orders", "🎁 Refer & Earn")
    k.row("👤 My Account", "🎧 Support")
    return k

def admin_only(uid):
    return uid == ADMIN_ID

def approval_buttons(kind, item):
    k = InlineKeyboardMarkup()
    k.row(
        InlineKeyboardButton(
            "✅ Approve",
            callback_data=f"{kind}_yes_{item}"
        ),
        InlineKeyboardButton(
            "❌ Reject",
            callback_data=f"{kind}_no_{item}"
        )
    )
    return k

@bot.message_handler(commands=["start"])
def start(m):
    uid = m.from_user.id
    ref = None

    args = m.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref = int(args[1][4:])
        except ValueError:
            pass

    with connect() as c:
        user = c.execute(
            "SELECT uid FROM users WHERE uid=?", (uid,)
        ).fetchone()

        if not user:
            if ref and ref != uid:
                exists = c.execute(
                    "SELECT uid FROM users WHERE uid=?", (ref,)
                ).fetchone()
                if exists:
                    c.execute(
                        "INSERT INTO users(uid,referrer) VALUES(?,?)",
                        (uid, ref)
                    )
                else:
                    c.execute("INSERT INTO users(uid) VALUES(?)", (uid,))
            else:
                c.execute("INSERT INTO users(uid) VALUES(?)", (uid,))

    bot.send_message(
        m.chat.id,
        "👑 Welcome to NAYAK SMM PANEL!\n\n"
        "আপনার পছন্দের সার্ভিস নির্বাচন করুন।",
        reply_markup=menu()
    )

@bot.message_handler(commands=["cancel"])
def cancel(m):
    flows.pop(m.from_user.id, None)
    bot.send_message(m.chat.id, "বাতিল হয়েছে।", reply_markup=menu())

@bot.message_handler(func=lambda m: m.text == "👛 My Wallet")
def wallet(m):
    with connect() as c:
        u = c.execute(
            "SELECT balance FROM users WHERE uid=?",
            (m.from_user.id,)
        ).fetchone()

    bot.reply_to(m, f"👛 আপনার ব্যালেন্স: ৳{u['balance'] if u else 0}")

@bot.message_handler(func=lambda m: m.text == "💳 Deposit")
def deposit(m):
    flows[m.from_user.id] = "amount"
    bot.send_message(
        m.chat.id,
        f"সর্বনিম্ন Deposit ৳{MIN_DEPOSIT}\n"
        "কত টাকা Deposit করবেন লিখুন।"
    )

@bot.message_handler(func=lambda m: m.text == "📱 Services")
@bot.message_handler(func=lambda m: m.text == "🛒 New Order")
def services(m):
    k = InlineKeyboardMarkup()
    for i, s in enumerate(SERVICES):
        k.add(InlineKeyboardButton(s, callback_data=f"service_{i}"))
    bot.send_message(m.chat.id, "সার্ভিস নির্বাচন করুন:", reply_markup=k)

@bot.callback_query_handler(func=lambda q: q.data.startswith("service_"))
def select_service(q):
    i = int(q.data.split("_")[1])
    if i < 0 or i >= len(SERVICES):
        return bot.answer_callback_query(q.id, "Invalid service")

    flows[q.from_user.id] = ("order", SERVICES[i])
    bot.answer_callback_query(q.id)
    bot.send_message(
        q.message.chat.id,
        "আপনার Page / Channel / Video Link এবং প্রচারের বিবরণ লিখুন।"
    )

@bot.message_handler(func=lambda m: m.text == "🎁 Refer & Earn")
def referral(m):
    uid = m.from_user.id
    username = bot.get_me().username
    link = f"https://t.me/{username}?start=ref_{uid}"

    with connect() as c:
        count = c.execute(
            "SELECT COUNT(*) n FROM users WHERE referrer=?",
            (uid,)
        ).fetchone()["n"]
        paid = c.execute(
            "SELECT COUNT(*) n FROM users WHERE referrer=? AND bonus_paid=1",
            (uid,)
        ).fetchone()["n"]

    bot.send_message(
        uid,
        f"🎁 Referral Link:\n{link}\n\n"
        f"মোট Refer: {count}\nসফল Refer: {paid}\n"
        f"প্রতি সফল Refer: ৳{REFERRAL_BONUS}"
    )

@bot.message_handler(func=lambda m: m.text == "👤 My Account")
def account(m):
    bot.reply_to(
        m,
        f"👤 My Account\nUser ID: {m.from_user.id}\n"
        f"Name: {m.from_user.first_name}"
    )

@bot.message_handler(func=lambda m: m.text == "📦 My Orders")
def orders(m):
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM orders WHERE uid=? ORDER BY id DESC LIMIT 10",
            (m.from_user.id,)
        ).fetchall()

    if not rows:
        return bot.reply_to(m, "এখনো কোনো অর্ডার নেই।")

    result = "📦 আপনার অর্ডার:\n\n"
    for r in rows:
        result += f"#{r['id']} | {r['service']} | {r['status']}\n"
    bot.send_message(m.chat.id, result)

@bot.message_handler(func=lambda m: m.text == "🎧 Support")
def support(m):
    bot.reply_to(m, "সাপোর্টের জন্য অ্যাডমিনের সঙ্গে যোগাযোগ করুন।")

@bot.message_handler(func=lambda m: m.from_user.id in flows)
def receive(m):
    uid = m.from_user.id
    f = flows.get(uid)

    if f == "amount":
        try:
            amount = int(m.text)
            if not MIN_DEPOSIT <= amount <= 100000:
                raise ValueError
        except ValueError:
            return bot.reply_to(m, "৳100 থেকে ৳100000-এর মধ্যে সঠিক পরিমাণ লিখুন।")

        flows[uid] = ("trx", amount)
        return bot.send_message(
            uid,
            f"বিকাশ নম্বর: {BKASH_NUMBER}\n"
            f"পরিমাণ: ৳{amount}\n"
            "পেমেন্ট করে Transaction ID পাঠান।"
        )

    if isinstance(f, tuple) and f[0] == "trx":
        amount = f[1]
        trx = m.text.strip()

        if not 5 <= len(trx) <= 100:
            return bot.reply_to(m, "সঠিক Transaction ID দিন।")

        try:
            with connect() as c:
                cur = c.execute(
                    "INSERT INTO deposits(uid,amount,trx) VALUES(?,?,?)",
                    (uid, amount, trx)
                )
                did = cur.lastrowid
        except sqlite3.IntegrityError:
            return bot.reply_to(m, "এই Transaction ID আগেই জমা হয়েছে।")

        flows.pop(uid, None)
        bot.send_message(uid, "⏳ Deposit Request Admin-এর কাছে পাঠানো হয়েছে।")
        bot.send_message(
            ADMIN_ID,
            f"💳 Deposit Request #{did}\nUser: {uid}\n"
            f"Amount: ৳{amount}\nTRX: {trx}",
            reply_markup=approval_buttons("dep", did)
        )
        return

    if isinstance(f, tuple) and f[0] == "order":
        service = f[1]
        details = m.text.strip()

        if not 5 <= len(details) <= 2000:
            return bot.reply_to(m, "সঠিক বিবরণ লিখুন।")

        with connect() as c:
            cur = c.execute(
                "INSERT INTO orders(uid,service,details) VALUES(?,?,?)",
                (uid, service, details)
            )
            oid = cur.lastrowid

        flows.pop(uid, None)
        bot.send_message(uid, f"✅ Order #{oid} জমা হয়েছে।")
        bot.send_message(
            ADMIN_ID,
            f"🛒 Order #{oid}\nUser: {uid}\nService: {service}\n"
            f"Details: {details}",
            reply_markup=approval_buttons("ord", oid)
        )

@bot.callback_query_handler(func=lambda q: q.data.startswith(("dep_", "ord_")))
def admin_action(q):
    if not admin_only(q.from_user.id):
        return bot.answer_callback_query(q.id, "Admin Permission নেই!", show_alert=True)

    kind, action, item = q.data.split("_")
    item = int(item)

    if kind == "dep":
        with connect() as c:
            r = c.execute("SELECT * FROM deposits WHERE id=?", (item,)).fetchone()

            if not r or r["status"] != "pending":
                return bot.answer_callback_query(q.id, "Already processed")

            if action == "yes":
                c.execute("UPDATE deposits SET status='approved' WHERE id=?", (item,))
                c.execute("UPDATE users SET balance=balance+? WHERE uid=?", (r["amount"], r["uid"]))

                u = c.execute(
                    "SELECT referrer,bonus_paid FROM users WHERE uid=?",
                    (r["uid"],)
                ).fetchone()

                if u and u["referrer"] and not u["bonus_paid"]:
                    c.execute(
                        "UPDATE users SET balance=balance+? WHERE uid=?",
                        (REFERRAL_BONUS, u["referrer"])
                    )
                    c.execute(
                        "UPDATE users SET bonus_paid=1 WHERE uid=?",
                        (r["uid"],)
                    )
                    bot.send_message(
                        u["referrer"],
                        f"🎁 Referral Bonus ৳{REFERRAL_BONUS} যোগ হয়েছে।"
                    )
                status = "Approved"
            else:
                c.execute("UPDATE deposits SET status='rejected' WHERE id=?", (item,))
                status = "Rejected"

        bot.send_message(r["uid"], f"Deposit {status} হয়েছে।")

    else:
        with connect() as c:
            r = c.execute("SELECT * FROM orders WHERE id=?", (item,)).fetchone()

            if not r or r["status"] != "pending":
                return bot.answer_callback_query(q.id, "Already processed")

            status = "completed" if action == "yes" else "rejected"
            c.execute("UPDATE orders SET status=? WHERE id=?", (status, item))

        bot.send_message(r["uid"], f"Order #{item}: {status}")

    bot.answer_callback_query(q.id, "Updated")
    bot.edit_message_reply_markup(
        q.message.chat.id, q.message.message_id, reply_markup=None
    )

@bot.message_handler(commands=["admin"])
def admin(m):
    if not admin_only(m.from_user.id):
        return bot.reply_to(m, "⛔ Admin Access নেই।")

    with connect() as c:
        users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        deposits = c.execute(
            "SELECT COUNT(*) n FROM deposits WHERE status='pending'"
        ).fetchone()["n"]
        orders = c.execute(
            "SELECT COUNT(*) n FROM orders WHERE status='pending'"
        ).fetchone()["n"]

    bot.send_message(
        m.chat.id,
        f"👑 NAYAK ADMIN PANEL\n\n"
        f"Total Users: {users}\n"
        f"Pending Deposits: {deposits}\n"
        f"Pending Orders: {orders}"
    )

print("NAYAK SMM PANEL STARTING...")
bot.remove_webhook()
bot.infinity_polling(skip_pending=True)
  
