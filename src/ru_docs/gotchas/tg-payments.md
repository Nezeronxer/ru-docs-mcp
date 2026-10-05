# Платежи в Telegram-ботах

## answerPreCheckoutQuery - за 10 секунд, иначе платёж отменится
После нажатия «Оплатить» бот получает `pre_checkout_query` и обязан ответить
`answerPreCheckoutQuery` в течение 10 секунд. Не делайте в этом обработчике долгих запросов
(внешние API, тяжёлые запросы к БД) - сначала ответьте, потом работайте.
Источник: https://core.telegram.org/bots/payments
Проверено: 2026-10-04

## Цифровые товары - только Telegram Stars (XTR)
Оплата цифровых товаров и услуг в Telegram должна идти исключительно в Stars: `currency: "XTR"`,
`provider_token` - пустая строка. Карта через ЮKassa в sendInvoice - для физических товаров и услуг
вне Telegram; для подписки на цифровой контент нужен Stars или внешняя оплата (redirect).
Источник: https://core.telegram.org/bots/payments-stars
Проверено: 2026-10-04

## Сохраняйте telegram_payment_charge_id
Из `successful_payment` сохраните `telegram_payment_charge_id` - без него не сделать возврат Stars
(`refundStarPayment`).
Источник: https://core.telegram.org/bots/payments-stars
Проверено: 2026-10-04

## Провайдер ЮKassa в sendInvoice - это только карта
Встроенный платёж Telegram с provider_token ЮKassa даёт оплату картой. Для СБП, SberPay, ЮMoney
создавайте платёж через API ЮKassa v3 с redirect-подтверждением и отправляйте ссылку кнопкой.
Источник: https://yookassa.ru/developers/payment-acceptance/getting-started/payment-methods
Проверено: 2026-10-04 (на реальном боте)
