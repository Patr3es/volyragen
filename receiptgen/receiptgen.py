import asyncio
import json
import string
from datetime import datetime, timedelta
from random import randint, choice
from urllib.parse import urlparse

import aiohttp
import hikari
import miru
from bs4 import BeautifulSoup
from email.message import EmailMessage

from receiptgen import utils, input_validator

class ReceiptModal(miru.Modal):
    """Universal modal for brand-specific forms."""

    def __init__(self, brand):
        super().__init__(title=brand.title)
        self.brand = brand

    async def callback(self, ctx: miru.ModalContext) -> None:
        await self.brand.user_input_validation([text_input for text_input, value in ctx.values.items()])
        await ctx.edit_response()


class Brand:
    def __init__(self):
        self.user_input = None
        self.default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
                          ' like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }
        self.spoof = False

        self.address_placeholder1 = "1. Street\n2. City\n3. Zip Code\n4. Country"
        self.address_placeholder2 = "1. Street\n2. City\n3. Country & Zip Code"
        self.address_placeholder3 = "1. Street\n2. City\n3. Country"
        self.title = "Default"

    async def user_input_validation(self, text_inputs: list) -> None:
        await self.user_input.validate(text_inputs)

    @staticmethod
    def get_template(name, spoof) -> str:
        with open(f"receiptgen/templates/{name}.html", "r", encoding="utf-8") as template_file:
            template = template_file.read()

        return template

    def set_spoof(self, enabled=True):
        self.spoof = enabled

    @staticmethod
    async def send_email(to_email, html_content, subject, sender_name, spoofed_email=None):
        smtp_server = ""
        smtp_port = 587
        smtp_user = ""
        smtp_password = ""

        msg = EmailMessage()
        msg["From"] = f"{sender_name} <{smtp_user}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Sender"] = smtp_user
        msg["Reply-To"] = f"{sender_name} <{smtp_user}>"
        msg.set_content("plain text email, this shouldn't be visible")
        msg.add_alternative(html_content, subtype='html')

        smtp = None
        try:
            smtp = aiohttp.ClientSession()
            await smtp.connect()

            if not smtp:
                await smtp.starttls()

            await smtp.login(smtp_user, smtp_password)
            await smtp.send_message(msg)

        except Exception:
            raise utils.GenerationError("email")

        finally:
            if smtp:
                await smtp.quit()

    async def fetch_web(
            self,
            headers: Optional[dict] = None,
            url: Optional[str] = None,
            params: Optional[dict] = None,
    ):
        if headers is None:
            headers = self.default_headers

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url=url, headers=headers, params=params) as response:
                    if response.status != 200:
                        raise aiohttp.ClientConnectionError

                    data = await response.text(encoding="utf-8")
        except Exception as e:
            raise e

        return data


class UserInput:
    error: bool
    validated: dict
    error_documentations: list

    def __init__(self):
        self.error_documentations = []
        self.validated = {}
        self.error = False
        self.values = {}

    async def validate(self, text_inputs):
        self.error_documentations = []
        self.error = False

        for text_input in text_inputs:
            self.values[text_input.custom_id] = text_input.value
            try:
                valid_data = await text_input.run_check()
                self.validated[text_input.custom_id] = valid_data
            except input_validator.ValidationError as e:
                self.error = True
                error_documentation = e.get_error_doc()
                if error_documentation not in self.error_documentations and error_documentation is not None:
                    self.error_documentations.append(error_documentation)


class BrandTextInput(miru.TextInput):
    def __init__(self, check=None, check_args=None, prev_values=None, **kwargs):
        if prev_values:
            prev_value = prev_values.get(kwargs.get("custom_id"))
        else:
            prev_value = None

        kwargs["required"] = kwargs.get("required", True)

        super().__init__(
            value=prev_value,
            **kwargs
        )

        self.check = check
        self.check_args = check_args

    async def run_check(self):
        if self.check and self.check_args:
            if isinstance(self.check_args, tuple):
                return await self.check(self.value, *self.check_args)
            else:
                return await self.check(self.value, self.check_args)
        elif self.check:
            return await self.check(self.value)
        else:
            return self.value


