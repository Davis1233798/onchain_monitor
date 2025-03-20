import asyncio
import websockets
import requests
import json
from telegram import Bot

# 配置
MORALIS_API_KEY = "YOUR_MORALIS_API_KEY"
BITQUERY_API_KEY = "YOUR_BITQUERY_API_KEY"
ETHERSCAN_API_KEY = "YOUR_ETHERSCAN_API_KEY"
TELEGRAM_TOKEN = "YOUR_TELEGRAM_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"
bot = Bot(TELEGRAM_TOKEN)
THRESHOLD_USD = 100000
PRICE_CACHE = {}

# 更新價格（CoinGecko）
async def update_prices():
    while True:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
        response = requests.get(url)
        if response.status_code == 200:
            PRICE_CACHE["ETH"] = response.json()["ethereum"]["usd"]
        await asyncio.sleep(60)

# 測試函數：檢查 API 並發送測試訊息
async def test_api():
    # 測試 Moralis
    try:
        headers = {"x-api-key": MORALIS_API_KEY}
        response = requests.get("https://deep-index.moralis.io/api/v2/block/latest/transactions?chain=eth", headers=headers)
        if response.status_code == 200:
            await bot.send_message(chat_id=CHAT_ID, text="✅ Moralis API 測試成功")
        else:
            await bot.send_message(chat_id=CHAT_ID, text=f"❌ Moralis API 測試失敗：{response.status_code}")
    except Exception as e:
        await bot.send_message(chat_id=CHAT_ID, text=f"❌ Moralis API 測試錯誤：{e}")

    # 測試 Bitquery
    try:
        url = "https://graphql.bitquery.io/"
        query = "{ EVM(network: eth) { Blocks(limit: {count: 1}) { Hash } } }"
        response = requests.post(url, json={"query": query}, headers={"X-API-KEY": BITQUERY_API_KEY})
        if response.status_code == 200:
            await bot.send_message(chat_id=CHAT_ID, text="✅ Bitquery API 測試成功")
        else:
            await bot.send_message(chat_id=CHAT_ID, text=f"❌ Bitquery API 測試失敗：{response.status_code}")
    except Exception as e:
        await bot.send_message(chat_id=CHAT_ID, text=f"❌ Bitquery API 測試錯誤：{e}")

    # 測試 PublicNode
    try:
        async with websockets.connect("wss://ethereum.publicnode.com") as ws:
            await ws.send(json.dumps({"id": 1, "jsonrpc": "2.0", "method": "eth_blockNumber", "params": []}))
            response = await ws.recv()
            if json.loads(response).get("result"):
                await bot.send_message(chat_id=CHAT_ID, text="✅ PublicNode API 測試成功")
            else:
                await bot.send_message(chat_id=CHAT_ID, text="❌ PublicNode API 測試失敗")
    except Exception as e:
        await bot.send_message(chat_id=CHAT_ID, text=f"❌ PublicNode API 測試錯誤：{e}")

    # 測試 Binance API
    try:
        response = requests.get("https://api.binance.com/api/v3/trades?symbol=BTCUSDT&limit=1")
        if response.status_code == 200:
            await bot.send_message(chat_id=CHAT_ID, text="✅ Binance API 測試成功")
        else:
            await bot.send_message(chat_id=CHAT_ID, text=f"❌ Binance API 測試失敗：{response.status_code}")
    except Exception as e:
        await bot.send_message(chat_id=CHAT_ID, text=f"❌ Binance API 測試錯誤：{e}")

    # 測試 Etherscan
    try:
        url = f"https://api.etherscan.io/api?module=proxy&action=eth_blockNumber&apikey={ETHERSCAN_API_KEY}"
        response = requests.get(url)
        if response.status_code == 200 and response.json()["result"]:
            await bot.send_message(chat_id=CHAT_ID, text="✅ Etherscan API 測試成功")
        else:
            await bot.send_message(chat_id=CHAT_ID, text=f"❌ Etherscan API 測試失敗：{response.status_code}")
    except Exception as e:
        await bot.send_message(chat_id=CHAT_ID, text=f"❌ Etherscan API 測試錯誤：{e}")

# DEX 監控 - Moralis
async def monitor_dex_moralis():
    headers = {"x-api-key": MORALIS_API_KEY}
    url = "https://deep-index.moralis.io/api/v2/block/latest/transactions?chain=eth"
    while True:
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                for tx in response.json()["result"]:
                    value_eth = int(tx["value"]) / 10**18
                    usd_value = value_eth * PRICE_CACHE.get("ETH", 0)
                    if usd_value > THRESHOLD_USD:
                        await bot.send_message(
                            chat_id=CHAT_ID,
                            text=f"🚨 DEX 大額交易 (Moralis)：{value_eth} ETH (${usd_value})\n哈希：{tx['hash']}"
                        )
        except Exception as e:
            print(f"Moralis 錯誤：{e}")
        await asyncio.sleep(5)

