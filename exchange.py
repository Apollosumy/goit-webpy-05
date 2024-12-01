import asyncio
import datetime
import json
from aiofile import AIOFile, Writer
from aiopath import AsyncPath
import websockets
import aiohttp


class ExchangeRateFetcher:
    """Класс для получения курсов валют от ПриватБанка."""
    BASE_URL = "https://api.privatbank.ua/p24api/exchange_rates"

    async def fetch_rates(self, date: datetime.date, currencies: list[str]) -> dict:
        """Получает курсы валют на указанную дату."""
        formatted_date = date.strftime("%d.%m.%Y")
        url = f"{self.BASE_URL}?date={formatted_date}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return {"error": f"HTTP Error {response.status}"}

                data = await response.json()
                rates = {rate["currency"]: {"sale": rate.get("saleRate"), "purchase": rate.get("purchaseRate")}
                         for rate in data.get("exchangeRate", [])
                         if rate.get("currency") in currencies}
                return {formatted_date: rates}


class Logger:
    """Класс для логирования команд."""
    def __init__(self, log_file: AsyncPath):
        self.log_file = log_file

    async def log(self, message: str):
        """Логирует сообщение в файл."""
        async with AIOFile(self.log_file, "a") as afp:
            writer = Writer(afp)
            await writer(f"{datetime.datetime.now()} - {message}\n")


class WebSocketServer:
    """WebSocket-сервер для обработки команд."""
    def __init__(self, log_file: str):
        self.logger = Logger(AsyncPath(log_file))
        self.fetcher = ExchangeRateFetcher()

    async def handle_client(self, websocket):
        """Обрабатывает сообщения от клиента."""
        async for message in websocket:
            if message.startswith("exchange"):
                await self.handle_exchange(message, websocket)

    async def handle_exchange(self, message: str, websocket):
        """Обрабатывает команду exchange."""
        parts = message.split()
        days = int(parts[1]) if len(parts) > 1 else 1
        currencies = ["USD", "EUR"]  # Валюты по умолчанию

        if days < 1 or days > 10:
            response = "Ошибка: количество дней должно быть от 1 до 10."
            await websocket.send(response)
            await self.logger.log(response)
            return

        today = datetime.date.today()
        tasks = [self.fetcher.fetch_rates(today - datetime.timedelta(days=i), currencies)
                 for i in range(days)]
        results = await asyncio.gather(*tasks)

        response = json.dumps(results, ensure_ascii=False, indent=2)
        await websocket.send(response)
        await self.logger.log(f"exchange {days}: {response}")


async def main():
    """Запускает WebSocket-сервер."""
    server = WebSocketServer(log_file="chat_log.txt")
    async with websockets.serve(server.handle_client, "localhost", 8080):
        print("WebSocket сервер запущен на ws://localhost:8080")
        await asyncio.Future()  # Блокирует выполнение


if __name__ == "__main__":
    asyncio.run(main())
