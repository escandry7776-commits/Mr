#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# ReportBot v2: Telegram Bot + Web Server for Gmail App Reporter
# ═══════════════════════════════════════════════════════════════════════════════
# - Admins add unlimited subjects + bodies via Telegram bot
# - Web page picks random report and opens Gmail APP (not website)
# - No mailto:security@telegram.org (removed)
# Requires: pip install aiogram aiohttp
# ═══════════════════════════════════════════════════════════════════════════════

import os
import json
import asyncio
import logging
from datetime import datetime
from typing import List, Dict

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from aiohttp import web

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
BOT_TOKEN = "8802325561:AAH2H_9K81CgGwGDGboegaEzaxNSVyGgpfk"
ADMIN_IDS = [7182447005, 8952526489]
DATA_FILE = "reports.json"
WEB_PORT = 8080

# Gmail recipients (fixed)
GMAIL_TO = "abuse@telegram.org,reports@telegram.org,stopCA@telegram.org,dmca@telegram.org"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
LOG = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# DATA MANAGER
# ═══════════════════════════════════════════════════════════════════════════════
class DataManager:
    def __init__(self, path: str = DATA_FILE):
        self.path = path
        self.reports: List[Dict] = []
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    self.reports = json.load(f)
                LOG.info(f"Loaded {len(self.reports)} reports")
            except Exception as e:
                LOG.error(f"Load error: {e}")
                self.reports = []
        else:
            self.reports = []

    def save(self):
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.reports, f, ensure_ascii=False, indent=2)

    def add(self, subject: str, body: str) -> int:
        self.reports.append({
            'id': len(self.reports) + 1,
            'subject': subject,
            'body': body,
            'created': datetime.now().isoformat(),
        })
        self.save()
        return len(self.reports)

    def delete(self, report_id: int) -> bool:
        before = len(self.reports)
        self.reports = [r for r in self.reports if r['id'] != report_id]
        # Re-index
        for i, r in enumerate(self.reports):
            r['id'] = i + 1
        self.save()
        return len(self.reports) < before

    def delete_all(self):
        self.reports = []
        self.save()

    def get_all(self) -> List[Dict]:
        return self.reports

    def count(self) -> int:
        return len(self.reports)

db = DataManager()

# ═══════════════════════════════════════════════════════════════════════════════
# FSM STATES
# ═══════════════════════════════════════════════════════════════════════════════
class AddReport(StatesGroup):
    waiting_subject = State()
    waiting_body = State()

