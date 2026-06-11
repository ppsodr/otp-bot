import imaplib, email, re, time, requests, logging
from email.header import decode_header
from datetime import datetime, timezone

GMAIL_ADDRESS    = "l03875367@gmail.com"
GMAIL_APP_PASS   = "snpi lvcx zqnt ohnf"
TELEGRAM_TOKEN   = "8619581763:AAH7GPAUR9mQtrFIu4ajPXOFwCoBpkGrWwY"
TELEGRAM_CHAT_ID = "-5118195489"
POLL_INTERVAL    = 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

OTP_KEYWORDS = ["code", "otp", "verification", "authentification", "connexion", "login", "confirm", "securite", "security", "2fa", "pin"]

def extract_codes(text):
    found = set()
    for m in re.finditer(r"(?<!\d)(\d{5,8})(?!\d)", text):
        code = m.group(1)
        if re.match(r"^(19|20)\d{2}$", code):
            continue
        found.add(code)
    return list(found)

def decode_str(s):
    parts = decode_header(s or "")
    result = ""
    for part, enc in parts:
        if isinstance(part, bytes):
            result += part.decode(enc or "utf-8", errors="replace")
        else:
            result += part
    return result

def get_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() in ("text/plain", "text/html"):
                payload = part.get_payload(decode=True)
                if payload:
                    text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                    text = re.sub(r'<[^>]+>', ' ', text)
                    body += text
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return body

def is_otp_email(subject, body):
    text = (subject + " " + body[:500]).lower()
    return any(k in text for k in OTP_KEYWORDS)

def send_telegram(sender, subject, codes):
    codes_str = " | ".join([f"`{c}`" for c in codes])
    text = (
        f"*Code OTP detecte*\n\n"
        f"*De :* {sender}\n"
        f"*Objet :* {subject}\n"
        f"*Code(s) :* {codes_str}"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    if r.status_code == 200:
        log.info("Code(s) %s envoyes sur Telegram.", codes)
    else:
        log.error("Erreur Telegram %s : %s", r.status_code, r.text)

def connect_imap():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(GMAIL_ADDRESS, GMAIL_APP_PASS.replace(" ", ""))
    return mail

def check_new_emails(mail, seen_ids):
    mail.select("INBOX")
    _, data = mail.search(None, "(UNSEEN)")
    ids = data[0].split() if data[0] else []
    for uid in ids:
        if uid in seen_ids:
            continue
        seen_ids.add(uid)
        _, msg_data = mail.fetch(uid, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        sender  = decode_str(msg.get("From", ""))
        subject = decode_str(msg.get("Subject", ""))
        body    = get_body(msg)
        if not is_otp_email(subject, body):
            continue
        codes = extract_codes(subject + " " + body[:1000])
        if codes:
            log.info("Code(s) de %s : %s", sender, codes)
            send_telegram(sender, subject, codes)

def main():
    log.info("Demarrage bot Gmail OTP -> Telegram...")
    seen_ids = set()
    mail = None
    while True:
        try:
            if mail is None:
                mail = connect_imap()
                log.info("Connecte a Gmail. Surveillance demarree.")
            check_new_emails(mail, seen_ids)
        except imaplib.IMAP4.abort:
            mail = None
        except Exception as e:
            log.error("Erreur : %s", e)
            mail = None
            time.sleep(60)
            continue
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Bot arrete.")
