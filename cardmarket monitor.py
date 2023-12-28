import requests
from requests.utils import CaseInsensitiveDict
from bs4 import BeautifulSoup as BS
import json
from discord import SyncWebhook, Embed
import discord
from io import BytesIO
import random
from cardmarket_listing import cardmarket_item, cardmarket_listing
from constants import CARDMARKET_WEBHOOK

def safeFetch(url) -> requests.Response:
    session = requests.session()
    headers = CaseInsensitiveDict()
    headers["accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    headers["accept-encoding"] = "gzip, deflate, br"
    headers["accept-language"] = "nl"
    headers["dnt"] = "1"
    headers["preferanonymous"] = "1"
    headers["sec-ch-ua"] = '"Microsoft Edge";v="113", "Chromium";v="113", "Not-A.Brand";v="24"'
    headers["sec-ch-ua-arch"] = '"x86"'
    headers["sec-ch-ua-bitness"] = '"64"'
    headers["sec-ch-ua-full-version-list"] = '"Microsoft Edge";v="' + str(random.randint(90,115)) + '.0.1774.57", "Chromium";v="' + str(random.randint(90,115)) + '.0.5672.127", "Not-A.Brand";v="24.0.0.0"'
    headers["sec-ch-ua-mobile"] = "?0"
    headers["sec-ch-ua-model"] = '""'
    headers["sec-ch-ua-platform"] = '"Windows"'
    headers["sec-ch-ua-platform-version"] = '"15.0.0"'
    headers["sec-ch-ua-wow64"] = "?0"
    headers["sec-fetch-dest"] = "document"
    headers["sec-fetch-mode"] = "navigate"
    headers["sec-fetch-site"] = "none"
    headers["sec-fetch-user"] = "?1"
    headers["upgrade-insecure-requests"] = "1"
    headers["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/" + str(random.randint(90,115)) + ".0.0.0 Safari/537.36"

    safeFetchId = None
    attempts = 0
    while safeFetchId is None and attempts < 10:
        response = session.get(url="https://docs.google.com/gview?url=" + str(url), headers=headers, proxies=None, timeout=20)
        if response.status_code == 204:
            attempts = attempts + 1
            continue
        try:
            safeFetchId = response.text.split('text?id\\u003d')[1]
        except IndexError: # Code is 200 but can't find any safeFetchId
            attempts = attempts + 1
            continue
        safeFetchId = safeFetchId.split('\\u0026authuser')[0]
        safeFetchId = str(safeFetchId.split('"')[0])

    status = None
    while status in [None, 500]:
        response = session.get(url="https://docs.google.com/viewerng/text?id=" + str(safeFetchId) + "&authuser=0&page=0", timeout=20, proxies=None, headers=headers)
        status = response.status_code

    try:
        response_text = json.loads(response.text.replace(")]}'\n{", "{"))['data']
    except json.decoder.JSONDecodeError:
        print(response.text)
        print(response.status_code)
    return response_text

filtered = set()

for searchPage in range(1,100,1):

    response_text = safeFetch("https://www.cardmarket.com/en/Pokemon/Products/Tins?site=" + str(searchPage))

    if "Sorry, no matches for your query" in response_text:
        break

    soup = BS(response_text, 'html.parser')
    items = soup.find("div", {"class":"table-body"}).find_all("div", recursive=False)

    urls: list[str] = []
    for item in items:
        if item.get("id").replace("productRow", "") in filtered:
            continue
        localHrefs = [a.get("href") for a in item.find_all("a")]
        urls.append("https://www.cardmarket.com" + localHrefs[-1] + "?language=1")

    for url in urls:
        response_text = safeFetch(url)
        print(url)
        soup = BS(response_text, 'html.parser')

        item = cardmarket_item.from_html(html=soup)
        listings_html = soup.find("div", {"class":"table-body"}).find_all("div", recursive=False)

        for listing_html in listings_html:
            listing = cardmarket_listing.from_html(html=listing_html, item=item)

            if listing.description:
                skip = False
                for negative_keyword in ['empty', 'opened', 'no packs', 'only the tin', 'only tin', 'no cards', 'just the tin', 'just the metal box']:
                    if negative_keyword in listing.description:
                        skip = True
                        break

                if skip:
                    continue


            webhook = SyncWebhook.from_url(CARDMARKET_WEBHOOK)
            embed = Embed(title = listing.item.title, url = listing.item.url, description=listing.description)

            # Discord doesn't display image urls from cardmarket due to CORS settings. 
            # Hence, we download the image and upload it to discord manually.

            response_image = requests.get(listing.item.image_url, headers={'referer': 'cardmarket'})
            thumbnail = discord.File(fp=BytesIO(response_image.content), filename='thumbnail.png')
            embed.set_thumbnail(url='attachment://thumbnail.png')

            if listing.image_id:
                response_image = requests.get(listing.image_url, headers={'referer': 'cardmarket'})
                image = discord.File(fp=BytesIO(response_image.content), filename='image.png')
                embed.set_image(url='attachment://image.png')

            embed.add_field(name='Price', value=f'€{listing.price:.2f}', inline=True)
            embed.add_field(name='Stock', value=listing.stock, inline=True)
            embed.add_field(name='Seller', value=f'{listing.get_pretty_location()} [{listing.username}]({listing.user_url})\n {listing.products_sold} Sales | {listing.available_items} Available items', inline=False)

            webhook.send(embed=embed, files=[thumbnail, image])
            break