# ═══════════════════════════════════════════════════════════════════════════════
# BOT HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@dp.message(CommandStart())
async def cmd_start(msg: Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("⛔ دسترسی ندارید.")
        return
    await msg.answer(
        "🤖 <b>ReportBot v2</b>\n\n"
        "📋 دستورات:\n"
        "/add — افزودن گزارش جدید (سابجکت + متن)\n"
        "/list — لیست گزارش‌ها\n"
        "/delete — حذف گزارش\n"
        "/clear — حذف همه\n"
        "/stats — آمار\n"
        "/link — لینک صفحه گزارش‌دهی\n\n"
        f"📊 تعداد گزارش‌ها: <b>{db.count()}</b>",
        parse_mode="HTML"
    )

@dp.message(Command("add"))
async def cmd_add(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return await msg.answer("⛔ دسترسی ندارید.")
    await state.set_state(AddReport.waiting_subject)
    await msg.answer(
        "📝 <b>مرحله ۱/۲:</b> سابجکت ایمیل را بفرستید:\n\n"
        "<i>مثال: URGENT: Doxxing Report – @channel</i>",
        parse_mode="HTML"
    )

@dp.message(AddReport.waiting_subject)
async def process_subject(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    await state.update_data(subject=msg.text.strip())
    await state.set_state(AddReport.waiting_body)
    await msg.answer(
        "📝 <b>مرحله ۲/۲:</b> متن کامل گزارش را بفرستید:\n\n"
        "<i>متن انگلیسی باشد. لینک‌ها را هم اضافه کنید.</i>",
        parse_mode="HTML"
    )

@dp.message(AddReport.waiting_body)
async def process_body(msg: Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        return
    data = await state.get_data()
    subject = data.get('subject', '')
    body = msg.text.strip()
    total = db.add(subject, body)
    await state.clear()
    await msg.answer(
        f"✅ <b>گزارش #{total} اضافه شد!</b>\n\n"
        f"📌 سابجکت: <code>{subject[:80]}</code>\n"
        f"📝 متن: {len(body)} کاراکتر\n"
        f"📊 کل گزارش‌ها: <b>{total}</b>",
        parse_mode="HTML"
    )

@dp.message(Command("list"))
async def cmd_list(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("⛔ دسترسی ندارید.")
    reports = db.get_all()
    if not reports:
        return await msg.answer("📭 هیچ گزارشی وجود ندارد. /add بزنید.")
    text = f"📋 <b>لیست گزارش‌ها ({len(reports)}):</b>\n\n"
    for r in reports:
        text += f"<b>#{r['id']}</b> | {r['subject'][:60]}...\n"
        text += f"   📝 {len(r['body'])} کاراکتر | {r['created'][:10]}\n\n"
    await msg.answer(text, parse_mode="HTML")

@dp.message(Command("delete"))
async def cmd_delete(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("⛔ دسترسی ندارید.")
    reports = db.get_all()
    if not reports:
        return await msg.answer("📭 چیزی برای حذف نیست.")
    # Build inline keyboard
    buttons = []
    for r in reports:
        buttons.append([InlineKeyboardButton(
            text=f"❌ #{r['id']} — {r['subject'][:40]}",
            callback_data=f"del_{r['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🗑 حذف همه", callback_data="del_all")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await msg.answer("🗑 کدام گزارش حذف شود؟", reply_markup=kb)

@dp.callback_query(F.data.startswith("del_"))
async def process_delete(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("⛔", show_alert=True)
    if cb.data == "del_all":
        db.delete_all()
        await cb.message.edit_text("🗑 همه گزارش‌ها حذف شدند.")
    else:
        rid = int(cb.data.split("_")[1])
        if db.delete(rid):
            await cb.message.edit_text(f"✅ گزارش #{rid} حذف شد.")
        else:
            await cb.message.edit_text(f"❌ گزارش #{rid} پیدا نشد.")
    await cb.answer()

@dp.message(Command("clear"))
async def cmd_clear(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("⛔ دسترسی ندارید.")
    db.delete_all()
    await msg.answer("🗑 همه گزارش‌ها حذف شدند.")

@dp.message(Command("stats"))
async def cmd_stats(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("⛔ دسترسی ندارید.")
    reports = db.get_all()
    total_chars = sum(len(r['body']) for r in reports)
    await msg.answer(
        f"📊 <b>آمار:</b>\n\n"
        f"📋 تعداد گزارش‌ها: <b>{len(reports)}</b>\n"
        f"📝 کل کاراکترها: <b>{total_chars}</b>\n"
        f"📧 گیرندگان: <code>{GMAIL_TO}</code>",
        parse_mode="HTML"
    )

@dp.message(Command("link"))
async def cmd_link(msg: Message):
    if not is_admin(msg.from_user.id):
        return await msg.answer("⛔ دسترسی ندارید.")
    await msg.answer(
        f"🔗 <b>لینک صفحه گزارش‌دهی:</b>\n\n"
        f"<code>http://YOUR_SERVER_IP:{WEB_PORT}</code>\n\n"
        f"این لینک را به کاربران بدهید.\n"
        f"هر بار یک گزارش رندوم انتخاب و Gmail App باز می‌شود.",
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════════════════════════════════════
# WEB SERVER (serves HTML + API)
# ═══════════════════════════════════════════════════════════════════════════════
HTML_PAGE = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>گزارش‌ساز خودکار</title>
    <style>
        *{box-sizing:border-box;margin:0}
        body{background:#0a0e17;color:#e7edf9;font-family:'Segoe UI',system-ui,sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px;direction:rtl;text-align:center}
        .container{max-width:620px;width:100%;background:#111827;padding:36px 26px;border-radius:28px;border:1px solid #1e293b;box-shadow:0 20px 40px -12px rgba(0,0,0,.8)}
        h1{font-size:22px;color:#f1f5f9;margin-bottom:10px}
        h1 small{font-size:13px;font-weight:400;color:#94a3b8;background:#1e293b;padding:4px 14px;border-radius:40px}
        .btn{display:inline-block;margin-top:14px;padding:15px 32px;background:#2563eb;color:#fff;border-radius:40px;text-decoration:none;font-weight:600;border:none;cursor:pointer;font-size:17px;transition:.25s;width:100%}
        .btn:hover{background:#1d4ed8;transform:translateY(-2px)}
        .btn-green{background:#059669}.btn-green:hover{background:#047857}
        .info{margin-top:18px;padding:14px 18px;background:#1e293b;border-radius:12px;font-size:12px;color:#94a3b8;text-align:right;line-height:1.8}
        .info strong{color:#e2e8f0}
        .badge{display:inline-block;background:#1d4ed8;padding:5px 18px;border-radius:40px;font-size:13px;color:#fff;margin:12px 0}
        .subject-box{margin-top:12px;padding:12px 16px;background:#0f172a;border-radius:10px;font-size:13px;color:#38bdf8;text-align:left;direction:ltr;border:1px solid #1e3a5f}
        .preview{margin-top:12px;padding:14px 18px;background:#0f172a;border-radius:12px;font-size:12px;color:#cbd5e1;text-align:left;direction:ltr;max-height:180px;overflow-y:auto;line-height:1.7;white-space:pre-wrap;border:1px solid #1e293b}
        .status{margin-top:10px;padding:10px;border-radius:8px;font-size:13px;display:none}
        .status.ok{display:block;background:#064e3b;color:#34d399}
        .status.err{display:block;background:#7f1d1d;color:#fca5a5}
        .counter{font-size:11px;color:#64748b;margin-top:8px}
        .warning{margin-top:14px;padding:14px 18px;background:#1e293b;border-radius:12px;font-size:13px;color:#fcd34d;border-right:4px solid #f59e0b;text-align:right;line-height:1.8}
    </style>
</head>
<body>
<div class="container">
    <h1>📧 گزارش‌ساز خودکار <small>Telegram Report</small></h1>
    <div class="badge" id="deviceBadge">🔍 در حال تشخیص ...</div>

    <div class="info">
        <strong>📌 موضوع:</strong>
        <div class="subject-box" id="subjectText">در حال بارگذاری ...</div>
    </div>

    <div class="info">
        <strong>📝 متن گزارش:</strong>
        <div class="preview" id="previewText">در حال بارگذاری ...</div>
        <div class="counter" id="counterText"></div>
    </div>

    <button class="btn" id="gmailBtn">✉️ باز کردن Gmail (اپلیکیشن)</button>
    <button class="btn btn-green" id="mailtoBtn" style="margin-top:10px">📧 ایمیل پیش‌فرض دستگاه</button>

    <div class="status" id="statusMsg"></div>

    <div class="warning">
        💡 <strong>راهنما:</strong><br>
        • هر بار <strong>موضوع + متن</strong> متفاوت انتخاب می‌شود<br>
        • Gmail <strong>اپلیکیشن</strong> باز می‌شود (نه سایت)<br>
        • فقط دکمه <strong>Send</strong> را بزنید
    </div>
</div>

<script>
(function(){
    const TO = "abuse@telegram.org,reports@telegram.org,stopCA@telegram.org,dmca@telegram.org";
    let SUBJECT = "";
    let BODY = "";
    let idx = 0;
    let total = 0;

    // Detect device
    const ua = navigator.userAgent || navigator.vendor || window.opera;
    const isAndroid = /android/i.test(ua);
    const isIOS = /iPad|iPhone|iPod/.test(ua) && !window.MSStream;
    const badge = document.getElementById('deviceBadge');
    if (isAndroid) badge.textContent = '🤖 اندروید → Gmail App';
    else if (isIOS) badge.textContent = '🍎 آیفون → Mail/Gmail App';
    else badge.textContent = '💻 کامپیوتر → Mail App';

    function enc(s){ return encodeURIComponent(s); }
    function showStatus(msg, ok){
        const el = document.getElementById('statusMsg');
        el.textContent = msg;
        el.className = 'status ' + (ok ? 'ok' : 'err');
    }

    // Fetch reports from API
    async function loadReports(){
        try {
            const resp = await fetch('/api/reports');
            const data = await resp.json();
            if (!data.reports || data.reports.length === 0){
                document.getElementById('subjectText').textContent = '⚠️ هیچ گزارشی ثبت نشده';
                document.getElementById('previewText').textContent = 'ادمین هنوز گزارشی اضافه نکرده.';
                return;
            }
            total = data.reports.length;
            idx = Math.floor(Math.random() * total);
            const report = data.reports[idx];
            SUBJECT = report.subject;
            BODY = report.body;
            document.getElementById('subjectText').textContent = SUBJECT;
            document.getElementById('previewText').textContent = BODY;
            document.getElementById('counterText').textContent =
                '📌 گزارش ' + (idx+1) + ' از ' + total + ' | ' + BODY.length + ' کاراکتر';
        } catch(e){
            document.getElementById('subjectText').textContent = '❌ خطا در بارگذاری';
        }
    }

    // Gmail APP (not website)
    function openGmailApp(){
        if (!SUBJECT || !BODY) { showStatus('⚠️ گزارشی وجود ندارد', false); return; }
        showStatus('⏳ در حال باز کردن Gmail ...', true);

        if (isAndroid) {
            const mailto = 'mailto:' + enc(TO) + '?subject=' + enc(SUBJECT) + '&body=' + enc(BODY.substring(0, 1800));
            const intent = 'intent:' + mailto
                + '#Intent;scheme=mailto;'
                + 'package=com.google.android.gm;'
                + 'action=android.intent.action.SENDTO;'
                + 'S.browser_fallback_url=' + enc(mailto)
                + ';end';
            window.location.href = intent;
        } else if (isIOS) {
            const mailto = 'mailto:' + enc(TO) + '?subject=' + enc(SUBJECT) + '&body=' + enc(BODY.substring(0, 1800));
            window.location.href = mailto;
        } else {
            const mailto = 'mailto:' + enc(TO) + '?subject=' + enc(SUBJECT) + '&body=' + enc(BODY);
            window.location.href = mailto;
        }
    }

    // Default mail app
    function openMailto(){
        if (!SUBJECT || !BODY) { showStatus('⚠️ گزارشی وجود ندارد', false); return; }
        showStatus('⏳ در حال باز کردن ایمیل ...', true);
        const shortBody = BODY.substring(0, 1800);
        window.location.href = 'mailto:' + enc(TO) + '?subject=' + enc(SUBJECT) + '&body=' + enc(shortBody);
    }

    document.getElementById('gmailBtn').addEventListener('click', openGmailApp);
    document.getElementById('mailtoBtn').addEventListener('click', openMailto);

    // Load on page open
    loadReports();

    // Auto-open after 2.5s
    setTimeout(function(){
        if (SUBJECT && BODY) openGmailApp();
    }, 2500);
})();
</script>
</body>
</html>"""

async def handle_index(request):
    return web.Response(text=HTML_PAGE, content_type='text/html')

async def handle_api_reports(request):
    reports = db.get_all()
    return web.json_response({
        'reports': reports,
        'to': GMAIL_TO,
        'count': len(reports),
    })

async def start_web():
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_get('/api/reports', handle_api_reports)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEB_PORT)
    await site.start()
    LOG.info(f"🌐 Web server running on http://0.0.0.0:{WEB_PORT}")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
async def main():
    LOG.info("🤖 Starting ReportBot v2...")
    LOG.info(f"📊 Reports loaded: {db.count()}")
    LOG.info(f"👑 Admins: {ADMIN_IDS}")

    # Start web server
    await start_web()

    # Start bot polling
    LOG.info("🤖 Bot polling started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOG.info("🛑 Stopped.")
