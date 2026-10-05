# Яндекс Пэй (Merchant API и Yandex Pay API)

## Тело вебхука - JWT (ES256), а не JSON: проверяйте подпись по JWKS
Тело приходит как `application/octet-stream` с JWT, подписанным ES256. Ключ выбирают по `alg` и `kid` из
JWKS: `https://pay.yandex.ru/api/jwks` (прод) и `https://sandbox.pay.yandex.ru/api/jwks` (тест). После
проверки подписи сверьте `merchantId` в payload с ID своего продавца.
Источник: https://pay.yandex.ru/docs/ru/custom/backend/merchant-api/index
Проверено: 2026-10-05

## Callback URL указывать без /v1/webhook и только с доверенным сертификатом
Путь `/v1/webhook` добавится автоматически: адрес с ним превратится в `/v1/webhook/v1/webhook`.
Самоподписанные SSL-сертификаты система не распознает, нужен сертификат от доверенного центра.
Источник: https://pay.yandex.ru/docs/ru/custom/backend/merchant-api/webhook
Проверено: 2026-10-05

## Вебхук надо подтверждать HTTP 200, иначе повторы идут 24 часа
`200` (тело любое, рекомендуют `{"status": "success"}`) останавливает повторы. Нет ответа или не `200` -
шлют снова с новым JWT: 10 раз через 5 мс, затем с растущим интервалом до 15 минут, затем каждые
15 минут; всего 24 часа, после чего вебхук считается недоставленным. При ошибке отвечайте 4xx с `reasonCode`.
Источник: https://pay.yandex.ru/docs/ru/custom/backend/merchant-api/webhook
Проверено: 2026-10-05

## Авторизация по Api-Key, в sandbox ключ - Merchant ID, перезапросы с тем же X-Request-Id
Заголовок `Authorization: Api-Key <ключ>` обязателен, без него или с неверным ключом - `401`. В тестовой
среде в качестве API-ключа используется Merchant ID магазина. При перезапросах после `5xx` или `429`
сохраняйте тот же `X-Request-Id`.
Источник: https://pay.yandex.ru/docs/ru/custom/backend/yandex-pay-api/index
Проверено: 2026-10-05

## Суммы - строки, цена за единицу максимум 2 знака, минимум 1 рубль
Суммы в заказе - строки типа `string<double>` (`"100.00"`). Цена за единицу `total / quantity.count`
не больше 2 знаков, иначе `ORDER_CART_DATA_ERROR`. Заказ с `amount: "0"` создать нельзя, минимум 1 рубль,
а `amount` + `externalAmount` должны равняться сумме всех `items`.
Источник: https://pay.yandex.ru/docs/ru/custom/backend/yandex-pay-api/order/merchant_v1_orders-post
Проверено: 2026-10-05

## Возврат: один за раз, externalOperationId - ключ идемпотентности
Пока прошлый возврат по заказу не завершён (`status` не `SUCCESS` и не `FAIL`), новый даст `409` с
`ANOTHER_OPERATION_IN_PROGRESS`. Повтор незавершённой операции с тем же `externalOperationId` идемпотентен,
повтор уже запущенной вернёт `DUPLICATE_EXTERNAL_OPERATION_ID`. Нельзя вернуть меньше 1 рубля и оставить в заказе меньше 1 рубля.
Источник: https://pay.yandex.ru/docs/ru/custom/backend/yandex-pay-api/order/merchant_v2_refund-post
Проверено: 2026-10-05
