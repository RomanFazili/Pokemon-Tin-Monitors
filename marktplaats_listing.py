from dataclasses import dataclass
from uuid import UUID
from typing import Self


@dataclass
class marktplaats_listing:
    id: str
    title: str
    description: str
    price: float
    image_id: UUID
    image_ext: int

    username: str
    user_id: str
    city: str
    iso: str


    condition: str
    delivery: str

    @classmethod
    def from_json(cls, json: dict) -> Self:
        price = json['priceInfo']['priceCents'] / 100
        if json['priceInfo']['priceType'] == 'FAST_BID':
            price = None

        condition = None
        delivery = None
        for attribute in json['attributes']:
            if attribute['key'] == 'condition':
                condition = attribute['value']
            if attribute['key'] == 'delivery':
                delivery = attribute['value']

        return cls(
            id = json['itemId'],
            title = json['title'],
            description = json['categorySpecificDescription'],
            price = price,
            image_id = UUID(json['pictures'][0]['extraExtraLargeUrl'].split('?')[0].split('/')[-1]),
            image_ext = int(json['pictures'][0]['extraExtraLargeUrl'].split('ecg_mp_eps$_')[-1].split('.')[0]),
            username = json['sellerInformation']['sellerName'],
            user_id = json['sellerInformation']['sellerId'], 
            city = json['location']['cityName'],
            iso = json['location']['countryAbbreviation'],
            
            condition = condition,
            delivery = delivery
        )
    
    @property
    def url(self) -> str:
        return f'https://www.marktplaats.nl/{self.id}'
    
    @property
    def user_url(self) -> str:
        return f'https://www.marktplaats.nl/u/u/{self.user_id}/'
    
    @property
    def image_url(self) -> str:
        return f'https://images.marktplaats.com/api/v1/listing-mp-p/images/{str(self.image_id)[0:2]}/{self.image_id}?rule=ecg_mp_eps$_{self.image_ext}.jpg'
    
    def getFlag(self) -> str:
        return f':flag_{self.iso.lower()}:'