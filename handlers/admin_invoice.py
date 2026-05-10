from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from models.database import get_db
from keyboards.admin_kb import invoice_status_kb, order_status_kb
from utils.states import InvoiceStates
from utils.helpers import generate_invoice_number
from utils.pdf_generator import generate_invoice_pdf
from datetime import date

router = Router()

@router.callback_query(F.data.startswith("create_invoice_"))
async def create_invoice_start(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[2])
    async with get_db() as db:
        cur = await db.execute("SELECT id FROM invoices WHERE order_id=?", (order_id,))
        existing = await cur.fetchone()
    if existing:
        await callback.answer("Рахунок для цього замовлення вже існує!", show_alert=True)
        return
    await state.update_data(invoice_order_id=order_id)
    await callback.message.answer(
        "🧾 Створення рахунку\n\n"
        "Введіть <b>дату оплати до</b> (напр. 20.05.2026) або /skip:",
        parse_mode="HTML"
    )
    await state.set_state(InvoiceStates.due_date)

@router.message(InvoiceStates.due_date)
async def invoice_due_date(message, state: FSMContext):
    if message.text.strip() != "/skip":
        await state.update_data(due_date=message.text.strip())
    await message.answer("Введіть <b>примітку до рахунку</b> або /skip:", parse_mode="HTML")
    await state.set_state(InvoiceStates.notes)

@router.message(InvoiceStates.notes)
async def invoice_notes(message, state: FSMContext):
    if message.text.strip() != "/skip":
        await state.update_data(notes=message.text.strip())
    data = await state.get_data()
    order_id = data["invoice_order_id"]
    await state.clear()
    await _generate_and_send_invoice(message, order_id, data)

async def _generate_and_send_invoice(message_or_cb, order_id: int, extra: dict = None, auto: bool = False):
    """
    Генерує рахунок і надсилає адміну + клієнту.
    auto=True — викликається автоматично при підтвердженні замовлення.
    """
    if extra is None:
        extra = {}

    inv_number = generate_invoice_number()
    today = date.today().strftime("%d.%m.%Y")

    async with get_db() as db:
        cur = await db.execute("""SELECT o.*, u.first_name, u.last_name, u.phone, u.email, u.company_id
            FROM orders o JOIN users u ON o.user_id=u.id WHERE o.id=?""", (order_id,))
        order = await cur.fetchone()
        cur2 = await db.execute("""SELECT oi.*, p.name FROM order_items oi
            JOIN products p ON oi.product_id=p.id WHERE oi.order_id=?""", (order_id,))
        items = await cur2.fetchall()
        cur3 = await db.execute("SELECT * FROM fop_settings WHERE id=1")
        fop = await cur3.fetchone() or {}

        buyer = {
            "name": f"{order['first_name']} {order['last_name']}",
            "edrpou": "", "iban": "",
            "address": "", "phone": order.get("phone","")
        }
        if order.get("company_id"):
            cur4 = await db.execute("SELECT * FROM companies WHERE id=?", (order["company_id"],))
            co = await cur4.fetchone()
            if co:
                co = dict(co)
                buyer = {
                    "name": co.get("display_name") or co["name"],
                    "edrpou": co.get("edrpou",""),
                    "iban": co.get("iban",""),
                    "address": co.get("legal_address",""),
                    "phone": co.get("phone","")
                }

        cur5 = await db.execute("SELECT telegram_id FROM users WHERE id=?", (order["user_id"],))
        client_tg_row = await cur5.fetchone()
        client_tg = client_tg_row["telegram_id"] if client_tg_row else None

        await db.execute(
            """INSERT INTO invoices (invoice_number,order_id,invoice_date,due_date,total_amount,status,notes)
               VALUES (?,?,?,?,?,'draft',?)""",
            (inv_number, order_id, today,
             extra.get("due_date",""), order["total_amount"], extra.get("notes",""))
        )
        await db.commit()
        cur6 = await db.execute("SELECT id FROM invoices WHERE invoice_number=?", (inv_number,))
        inv_row = await cur6.fetchone()
        inv_id = inv_row["id"] if inv_row else None

    # Призначення платежу: фіксований формат
    purpose = f"Оплата за товар згідно рахунку {inv_number} від {today}"

    pdf_data = {
        "invoice_number": inv_number,
        "invoice_date": today,
        "due_date": extra.get("due_date",""),
        "seller": {
            "name": fop.get("fop_name",""),
            "edrpou": fop.get("edrpou",""),
            "iban": fop.get("iban",""),
            "address": fop.get("legal_address",""),
            "phone": fop.get("phone",""),
        },
        "buyer": buyer,
        "items": [{"name": i["name"], "qty": i["quantity"], "price": i["unit_price"], "subtotal": i["subtotal"]} for i in items],
        "total": order["total_amount"],
        "payment_purpose": purpose,
        "notes": extra.get("notes",""),
    }
    pdf_bytes = generate_invoice_pdf(pdf_data)
    pdf_file = BufferedInputFile(pdf_bytes, filename=f"invoice_{inv_number}.pdf")

    caption_admin = (
        f"✅ Рахунок <b>#{inv_number}</b> {'(авто) ' if auto else ''}створено!"
    )
    caption_client = (
        f"🧾 <b>Рахунок на оплату №{inv_number}</b>\n\n"
        f"💰 Сума: <b>{order['total_amount']:.2f} грн</b>\n"
        f"🏦 IBAN: <code>{fop.get('iban','—')}</code>\n"
        f"💬 Призначення:\n<code>{purpose}</code>"
    )

    if hasattr(message_or_cb, "answer"):
        await message_or_cb.answer_document(
            pdf_file, caption=caption_admin, parse_mode="HTML",
            reply_markup=invoice_status_kb(inv_id) if inv_id else None
        )
    else:
        await message_or_cb.message.answer_document(
            pdf_file, caption=caption_admin, parse_mode="HTML",
            reply_markup=invoice_status_kb(inv_id) if inv_id else None
        )

    # Надсилаємо клієнту
    if client_tg:
        try:
            bot = message_or_cb.bot if hasattr(message_or_cb, "bot") else message_or_cb.message.bot
            await bot.send_document(
                client_tg, pdf_file,
                caption=caption_client,
                parse_mode="HTML"
            )
        except Exception:
            pass

    return inv_number

@router.callback_query(F.data.startswith("inv_sent_"))
async def inv_mark_sent(callback: CallbackQuery):
    inv_id = int(callback.data.split("_")[2])
    async with get_db() as db:
        await db.execute("UPDATE invoices SET status='sent' WHERE id=?", (inv_id,))
        await db.commit()
    await callback.answer("📤 Статус: Відправлений", show_alert=False)

@router.callback_query(F.data.startswith("inv_paid_"))
async def inv_mark_paid(callback: CallbackQuery):
    inv_id = int(callback.data.split("_")[2])
    async with get_db() as db:
        await db.execute("UPDATE invoices SET status='paid' WHERE id=?", (inv_id,))
        await db.commit()
    await callback.answer("✅ Статус рахунку: Оплачений", show_alert=False)