class Apple(Brand):

    def __init__(self):
        super(Apple, self).__init__()
        self.user_input = UserInput()
        self.title = "Apple"

    async def get_step_one(self):
        modal = ReceiptModal(self) \
            .add_item(
            BrandTextInput(
                label="Image Link",
                custom_id="image",
                prev_values=self.user_input.values,
                check=input_validator.UserDataValidator.image,
            )
        ).add_item(
            BrandTextInput(
                label="Product Name",
                custom_id="product_name",
                prev_values=self.user_input.values,
            )
        ).add_item(
            BrandTextInput(
                label="Price",
                custom_id="price",
                prev_values=self.user_input.values,
                check=input_validator.UserDataValidator.common_value,
            )
        ).add_item(
            BrandTextInput(
                label="Currency",
                custom_id="currency",
                prev_values=self.user_input.values,
                check=input_validator.UserDataValidator.currency,
                check_args=["€", "$", "£"]
            )
        ).add_item(
            BrandTextInput(
                label="Shipping Cost",
                custom_id="shipping",
                prev_values=self.user_input.values,
                check=input_validator.UserDataValidator.common_value,
            )
        )

        return modal

    async def get_step_two(self):
        modal = ReceiptModal(self) \
            .add_item(
            BrandTextInput(
                label="Your name",
                custom_id="name",
                prev_values=self.user_input.values,
                check=input_validator.UserDataValidator.name,
                check_args=20
            )
        ).add_item(
            BrandTextInput(
                label="Date of purchase (M/D/YYYY)",
                custom_id="date",
                prev_values=self.user_input.values,
                check=input_validator.UserDataValidator.date,
            )
        ).add_item(
            BrandTextInput(
                label="Billing Address",
                custom_id="billing_addr",
                prev_values=self.user_input.values,
                style=hikari.TextInputStyle.PARAGRAPH,
                placeholder=self.address_placeholder1,
                check=input_validator.UserDataValidator.address,
                check_args=4
            )
        ).add_item(
            BrandTextInput(
                label="Shipping Address",
                custom_id="shipping_addr",
                prev_values=self.user_input.values,
                style=hikari.TextInputStyle.PARAGRAPH,
                placeholder=self.address_placeholder1,
                check=input_validator.UserDataValidator.address,
                check_args=4
            )
        )

        return modal

    async def scrape_web(self) -> dict:
        await asyncio.sleep(1)
        product = {
            "product_name": self.user_input.validated["product_name"],
            "image": self.user_input.validated["image"],
        }

        return product

    async def generate_email(self, product, email):
        template = self.get_template("apple", self.spoof)
        user_input = self.user_input.validated

        total = user_input["shipping"] + user_input["price"]
        total = f"{total:.2f}"
        shipping = f"{user_input['shipping']:.2f}"

        order_number = f"W{randint(1231486486, 9813484886)}"

        replacement_values = {
            "ADDRESS1": user_input["name"],
            "ADDRESS2": user_input["shipping_addr"].split("\n")[0],
            "ADDRESS3": user_input["shipping_addr"].split("\n")[1],
            "ADDRESS4": user_input["shipping_addr"].split("\n")[2],
            "ADDRESS5": user_input["shipping_addr"].split("\n")[3],

            "BILLING1": user_input["name"],
            "BILLING2": user_input["billing_addr"].split("\n")[0],
            "BILLING3": user_input["billing_addr"].split("\n")[1],
            "BILLING4": user_input["billing_addr"].split("\n")[2],
            "BILLING5": user_input["billing_addr"].split("\n")[3],

            "PRODUCT_IMAGE": product["image"],
            "PRODUCT_NAME": product["product_name"],
            "SHIPPING": f"{user_input['currency']}{shipping}",
            "PRODUCT_PRICE": f"{user_input['currency']}{user_input['price']:.2f}",
            "TOTAL": f"{user_input['currency']}{total}",
            "ORDERNUMBER": order_number,
            "EMAIL": email,
            "SPOOF_DATE": datetime.strptime(user_input["date"], "%m/%d/%Y").strftime("%d %B %Y"),
            "DATE": user_input["date"],
        }

        for key, value in replacement_values.items():
            template = template.replace(key, value)

        await self.send_email(
            to_email=email,
            html_content=template,
            sender_name="Applе Storе",
            subject=f"We're processing your order {order_number}",
            spoofed_email="noreply@apple.com"
        )

# Additional brand classes should be added following this structure, ensuring all database logic is removed.
