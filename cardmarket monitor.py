import requests
from requests.utils import CaseInsensitiveDict
from bs4 import BeautifulSoup as BS
import json
from discord import SyncWebhook, Embed
import discord
from io import BytesIO
import random
from cardmarket_listing import cardmarket_item, cardmarket_listing
from constants import CARDMARKET_WEBHOOK, ROTATING_PROXY
import utils

def safeFetch(url) -> requests.Response:
    session = requests.session()
    headers = CaseInsensitiveDict()
    proxies = ROTATING_PROXY
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
        response = session.get(url="https://docs.google.com/gview?url=" + str(url), headers=headers, proxies=proxies, timeout=20)
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
        response = session.get(url="https://docs.google.com/viewerng/text?id=" + str(safeFetchId) + "&authuser=0&page=0", timeout=20, proxies=proxies, headers=headers)
        status = response.status_code

    try:
        response_text = json.loads(response.text.replace(")]}'\n{", "{"))['data']
    except json.decoder.JSONDecodeError:
        print(response.text)
        print(response.status_code)
    return response_text


for searchPage in range(1,100,1):

    # Get a list of items
    response_text = safeFetch("https://www.cardmarket.com/en/Pokemon/Products/Tins?site=" + str(searchPage))
    if 'Sorry, no matches for your query' in response_text or 'We had to limit your search results to' in response_text:
        break
    soup = BS(response_text, 'html.parser')
    items_html = soup.find("div", {"class":"table-body"}).find_all("div", recursive=False)


    for item_html in items_html:
        # Compare initial prices
        id = item_html['id'].replace("productRow", "")

        with utils.getMySQLConnection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT price FROM cardmarket_items WHERE id=%s', (id, ))
                result = cursor.fetchone()
        bestPrice = None
        if result:
            bestPrice = float(result['price'])
        print(id, bestPrice)

        lowestItemPrice = item_html.find('div', {'class': 'col-price'}).get_text().strip()
        if lowestItemPrice != 'N/A':
            lowestItemPrice = float(lowestItemPrice.replace("€", "").replace(".", "").replace(",", ".").strip())

        if lowestItemPrice == bestPrice:
            continue
        if lowestItemPrice == 'N/A' and bestPrice is None:
            continue
        
        # Make the request, parse listing table
        url = f'https://www.cardmarket.com{item_html.find_all("a")[-1]["href"]}?language=1'
        response_text = safeFetch(url)
        soup = BS(response_text, 'html.parser')

        item = cardmarket_item.from_html(html=soup)
        listings_html = soup.find("div", {"class":"table-body"}).find_all("div", recursive=False)

        for listing_html in listings_html:
            # Check if there are even any listings
            if listing_html.find('p', {'class': 'noResults'}) is not None:
                break

            listing = cardmarket_listing.from_html(html=listing_html, item=item)

            # Filter bad entries
            if listing.description:
                skip = False
                for negative_keyword in ['empty', 'opened', 'no packs', 'only the tin', 'only tin', 'no cards', 'just the tin', 'just the metal box', 'vuota']:
                    if negative_keyword in listing.description.lower():
                        skip = True
                        break

                if skip:
                    continue

            # Compare and update prices
            with utils.getMySQLConnection() as connection:
                with connection.cursor() as cursor:
                    if bestPrice and bestPrice <= listing.price:
                        cursor.execute('UPDATE cardmarket_items SET price=%s WHERE id=%s', (listing.price, listing.item.id))
                        break

                    if bestPrice is None:
                        cursor.execute('INSERT INTO cardmarket_items (id,price) VALUES (%s,%s)', (listing.item.id, listing.price))
                    else:
                        cursor.execute('UPDATE cardmarket_items SET price=%s WHERE id=%s', (listing.price, listing.item.id))

            # Send the webhook
            webhook = SyncWebhook.from_url(CARDMARKET_WEBHOOK)
            embed = Embed(title = listing.item.title, url = listing.item.url, description=listing.description)

            # Discord doesn't display image urls from cardmarket due to CORS settings. 
            # Hence, we download the image and upload it to discord manually.

            response_image = requests.get(listing.item.image_url, headers={'referer': 'cardmarket'})
            thumbnail = discord.File(fp=BytesIO(response_image.content), filename='thumbnail.png')
            embed.set_thumbnail(url='attachment://thumbnail.png')

            files: list[discord.File] = [thumbnail]
            if listing.image_id:
                response_image = requests.get(listing.image_url, headers={'referer': 'cardmarket'})
                image = discord.File(fp=BytesIO(response_image.content), filename='image.png')
                embed.set_image(url='attachment://image.png')
                files.append(image)

            if bestPrice:
                embed.add_field(name='Price', value=f'€{listing.price:.2f} <- €{bestPrice:.2f}', inline=True)
            else:
                embed.add_field(name='Price', value=f'€{listing.price:.2f}', inline=True)
            embed.add_field(name='Stock', value=listing.stock, inline=True)
            embed.add_field(name='Seller', value=f'{listing.get_pretty_location()} [{listing.username}]({listing.user_url})\n {listing.products_sold} Sales | {listing.available_items} Available items', inline=False)

            webhook.send(embed=embed, files=files)
            break