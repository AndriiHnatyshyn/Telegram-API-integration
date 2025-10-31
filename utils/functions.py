import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import phonenumbers
from phonenumbers import geocoder
from jinja2 import Template
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')  # "kravchik.orest@gmail.com"
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')  # "szdd ygxb tjjt zend"
SMTP_SERVER = os.getenv('SMTP_SERVER')  # "smtp.gmail.com"
SMTP_PORT = os.getenv('SMTP_PORT')  # 587


async def send_verification_email(to_email: str, verification_link: str):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg['Subject'] = 'Email Verification'

    template = Template(Path("api/templates/verification_email.html").read_text())
    html_content = template.render(verification_link=verification_link)
    msg.attach(MIMEText(html_content, 'html'))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())


async def is_us_state(phone_number: str) -> bool:
    us_country_code = 'US'
    parsed_number = phonenumbers.parse(phone_number)
    country_code = geocoder.country_name_for_number(parsed_number, 'en')
    return country_code == us_country_code


async def get_country_from_phone_number(phone_number: str) -> str:
    try:
        parsed_number = phonenumbers.parse(phone_number)
        country = geocoder.description_for_number(parsed_number, 'en')
        if await is_us_state(phone_number):
            return "United States"
        return country
    except phonenumbers.phonenumberutil.NumberParseException:
        return "Invalid phone number"
