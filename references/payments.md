# Payment routing and fulfillment boundary

Begin with the decision, not an invoice snippet. Do not add payment code,
dependencies, provider credentials, or a checkout flow to a bot that has no
payment requirement.

## Payment decision matrix

| What the product needs | Routing decision |
| --- | --- |
| No payments | Add nothing. |
| In-Telegram digital goods or services | Use Telegram Stars with `currency="XTR"`; do not configure provider credentials. |
| Physical goods or offline services | Use an ordinary currency and a configured, supported payment provider. |
| Explicit external checkout | Use the chosen provider's API and webhook, not a Telegram invoice. |

For every version-sensitive implementation involving digital goods, re-check
the current Telegram policy before shipping. The product classification and the
policy determine the selected route; do not use external checkout to evade a
digital-goods requirement.

## Selected Telegram flow

For in-Telegram digital goods or services, create the invoice only after the
server has selected the product and calculated the amount. Telegram Stars uses
`currency="XTR"` and has no provider credentials. For physical goods or
offline services, use the ordinary currency and configured supported provider
for that business; keep provider credentials in server-side configuration.

```python
await bot.send_invoice(
    chat_id=message.chat.id,
    title=product.title,
    description=product.description,
    payload=order.public_reference,
    currency="XTR",
    prices=[LabeledPrice(label=product.title, amount=product.stars_amount)],
)
```

`payload` is only an opaque correlation reference, not a price or entitlement.
The server must load the order and its amount from durable state. Never trust a
client-provided price or entitlement.

Answer each `pre_checkout_query` after server-side order validation and within
Telegram's documented 10-second window. Acknowledge only an order that is still
valid and payable. Reload durable state, apply the stored payer/recipient
policy, and compare currency and total amount with Telegram's query; deny any
missing, stale, unauthorized, or mismatched order promptly.

```python
@router.pre_checkout_query()
async def confirm_checkout(query: PreCheckoutQuery) -> None:
    order = await orders.get(query.invoice_payload)
    if (
        order is None
        or order.status != "pending"
        or not orders.payer_is_allowed(order=order, payer_id=query.from_user.id)
        or order.currency != query.currency
        or order.total_amount != query.total_amount
    ):
        await query.answer(ok=False, error_message="This order is unavailable.")
        return
    await query.answer(ok=True)
```

`payer_is_allowed` is application policy over the durable order: it can require
the stored payer or allow a payer to buy for the stored recipient. Neither
identity comes from the invoice payload or another client-supplied snapshot.

The pre-checkout acknowledgement is not fulfillment. On every
`successful_payment`, reload the order and compare the payer policy, currency,
and total amount again before granting the product. Treat a mismatch as an
incident to record and investigate, not as a paid entitlement.

```python
@router.message(F.successful_payment)
async def confirm_success(message: Message) -> None:
    payment = message.successful_payment
    order = await orders.get(payment.invoice_payload)
    if (
        order is None
        or not orders.payer_is_allowed(order=order, payer_id=message.from_user.id)
        or order.currency != payment.currency
        or order.total_amount != payment.total_amount
    ):
        raise PaymentContractMismatch(payment.invoice_payload)

    await orders.fulfill_paid_order_once(
        order_id=order.id,
        telegram_charge_id=payment.telegram_payment_charge_id,
        provider_charge_id=(payment.provider_payment_charge_id or None),
    )
```

`fulfill_paid_order_once` runs in one database transaction and is idempotent:
`telegram_payment_charge_id` is the universal Telegram-payment idempotency key;
record it under a unique constraint while advancing durable order state and
granting the entitlement atomically. `provider_payment_charge_id` can be empty
for Stars (`XTR`), so persist it only when nonempty as an optional, nullable
field. When a provider ID applies, use provider-scoped uniqueness over non-null
values. A duplicate event returns the recorded result rather than granting
twice.

## External checkout boundary

When the explicit decision is external checkout, integrate the chosen
provider's API and webhook instead of creating a Telegram invoice. Verify the
provider webhook signature, resolve the provider event to durable server-side
order state, and reconcile payment and fulfillment state idempotently using
the provider's stable charge or event identifier. Do not grant an entitlement
from a browser return URL, a client callback, or an unverified webhook.

Consult Telegram's [Payments guide](https://core.telegram.org/bots/payments),
[Stars guide](https://core.telegram.org/bots/payments-stars), and
[pre-checkout API reference](https://core.telegram.org/bots/api#precheckoutquery)
before implementing a version-specific flow.
