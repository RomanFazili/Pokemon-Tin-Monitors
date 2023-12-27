from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Self
from bs4 import BeautifulSoup as BS
import re
import pytz
import pymysql.cursors

@dataclass
class ebay_listing:
    id: str
    title: str
    image_id: str
    date: datetime
    current_price: float
    delivery_cost: float
    origin_country: str

    is_new: Optional[bool] # Only None when 'PROBSTEIN is actively accepting consignment' is in the way
    taxes: Optional[float] # Only when taxes apply

    # Only in the case of an auction:
    buy_now_price: Optional[float]
    offers: Optional[int]
    expiry_date: Optional[datetime]

    @classmethod
    def from_html(cls, html: BS) -> Self:
        def clean_price(text: str) -> float:
            text = text.replace('EUR', '').replace('.', '').replace(',', '.').replace('+', '').strip()
            return float(text)
        
        item_id_pattern = r'/(\d+)\?'
        id = re.search(item_id_pattern, html.find(name='a').get('href'))
        if id is None:
            raise ValueError('Could not find a valid ID.')
        
        is_new = html.find(name='span', attrs={'class': 'SECONDARY_INFO'})
        if is_new is not None:
            is_new = 'gloednieuw' in is_new.get_text().lower()

        image_id_pattern = '/g/(.*?)/s-'
        image_id = re.search(image_id_pattern, html.find('img').get('src'))
        if image_id is None:
            raise ValueError('Could not find a valid image ID.')
            
        date_time_format = r'%b-%d %H:%M'
        date = html.find(name='span', attrs={'class': 's-item__listingDate'})
        if date is not None:
            date = datetime.strptime(date.get_text(), date_time_format)
            date = date.replace(year=datetime.utcnow().year)

        prices = html.find_all(name='span', attrs={'class': 's-item__price'})
        current_price = clean_price(prices[0].get_text())
        buy_now_price = clean_price(prices[-1].get_text())
        if buy_now_price == current_price:
            buy_now_price = None

        taxes = html.find(name='span', attrs={'class': 's-item__gstMessage'})
        if taxes is not None:
            taxes = clean_price(taxes.get_text().replace('btw van toepassing', ''))
        delivery_cost = clean_price(html.find(name='span', attrs={'class': 's-item__logisticsCost'}).get_text().replace('geschatte', '').replace('verzendkosten', '').strip())

        offers = html.find(name='span', attrs={'class': 's-item__bidCount'})
        if offers is not None:
            offers = int(offers.get_text().replace('bod', '').replace(' biedingen', '').replace('·', '').strip())

        expiry_date = html.find(name='span', attrs={'class': 's-item__time-end'})
        if expiry_date is not None:
            date_time_format = r'%H:%M'
            current_time_utc_minus_seven = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pytz.timezone('America/Denver'))
        
            weekday = int(expiry_date.get_text().replace('(', '').split(' ')[0].replace('Vandaag', str(current_time_utc_minus_seven.weekday())).replace('ma', '0').replace('di', '1').replace('wo', '2').replace('do', '3').replace('vr', '4').replace('za', '5').replace('zo', '6').replace(',', '').strip())
            expiry_time = datetime.strptime(expiry_date.get_text().replace(')', '').split(' ')[-1], date_time_format).replace(tzinfo=pytz.timezone('America/Denver'))

            days_until_expiry = (weekday - current_time_utc_minus_seven.weekday() + 7) % 7
            next_occurrence = current_time_utc_minus_seven + timedelta(days=days_until_expiry)

            expiry_date = datetime.combine(next_occurrence, expiry_time.time())

        return cls(
            id = id.group(1),
            title = html.find(name='span', attrs={'role': 'heading'}).get_text().replace('Nieuwe aanbieding', ''),
            is_new = is_new,
            image_id = image_id.group(1),
            date = date,
            current_price = current_price,
            buy_now_price = buy_now_price,
            taxes = taxes,
            delivery_cost = delivery_cost,
            origin_country = html.find(name='span', attrs={'class': 's-item__itemLocation'}).get_text().replace('van', '').strip(),
            offers = offers,
            expiry_date = expiry_date,
        )
    
    @property
    def url(self) -> str:
        return f'https://www.ebay.nl/itm/{self.id}'

    def get_image_url(self, resolution: int = 300) -> str:
        if resolution > 1200 or resolution < 50:
            ValueError(f'Resolution must be between 50 - 1200, not {resolution}.')
        return f'https://i.ebayimg.com/thumbs/images/g/{self.image_id}/s-l{resolution}.jpg'
    
    def save(self, cursor: pymysql.cursors.DictCursor) -> None:
        cursor.execute('INSERT INTO ebay_listings (id) VALUES (%s);', (self.id, ))