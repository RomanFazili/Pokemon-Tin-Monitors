from dataclasses import dataclass
from bs4 import BeautifulSoup as BS
from typing import Self, Literal, Optional
from datetime import datetime
import pytz

@dataclass
class cardmarket_item:
    """Class that represents an item on the cardmarket.com platform"""
    
    id: str
    title: str
    url_key: str
    language: Literal['English']

    @classmethod
    def from_html(cls, html: BS) -> Self:
        title_html = html.find("div", attrs={'class': 'page-title-container'}).find("h1")
        title_html.find('span').extract()

        return cls(
            id = html.find('input', {"type":"hidden", "name":"idProduct"})['value'],
            title = title_html.get_text(),
            url_key = html.find('link')['href'],
            language = 'English'
        )
    
    @property
    def url(self) -> str:
        return f'https://www.cardmarket.com{self.url_key}'
    
    @property
    def image_url(self) -> str:
        return f'https://product-images.s3.cardmarket.com/1014/{self.id}/{self.id}.jpg'
    
@dataclass
class cardmarket_listing:
    """"Class that represents a cardmarket.com listing under a given item."""

    username: str
    products_sold: int
    available_items: int
    item: cardmarket_item
    location: str

    image_id: Optional[str]
    description: Optional[str]
    price: float
    stock: int

    @classmethod
    def from_html(cls, html: BS, item: cardmarket_item) -> Self:


        image_id = html.find("div", {"class":"product-attributes col"}).find('a')
        if image_id:
            image_id = image_id['href'].split('cardmarket.com/')[-1].split('/')[0]

        description = html.find("div", {"class":"product-comments"})
        if description:
            description = description.find("span").get_text()

        items_record = html.find('span', {'class': 'sell-count'})['title']

        return cls(
            username = html.find('span', {'class': 'seller-name'}).find('a').get_text(),
            products_sold = int(items_record.split('Sales')[0].strip()),
            available_items = int(items_record.split('|')[-1].replace('Available items', '').strip()),
            item = item,
            location = html.find('span', {'class': 'seller-name'}).find_all('span', recursive=False)[1]['title'].replace('Item location:', '').strip(),

            image_id = image_id,
            description = description,
            price = float(html.find("div", {"class":"col-offer"}).find('span').get_text().strip().replace("€", "").replace(".", "").replace(",", ".").strip()),
            stock = int(html.find("span", {"class":"item-count"}).get_text())
        )

    @property
    def user_url(self) -> str:
        return f'https://www.cardmarket.com/en/Pokemon/Users/{self.username}'
    
    @property
    def image_url(self) -> Optional[str]:
        # Required to load from the site first to load the following image url
        if self.image_id:
            return f'https://marketplace-article-scans.s3.cardmarket.com/{self.image_id}/{self.image_id}t.jpg?timestamp={datetime.now(tz=pytz.timezone("Europe/Amsterdam")).strftime(r"%Y-%m-%d %H:%M:%S").replace(" ", "%20")}'
    
    @property
    def iso(self) -> Optional[str]:
        if self.location == 'Sweden':
            return 'SE'
        elif self.location == 'Germany':
            return 'DE'
        elif self.location == 'Italy':
            return 'IT'
        elif self.location == 'Poland':
            return 'PL'
        elif self.location == 'Netherlands':
            return 'NL'
        elif self.location == 'Portugal':
            return 'PT'
        elif self.location == 'Czech Republic':
            return 'CZ'
        elif self.location == 'United Kingdom':
            return 'UK'
        elif self.location == 'Denmark':
            return 'DK'
        elif self.location == 'Greece':
            return 'GR'
        elif self.location == 'Spain':
            return 'ES'
        elif self.location == 'France':
            return 'FR'
        elif self.location == 'Belgium':
            return 'BE'
        elif self.location == 'Austria':
            return 'AT'
        
        print(self.location)
        return None
    
    def get_pretty_location(self) -> str:
        if self.iso:
            return f':flag_{self.iso.lower()}:'
        return self.location