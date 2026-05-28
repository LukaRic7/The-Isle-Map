from datetime import datetime
from collections import deque
from bs4 import BeautifulSoup
#import loggerric as lr
import requests, time

class Client:
    """
    **Communicate with a web endpoint.**
    
    Passes cookies and user agent in the headers.
    
    *Methods*:
    - `fetch(path) -> BeautifulSoup`: Parsed HTML response from the endpoint.
    """

    def __init__(self, base_url:str, cookie:str, user_agent:str):
        """
        **Initializer.**
        
        *Parameters*:
        - `base_url` (str): Base URL of domain.
        - `cookie` (str): Cookie to pass in the headers.
        - `user_agent` (str): User agent to pass in the headers.
        """

        self.base_url = base_url
        self.headers  = { 'User-Agent': user_agent, 'Cookie': cookie }

        #lr.Log.info('Initialized fetching client!')

    def fetch(self, path:str='') -> BeautifulSoup:
        """
        **Fetch from the endpoint.**
        
        *Parameters*:
        - `path` (str): URL path after the base URL.
        
        *Returns*:
        - (BeautifulSoup): Parsed HTML response from the endpoint.
        """

        url = self.base_url + path

        # Fetch URL
        response = requests.get(url, headers=self.headers)
        status = response.status_code
        reason = response.reason

        # URL did not return OK
        if not response.ok:
            #lr.Log.error('"{}" Failed! [{}]: {}'.format(url, status, reason))
            return

        #lr.Log.debug('"{}" Succeeded! [{}]: {}'.format(url, status, reason))

        return BeautifulSoup(response.text, 'lxml')

class Observer:
    """
    **Observes webpage data, parses it and writes to an output file.**
    
    Repeatedly requests new data from the URL endpoint, then parses it
    calculating deltas and time estimations in the process, writing it all
    to an output JSON file.
    
    *Methods*:
    - `record(info) -> None`: Add information to the history.
    - `calculate_deltas() -> dict`: Calculate delta values from history.
    - `estimate_time_to_target(info, deltas) -> dict`: Calculate EST minutes
    until the target value is hit.
    - `extract_info(soup) -> dict`: Extract information from parsed HTML soup.
    - `mainloop() -> None`: Enter the mainloop, uses while true.
    """

    def __init__(self, je_cookie:str, user_agent:str):
        """
        **Initializer.**
        """

        self.cookie = je_cookie
        
        self.Client = Client(
            base_url='https://echoes.norden.cloud/',
            cookie=je_cookie,
            user_agent=user_agent
        )

        self.POST_UPDATE_DELAY = 3

        self.history = deque(maxlen=5)
    
    def record(self, info:dict):
        """
        **Add information to the history.**
        
        *Parameters*:
        - `info` (dict): Information to be added.
        """

        now = time.time() 

        self.history.append({ 'time': now, 'info': info })
    
    def get_sleep_time(self) -> int:
        """
        **Sleep until the predicted update time.**
        
        *Returns*:
        - (int): Time to sleep.
        """

        now = datetime.now()

        return 60 + self.POST_UPDATE_DELAY - now.second

    def calculate_deltas(self) -> dict:
        """
        **Calculate delta values from history.**
        
        *Returns*:
        - (dict): Calculated deltas.
        """

        # Ensure more than 2 datapoints
        if len(self.history) < 2: return None

        total_change = {k: 0 for k in self.history[-1]['info']}
        first_time = self.history[0]['time']
        last_time  = self.history[-1]['time']
        delta_minutes = (last_time - first_time) / 60

        if delta_minutes == 0:
            return {k: 0 for k in total_change}

        for key in total_change:
            start_value = self.history[0]['info'].get(key, 0)
            end_value   = self.history[-1]['info'].get(key, 0)
            total_change[key] = (end_value - start_value) / delta_minutes

        return total_change if len(total_change) > 0 else None

    def estimate_time_to_target(self, info:dict, deltas:dict) -> dict:
        """
        **Calculate EST minutes until the target value is hit.**
        
        *Parameters*:
        - `info` (dict): Freshly fetched information.
        - `deltas` (dict): Calculated deltas from history.
        
        *Returns*:
        - (dict): EST minutes until targets are reached.
        """

        # Define lookup table from keys to targets
        TARGETS = { 'Growth': 1.0, 'Health': 1.0, 'Hunger': 0.0, 'Thirst': 0.0 }

        # Iterate targets
        estimates = {}
        for key, target in TARGETS.items():
            # Ensure the key exists in deltas
            if key not in info or key not in deltas: continue

            delta   = deltas[key]
            current = info[key]

            # Ensure the delta is non-zero to avoid zero division error
            if delta == 0:
                estimates[key] = 0
            else:
                # Calculate estimated target and ensure positive number
                time_to_target = (target - current) / delta
                estimates[key] = max(0, time_to_target)
        
        # If no estimates, return None instead of empty dict
        return estimates if len(estimates) > 0 else None

    def extract_info(self, soup:BeautifulSoup) -> dict:
        """
        **Extract information from parsed HTML soup.**
        
        *Parameters*:
        - `soup` (BeautifulSoup): Parsed HTML to extract from.
        
        *Returns*:
        - (dict): Extracted information.
        """

        # Grab the div that holds the information
        ingame_info = soup.find(
            name='div',
            class_='grid grid-cols-1 md:grid-cols-2 gap-5'
        )

        # Iterate the div's children
        extracted_info = {}
        for row in ingame_info.children:
            # Extract the rows label and percent, both HTML
            label = row.find_next(
                name='div',
                class_='text-xs uppercase tracking-wide text-gray-300/80'
            )
            percent = row.find_next(
                name='div',
                class_='mt-1 text-base font-medium'
            )

            VALID = ['Growth', 'Health', 'Hunger', 'Thirst']

            # Only grab valid results
            if label and percent and label.text in VALID:
                # Extract the percentage and format it
                pct = float(percent.text[0:-1]) / 100
                extracted_info[label.text] = pct

        return extracted_info

    def extract_balance(self, soup:BeautifulSoup) -> int:
        """
        **Extract the balance from the parsed HTML soup.**
        
        *Parameters*:
        - `soup` (BeautifulSoup): Parsed HTML to extract from.
        
        *Returns*:
        - (int): The balance extracted.
        """

        balance = soup.find('div', class_='mt-1 text-base font-medium')

        if not balance:
            return 0

        return balance.text

    def extract_dinosaur(self, soup:BeautifulSoup) -> str:
        """
        **Extract the dinosaur species from the parsed HTML soup.**
        
        *Parameters*:
        - `soup` (BeautifulSoup): Parsed HTML to extract from.
        
        *Returns*:
        - (str): The dinosaur species extracted.
        """

        species = soup.find_all('div', class_='mt-1 text-2xl font-semibold')

        if not species:
            return 'No Dinosaur'
        
        return species[1].text

    def fetch(self):
        soup = self.Client.fetch('player')
        if not soup: return

        info = self.extract_info(soup)
        self.record(info)

        deltas    = self.calculate_deltas()
        estimates = self.estimate_time_to_target(info, deltas or {})

        return {
            'current': info,
            'delta-per-min': deltas or {},
            'est-time-min': estimates or {},
            'balance': self.extract_balance(soup),
            'dinosaur': self.extract_dinosaur(soup)
        }