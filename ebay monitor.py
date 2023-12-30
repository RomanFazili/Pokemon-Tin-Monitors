from bs4 import BeautifulSoup as BS
import requests
from ebay_listing import ebay_listing
import utils
import time
from discord import SyncWebhook, Embed
from constants import EBAY_WEBHOOK, NEGATIVE_KEYWORDS

params = {
    '_nkw': 'pokemon tin', # Query
    '_sop': 10, # Sorted by: {10: 'Newly Advertised', 1: 'First expired'}
    '_ipg': 240, # Hits per page
}

def ebay_monitor() -> None:

    try:
        # Fetch all previously found listings
        foundIds: set[str] = set()
        with utils.getMySQLConnection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT id FROM ebay_listings')
                results = cursor.fetchall()
        for result in results:
            foundIds.add(result['id'])

        while True:
            response = requests.session().get(url='https://www.ebay.nl/sch/i.html', params=params)

            soup = BS(response.content, 'html.parser')
            listings_html = soup.find(name='ul', attrs={'class':'srp-results'}).find_all(name='li', attrs={'class': 's-item'}, recursive=False)

            for listing_html in listings_html:
                listing: ebay_listing = ebay_listing.from_html(listing_html)

                if listing.id in foundIds:
                    continue
                foundIds.add(listing.id)

                with utils.getMySQLConnection() as connection:
                    with connection.cursor() as cursor:
                        listing.save(cursor=cursor)

                print(listing)
                print(listing.offers)
                print(listing.is_auction)
                skip = False
                for negative_keyword in NEGATIVE_KEYWORDS:
                    if negative_keyword in listing.title.lower():
                        skip = True
                        break
                if skip:
                    continue

                # Send the webhook
                webhook = SyncWebhook.from_url(EBAY_WEBHOOK)
                embed = Embed(title=listing.title, url=listing.url)
                embed.set_thumbnail(url=listing.get_image_url(1000))

                if listing.is_auction:
                    embed.add_field(name='Current Price', value=f'€{listing.current_price:.2f} + €{listing.get_extras_price():.2f}', inline=True)
                    if listing.buy_now_price:
                        embed.add_field(name='Buy Now Price', value=f'€{listing.buy_now_price:.2f}', inline=True)
                    embed.add_field(name='Offers', value=str(listing.offers), inline=True)
                    embed.add_field(name='Expiry date', value=f'<t:{int(listing.expiry_date.timestamp())}:f> <t:{int(listing.expiry_date.timestamp())}:R>', inline=True)
                else:
                    embed.add_field(name='Price', value=f'€{listing.get_price():.2f} | €{listing.get_price(True):.2f} shipped.', inline=True)

                if listing.date:
                    embed.add_field(name='Date', value=f'<t:{int(listing.date.timestamp())}:f> <t:{int(listing.date.timestamp())}:R>', inline=True)
                embed.add_field(name='Seller', value=f'{listing.get_pretty_location()} [{listing.username}]({listing.user_url})\n {listing.products_sold} Sales | {(100 * listing.percentage_positive):.0f}% Positive Ratings', inline=False)

                webhook.send(embed=embed)
                time.sleep(1)

            time.sleep(10)
    except BaseException as err:
        raise err

ebay_monitor()