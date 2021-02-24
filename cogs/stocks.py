import aiohttp
import discord
import json
from discord.ext import commands
import re
import pytz
from datetime import datetime
import Utils


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


_YAHOO_URL = 'https://query1.finance.yahoo.com/v10/finance/quoteSummary/'

pattern_quote = re.compile(r'[$]([A-Za-z]+)[+]?')


class Stocks(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Stocks cog ready')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != self.client.user.id:
            matches = re.findall(pattern_quote, message.content)

            for ticker in set(matches):
                try:
                    response = await get_stock_price_async(ticker)
                    quote_embed = get_yahoo_quote(ticker, response)
                    await message.channel.send(embed=quote_embed)
                except AssertionError:
                    await message.channel.send(f'Unknown symbol: **${ticker.upper()}**')


def setup(client):
    client.add_cog(Stocks(client))


def get_yahoo_quote(ticker: str, response) -> discord.Embed:
    quote_json = response
    quote_result = quote_json.get('quoteSummary', {}).get('result', []).pop().get('price', {})

    symbol = quote_result.get('symbol', ticker.upper())
    company_name = quote_result.get('shortName', ticker.upper())
    latest_price = quote_result.get('regularMarketPrice', {}).get('raw', 0.00)
    high = quote_result.get('regularMarketDayHigh', {}).get('raw', 0.00)
    low = quote_result.get('regularMarketDayLow', {}).get('raw', 0.00)
    prev = quote_result.get('regularMarketPreviousClose', {}).get('raw', 0.00)
    change = quote_result.get('regularMarketChange', {}).get('fmt', 0.00)
    change_percent = quote_result.get('regularMarketChangePercent', {}).get('fmt', 0.00)
    quote_time = quote_result.get('regularMarketTime', {})
    q_time = datetime.fromtimestamp(quote_time, tz=pytz.timezone('America/New_York')).strftime('%H:%M:%S %Y-%m-%d')

    if float(change_percent.strip('%')) >= 0:
        market_percent_string = " (+" + change_percent + ")"
    else:
        market_percent_string = " (" + change_percent + ")"

    color = 0x85bb65  # Dollar Bill Green
    if float(change.strip('%')) >= 0:
        change_string = "+" + change
    else:
        change_string = change
        color = 0xFF0000  # Red

    if Utils.is_market_closed():
        after_market = closed_market(quote_result)
    else:
        after_market = ''

    return stock_embed(change_string, color, company_name, high, latest_price, low, market_percent_string, prev, q_time, symbol,
                       after_market)


def stock_embed(change_string, color, company_name, high, latest_price, low, market_percent_string, prev, q_time, symbol,
                after_market):
    desc1 = ''.join([str('${:,.2f}'.format(float(latest_price))), " ", change_string, market_percent_string])
    if high is not None and low is not None:
        desc2 = ''.join(['High: ', '{:,.2f}'.format(float(high)), ' Low: ', '{:,.2f}'.format(float(low)), ' Prev: ',
                         '{:,.2f}'.format(float(prev))])
    else:
        desc2 = ''.join(['Prev: ', '{:,.2f}'.format(float(prev))])
    embed = discord.Embed(
        title="".join([company_name, " ($", symbol, ")"]),
        url="https://finance.yahoo.com/quote/" + symbol,
        description=''.join([desc1, '\n', desc2, '\n', after_market]),
        color=color
    )
    embed.set_footer(text=f'{q_time}')
    return embed


def closed_market(quote_result):
    postMarketPrice = quote_result.get('postMarketPrice', {}).get('raw', 0.00)
    postMarketChange = quote_result.get('postMarketChange', {}).get('fmt', 0.00)
    postMarketChangePercent = quote_result.get('postMarketChangePercent', {}).get('fmt', 0.00)
    postMarketTime = quote_result.get('postMarketTime', {})
    post_time = datetime.fromtimestamp(postMarketTime, tz=pytz.timezone('America/New_York')).strftime('%H:%M:%S %Y-%m-%d')

    preMarketPrice = quote_result.get('preMarketPrice', {}).get('raw', 0.00)
    preMarketChange = quote_result.get('preMarketChange', {}).get('fmt', 0.00)
    preMarketChangePercent = quote_result.get('preMarketChangePercent', {}).get('fmt', 0.00)
    preMarketTime = quote_result.get('preMarketTime', {})
    pre_time = datetime.fromtimestamp(preMarketTime, tz=pytz.timezone('America/New_York')).strftime('%H:%M:%S %Y-%m-%d')

    if float(postMarketChange) > 0:
        post_change_string = f'+{postMarketChange}'
        post_percent_string = f'+{postMarketChangePercent}'
    else:
        post_change_string = postMarketChange
        post_percent_string = postMarketChangePercent

    post_market_desc = f'Post-market: ${postMarketPrice} {post_change_string} ({post_percent_string}) {post_time}'

    if float(preMarketChange) > 0:
        pre_change_string = f'+{preMarketChange}'
        pre_percent_string = f'+{preMarketChangePercent}'
    else:
        pre_change_string = preMarketChange
        pre_percent_string = preMarketChangePercent

    pre_market_desc = f'Pre-market: ${preMarketPrice} {pre_change_string} ({pre_percent_string}) {pre_time}'

    return f'{pre_market_desc}\n{post_market_desc}'


async def get_stock_price_async(ticker: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(_YAHOO_URL + f'{ticker}?modules=price') as response:
            assert 200 == response.status, response.reason
            return await response.json()
