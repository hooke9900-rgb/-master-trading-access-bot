import json
import logging
import os
import time
from typing import Any, Dict

import requests

BOT_TOKEN = os.environ["BOT_TOKEN"].strip()
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

RULES_TEXT = """MASTER TRADING — ՄՈՒՏՔԻ ԿԱՆՈՆՆԵՐ

Խմբին միանալու համար խնդրում ենք կարդալ և հաստատել կանոնները։

Խմբում արգելվում է՝

1. Տրամադրել կոնկրետ առք/վաճառքի ազդանշաններ կամ հրահանգներ։
2. Նշել կոնկրետ մուտքի կամ ելքի գներ որպես գործողության հրահանգ։
3. Տրամադրել SL / TP մակարդակներ որպես անհատական առևտրային խորհուրդ։
4. Գնի ուղղությունը ներկայացնել որպես երաշխավորված՝ «հաստատ կբարձրանա», «հաստատ կիջնի» և նման ձևակերպումներով։
5. Տալ անհատական ռիսկի հաշվարկ, դիրքի չափ, լծակի չափ կամ ասել՝ որքան գումար/տոկոս օգտագործել կոնկրետ գործարքում։
6. Տրամադրել անհատական ֆինանսական, ներդրումային կամ առևտրային խորհրդատվություն։
7. Երաշխավորել շահույթ կամ որևէ գործարք ներկայացնել որպես «առանց ռիսկի», «100% անվտանգ» կամ «100% շահութաբեր»։
8. Կառավարել այլ մասնակցի հաշիվը կամ պահանջել API key, գաղտնաբառ, seed phrase կամ այլ գաղտնի տվյալ։
9. Առանց թույլտվության տարածել գովազդ, referral հղումներ, վճարովի ազդանշաններ կամ այլ խմբերի/ծառայությունների առաջարկներ։
10. Հրապարակել այլ մասնակցի անձնական կամ ֆինանսական տվյալները առանց նրա համաձայնության։
11. Վիրավորանք, սպամ, սադրանք և խմբի աշխատանքը խանգարող վարքագիծ։

Թույլատրվում է քննարկել շուկայի կառուցվածքը, տեխնիկական և ֆունդամենտալ տվյալները, order flow-ը, liquidity-ն, ռիսկի կառավարման ընդհանուր սկզբունքները և կրթական նյութերը՝ առանց կոնկրետ անհատական գործողության հրահանգի։

Խմբում հրապարակվող տեղեկատվությունը կրթական և տեղեկատվական բնույթ ունի և չի հանդիսանում ֆինանսական կամ ներդրումային խորհրդատվություն։

Շարունակելով՝ հաստատում եք, որ կարդացել և ընդունում եք կանոնները։
"""

AGREE_TEXT = "✅ Կարդացի և համաձայն եմ"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("master-trading-access")


def api(method: str, **data: Any) -> Dict[str, Any]:
    response = requests.post(f"{API}/{method}", json=data, timeout=35)
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API error in {method}: {payload}")
    return payload


def send_rules(join_request: Dict[str, Any]) -> None:
    chat_id = int(join_request["chat"]["id"])
    user_id = int(join_request["from"]["id"])
    user_chat_id = int(join_request["user_chat_id"])

    # callback_data must be <= 64 bytes. These numeric IDs easily fit.
    callback_data = f"agree:{chat_id}:{user_id}"

    keyboard = {
        "inline_keyboard": [[
            {"text": AGREE_TEXT, "callback_data": callback_data}
        ]]
    }

    api(
        "sendMessage",
        chat_id=user_chat_id,
        text=RULES_TEXT,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    log.info("Rules sent to applicant user_id=%s for chat_id=%s", user_id, chat_id)


def handle_callback(query: Dict[str, Any]) -> None:
    data = query.get("data", "")
    if not data.startswith("agree:"):
        return

    try:
        _, chat_id_raw, user_id_raw = data.split(":", 2)
        chat_id = int(chat_id_raw)
        expected_user_id = int(user_id_raw)
    except Exception:
        api(
            "answerCallbackQuery",
            callback_query_id=query["id"],
            text="Սխալ տվյալներ։ Փորձեք կրկին։",
            show_alert=True,
        )
        return

    actual_user_id = int(query["from"]["id"])
    if actual_user_id != expected_user_id:
        api(
            "answerCallbackQuery",
            callback_query_id=query["id"],
            text="Այս կոճակը նախատեսված չէ Ձեր հաշվի համար։",
            show_alert=True,
        )
        return

    try:
        api(
            "approveChatJoinRequest",
            chat_id=chat_id,
            user_id=actual_user_id,
        )

        api(
            "answerCallbackQuery",
            callback_query_id=query["id"],
            text="✅ Մուտքը հաստատված է",
        )

        msg = query.get("message")
        if msg:
            api(
                "editMessageText",
                chat_id=msg["chat"]["id"],
                message_id=msg["message_id"],
                text=(
                    "✅ Դուք կարդացել և ընդունել եք MASTER TRADING-ի կանոնները։\n\n"
                    "Ձեր մուտքի հայտը հաստատված է։ Կարող եք մտնել խումբ։"
                ),
            )

        log.info("Approved user_id=%s for chat_id=%s", actual_user_id, chat_id)

    except Exception as exc:
        log.exception("Approval failed: %s", exc)
        try:
            api(
                "answerCallbackQuery",
                callback_query_id=query["id"],
                text=(
                    "Չհաջողվեց հաստատել մուտքը։ "
                    "Հնարավոր է հայտը արդեն մշակված է կամ բոտին պակասում է իրավունքը։"
                ),
                show_alert=True,
            )
        except Exception:
            pass


def main() -> None:
    # Long polling requires no active webhook.
    # IMPORTANT: If another service uses a webhook for this SAME bot,
    # do not run this script with that token; use a separate admission bot.
    try:
        info = api("getWebhookInfo")["result"]
        if info.get("url"):
            raise RuntimeError(
                "This bot currently has an active webhook. "
                "Use a separate admission bot or disable the other service's webhook."
            )
    except RuntimeError:
        raise
    except Exception:
        log.exception("Could not check webhook info")
        raise

    offset = None
    log.info("Bot started. Waiting for join requests...")

    while True:
        try:
            payload = {
                "timeout": 30,
                "allowed_updates": ["chat_join_request", "callback_query"],
            }
            if offset is not None:
                payload["offset"] = offset

            updates = api("getUpdates", **payload)["result"]

            for update in updates:
                offset = update["update_id"] + 1

                if "chat_join_request" in update:
                    try:
                        send_rules(update["chat_join_request"])
                    except Exception:
                        log.exception("Failed to send rules")

                elif "callback_query" in update:
                    handle_callback(update["callback_query"])

        except requests.RequestException:
            log.exception("Network error; retrying in 5 seconds")
            time.sleep(5)
        except Exception:
            log.exception("Unexpected error; retrying in 5 seconds")
            time.sleep(5)


if __name__ == "__main__":
    main()
