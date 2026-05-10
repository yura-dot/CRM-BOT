from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from models.database import get_db
from keyboards.admin_kb import invoice_status_kb
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
    if message.text != "/skip":
        await state.update_data(due_date=message.text.strip())
    await message.answer("Введіть <b>примітку до рахунку</b> або /skip:", parse_mode="HTML")
    await state.set_state(InvoiceStates.notes)

@router.message(InvoiceStates.notes)
async def invoice_notes(message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(notes=message.text.strip())
    data = await state.get_data()
    order_id = data["invoice_order_id"]
    await state.clear()
    await _generate_and_send_invoice(message, order_id, data)

async def _generate_and_send_invoice(message, order_id: int, data: dict):
    inv_number = generate_invoice_number()
    today = date.today().strftime("%d.%m.%Y")

    async with get_db() as db:
        db.row_factory = "dict"
        cur = await db.execute("""SELECT o.*, u.first_name, u.last_name, u.phone, u.email, u.company_id
            FROM orders o JOIN users u ON o.user_id=u.id WHERE o.id=?""", (order_id,))
        order = await cur.fetchone()
        cur2 = await db.execute("""SELECT oi.*, p.name FROM order_items oi
            JOIN products p ON oi.product_id=p.id WHERE oi.order_id=?""", (order_id,))
        items = await cur2.fetchall()
        cur3 = await db.execute("SELECT * FROM fop_settings WHERE id=1")
        fop = dict(await cur3.fetchone())
        buyer = {"name": f"{order['first_name']} {order['last_name']}", "edrpou": "", "iban": "", "address": "", "phone": order.get("phone","")}
        if order.get("company_id"):
            cur4 = await db.execute("SELECT * FROM companies WHERE id=?", (order["company_id"],))
            co = await cur4.fetchone()
            if co:
                co = dict(co)
                buyer = {"name": co.get("display_name") or co["name"], "edrpou": co.get("edrpou",""), "iban": co.get("iban",""), "address": co.get("legal_address",""), "phone": co.get("phone","")}
        cur5 = await db.execute("SELECT telegram_id FROM users WHERE id=?", (order["user_id"],))
        client_tg = (await cur5.fetchone())[0]

        await db.execute("""INSERT INTO invoices (invoice_number,order_id,invoice_date,due_date,total_amount,status,notes)
            VALUES (?,?,?,?,?,'draft',?)""",
            (inv_number, order_id, today, data.get("due_date",""), order["total_amount"], data.get("notes","")))
        await db.commit()
        cur6 = await db.execute("SELECT id FROM invoices WHERE invoice_number=?", (inv_number,))
        inv_id = (await cur6.fetchone())[0]

    purpose = (fop.get("payment_template") or "Оплата за замовленням №{order_number}").replace("{order_number}", order["order_number"])

    pdf_data = {
        "invoice_number": inv_number,
        "invoice_date": today,
        "due_date": data.get("due_date",""),
        "seller": {"name": fop.get("fop_name",""), "edrpou": fop.get("edrpou",""), "iban": fop.get("iban",""), "address": fop.get("legal_address",""), "phone": fop.get("phone","")},
        "buyer": buyer,
        "items": [{"name": i["name"], "qty": i["quantity"], "price": i["unit_price"], "subtotal": i["subtotal"]} for i in items],
        "total": order["total_amount"],
        "payment_purpose": purpose,
        "notes": data.get("notes",""),
    }
    pdf_bytes = generate_invoice_pdf(pdf_data)
    pdf_file = BufferedInputFile(pdf_bytes, filename=f"invoice_{inv_number}.pdf")

    await message.answer_document(pdf_file, caption=f"✅ Рахунок <b>#{inv_number}</b> створено!", parse_mode="HTML",
                                  reply_markup=invoice_status_kb(inv_id))
    try:
        await message.bot.send_document(
            client_tg, pdf_file,
            caption=f"🧾 <b>Рахунок на оплату №{inv_number}</b>\n\n"
                    f"💰 Сума: <b>{order['total_amount']:.2f} грн</b>\n"
                    f"🏦 IBAN: <code>{fop.get('iban','—')}</code>\n"
                    f"💬 Призначення: {purpose}",
            parse_mode="HTML"
        )
    except Exception:
        pass

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
    await callback.answer("✅ Статус: Оплачений", show_alert=False)
