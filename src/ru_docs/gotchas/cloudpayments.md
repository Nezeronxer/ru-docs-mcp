# CloudPayments

## Уведомления подписаны: проверять Content-HMAC
Все уведомления (check, pay, fail, confirm, cancel, refund, recurrent) приходят с заголовками
`Content-HMAC` и `X-Content-HMAC` - HMAC-SHA256 тела запроса в base64, ключ - API Secret.
`Content-HMAC` считается от тела как пришло (URL-encoded), `X-Content-HMAC` - от URL-decoded
параметров. Считайте HMAC от **сырого** тела запроса до любого парсинга, сравнивайте
`hmac.compare_digest`. Без проверки любой POST «оплатит» заказ.
Источник: https://developers.cloudpayments.ru/
Проверено: 2026-10-04

## На уведомление отвечать JSON {"code":0}
Система ждёт JSON с обязательным `code`. Для check: `0` - платёж можно проводить, другие коды
отклоняют (неверный номер заказа, сумма и т.д.). Для pay/fail/refund допустим только `0`.
Ответ не тем форматом = уведомление считается необработанным.
Источник: https://developers.cloudpayments.ru/
Проверено: 2026-10-04

## API: Basic Auth, логин Public ID, пароль API Secret
Запросы к API - HTTP Basic: логин **Public ID**, пароль **API Secret** (оба в личном кабинете).
API Secret не должен попадать на фронтенд: на клиенте только Public ID (виджет, криптограмма).
Исключения - методы вроде ссылки на оплату Долями: там Basic Auth нет, а `PublicId` идёт в теле.
Источник: https://developers.cloudpayments.ru/
Проверено: 2026-10-04

## Check - это вопрос «можно ли провести», а не факт оплаты
Уведомление `check` приходит до авторизации: проверьте заказ и сумму и ответьте кодом. Факт оплаты -
только `pay` (или `confirm` при двухстадийной схеме). Выдавать товар по `check` нельзя.
Источник: https://developers.cloudpayments.ru/
Проверено: 2026-10-04
