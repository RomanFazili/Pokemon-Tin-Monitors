from bs4 import BeautifulSoup as BS
import requests
from ebay_listing import ebay_listing
import utils
import time

headers = {
    'authority': 'www.ebay.nl',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'nl,en;q=0.9,en-GB;q=0.8,en-US;q=0.7',
    'dnt': '1',
    'referer': 'https://www.ebay.nl/',
    'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
    'sec-ch-ua-full-version': '"120.0.2210.91"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-model': '""',
    'sec-ch-ua-platform': '"Windows"',
    'sec-ch-ua-platform-version': '"15.0.0"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
}

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
            response = requests.session().get(url='https://www.ebay.nl/sch/i.html', headers=headers, params=params)

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

                # Ping for new item

            time.sleep(10)
    except BaseException as err:
        print(err)

ebay_monitor()