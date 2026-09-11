from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Start Session", callback_data="start_session"),
         InlineKeyboardButton("⏹ Stop Session", callback_data="stop_session")],
        [InlineKeyboardButton("💼 Active Trade", callback_data="active_trade"),
         InlineKeyboardButton("📋 Session Status", callback_data="status")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ])

def asset_menu(assets):
    rows, row = [], []
    for asset in assets:
        row.append(InlineKeyboardButton(asset, callback_data=f"asset:{asset}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)

def trade_signal_menu():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ TRADE TAKEN", callback_data="trade_taken"),
        InlineKeyboardButton("❌ TRADE NOT TAKEN", callback_data="trade_not_taken"),
    ]])

def trade_monitor_menu():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🛑 STOP TRADE", callback_data="stop_trade"),
        InlineKeyboardButton("🔄 REFRESH", callback_data="refresh"),
    ]])