# DEX 監控 - Bitquery
async def monitor_dex_bitquery():
    url = "https://graphql.bitquery.io/"
    query = """
    subscription {
      EVM(network: eth) {
        DEXTrades(
          where: {Trade: {Buy: {AmountInUSD: {gt: 100000}}}}
          limit: {count: 10}
        ) {
          Transaction { Hash }
          Trade { Buy { Amount AmountInUSD Currency { Symbol } } }
        }
      }
    }
    """
    headers = {"X-API-KEY": BITQUERY_API_KEY}
    while True:
        try:
            response = requests.post(url, json={"query": query}, headers=headers)
            if response.status_code == 200:
                trades = response.json()["data"]["EVM"]["DEXTrades"]
                for trade in trades:
                    amount_usd = float(trade["Trade"]["Buy"]["AmountInUSD"])
                    tx_hash = trade["Transaction"]["Hash"]
                    await bot.send_message(
                        chat_id=CHAT_ID,
                        text=f"🚨 DEX 大額交易 (Bitquery)：${amount_usd}\n哈希：{tx_hash}"
                    )
        except Exception as e:
            print(f"Bitquery 錯誤：{e}")
        await asyncio.sleep(60)

# DEX 監控 - PublicNode
async def monitor_dex_publicnode():
    ws_url = "wss://ethereum.publicnode.com"
    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                await ws.send(json.dumps({
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": "eth_subscribe",
                    "params": ["newHeads"]
                }))
                await ws.recv()
                while True:
                    message = await ws.recv()
                    block_data = json.loads(message)
                    block_number = block_data["params"]["result"]["number"]
                    block_url = "https://ethereum.publicnode.com"
                    block_payload = {
                        "id": 1,
                        "jsonrpc": "2.0",
                        "method": "eth_getBlockByNumber",
                        "params": [block_number, True]
                    }
                    response = requests.post(block_url, json=block_payload)
                    if response.status_code == 200:
                        block = response.json()["result"]
                        for tx in block["transactions"]:
                            value_wei = int(tx["value"], 16)
                            value_eth = value_wei / 10**18
                            usd_value = value_eth * PRICE_CACHE.get("ETH", 0)
                            if usd_value > THRESHOLD_USD:
                                await bot.send_message(
                                    chat_id=CHAT_ID,
                                    text=f"🚨 DEX/鏈上大額轉帳 (PublicNode)：{value_eth} ETH (${usd_value})\n哈希：{tx['hash']}"
                                )
        except Exception as e:
            print(f"PublicNode 錯誤：{e}")
            await asyncio.sleep(5)

# CEX 監控 - Binance API
async def monitor_cex_binance():
    url = "https://api.binance.com/api/v3/trades?symbol=BTCUSDT&limit=100"
    while True:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                for trade in response.json():
                    qty = float(trade["qty"])
                    price = float(trade["price"])
                    usd_value = qty * price
                    if usd_value > THRESHOLD_USD:
                        await bot.send_message(
                            chat_id=CHAT_ID,
                            text=f"🚨 CEX 大額交易 (Binance)：{qty} BTC (${usd_value})\nID：{trade['id']}"
                        )
        except Exception as e:
            print(f"Binance 錯誤：{e}")
        await asyncio.sleep(10)

# CEX 監控 - Etherscan
async def monitor_cex_etherscan():
    address = "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be"  # Binance 熱錢包
    url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&sort=desc&apikey={ETHERSCAN_API_KEY}"
    while True:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                for tx in response.json()["result"][:10]:
                    value_wei = int(tx["value"])
                    value_eth = value_wei / 10**18
                    usd_value = value_eth * PRICE_CACHE.get("ETH", 0)
                    if usd_value > THRESHOLD_USD:
                        await bot.send_message(
                            chat_id=CHAT_ID,
                            text=f"🚨 CEX 鏈上活動 (Etherscan)：{value_eth} ETH (${usd_value})\n哈希：{tx['hash']}"
                        )
        except Exception as e:
            print(f"Etherscan 錯誤：{e}")
        await asyncio.sleep(60)

# 主函數：先測試再監控
async def main():
    await bot.send_message(chat_id=CHAT_ID, text="🚀 程式啟動，正在測試所有 API...")
    await test_api()  # 執行測試
    await bot.send_message(chat_id=CHAT_ID, text="✅ 測試完成，開始正常監控")
    await asyncio.gather(
        update_prices(),
        monitor_dex_moralis(),
        monitor_dex_bitquery(),
        monitor_dex_publicnode(),
        monitor_cex_binance(),
        monitor_cex_etherscan()
    )

if __name__ == "__main__":
    asyncio.run(main())
