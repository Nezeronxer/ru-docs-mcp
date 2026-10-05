# GigaChat API

## Токен берут POST-формой с обязательным RqUID (uuid4); он живёт 30 минут
`POST https://ngw.devices.sberbank.ru:9443/api/v2/oauth`, тело - форма (`application/x-www-form-urlencoded`), `scope` - поле формы.
`RqUID` - обязательный заголовок, uuid4, значение генерируете сами; `Authorization: Basic <ключ_авторизации>`.
Токен действует 30 минут: кэшируйте и обновляйте заранее, а не запрашивайте на каждый вызов.
Источник: https://developers.sber.ru/docs/ru/gigachat/api/authorization
Проверено: 2026-10-05

## scope должен совпадать с типом ключа: PERS, B2B или CORP
`GIGACHAT_API_PERS` - физлица, `GIGACHAT_API_B2B` - ИП и юрлица по предоплате, `GIGACHAT_API_CORP` - по постоплате.
Если scope не соответствует ключу, токен не выдаётся: `scope from db not fully includes consumed scope`.
`GET /balance` при оплате pay-as-you-go отвечает `403 Permission denied`: остатка предоплаченных токенов там нет.
Источник: https://developers.sber.ru/docs/ru/gigachat/api/errors-description
Проверено: 2026-10-05

## Нужен корневой сертификат Минцифры, но проверку TLS отключать нельзя
Без корня НУЦ Минцифры токен не получить: `[SSL: CERTIFICATE_VERIFY_FAILED] ... self-signed certificate in certificate chain`.
Не отключайте проверку (в документации есть пример с `NODE_TLS_REJECT_UNAUTHORIZED = '0'` - не копировать). Передавайте корень
как CA-bundle только клиенту, который ходит в GigaChat (SDK: `ca_bundle_file="/путь/к/файлу/russian_trusted_root_ca_pem.crt"`),
а не в системное хранилище и не в общий certifi.
Источник: https://developers.sber.ru/docs/ru/gigachat/certificates
Проверено: 2026-10-05

## Лимит - число одновременных потоков (1 у физлиц, 10 у ИП и юрлиц), превышение даёт 429
`429 Too Many Requests` приходит, когда число одновременных запросов превышает лимит для вашего `client_id`:
по умолчанию 1 поток у физлиц, 10 у ИП и юрлиц. Ограничьте параллелизм семафором на стороне клиента.
Токен можно запрашивать до 10 раз в секунду.
Источник: https://developers.sber.ru/docs/ru/gigachat/api/errors-description
Проверено: 2026-10-05

## С 17.07.2026 адрес API - api.giga.chat, и без заголовка User-Agent он отвечает 403
С 17 июля 2026 целевой адрес - `https://api.giga.chat`; старый `gigachat.devices.sberbank.ru` остаётся для подключившихся
раньше, но будет выведен. На `api.giga.chat` ответ `403 {"message": "Unauthorized"}` лечится заголовком `User-Agent`
с любым значением.
Источник: https://developers.sber.ru/docs/ru/gigachat/api/errors-description
Проверено: 2026-10-05

## Для stream передайте "stream": true; поток - SSE и заканчивается строкой data: [DONE]
В `POST /chat/completions` добавьте `"stream": true`: ответ придёт как `text/event-stream`, куски текста - отдельными
событиями `data: {...}`. Последним приходит `data: [DONE]` - это не JSON, обработайте его до разбора тела события.
Источник: https://developers.sber.ru/docs/ru/gigachat/guides/response-token-streaming
Проверено: 2026-10-05
