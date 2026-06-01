from datetime import datetime as dt, timezone as tz
from dataclasses import dataclass, asdict, field
from collections import deque
from pathlib import Path
import sys

# Handle both normal execution and PyInstaller bundled exe
if getattr(sys, 'frozen', False):
    # Running as PyInstaller exe
    ROOT = Path(sys._MEIPASS).parent
else:
    # Running as script
    ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.je_fetching import Observer

@dataclass
class JEStat:
    percent:int=0
    delta_rate:float=0.0
    eta_to_bounds:int=0

@dataclass
class JurassicEchoes:
    cookie:str
    user_agent:str
    fetching_client:Observer
    invalid_cookie:bool=False
    website_down:bool=False
    health:JEStat=field(default_factory=JEStat)
    growth:JEStat=field(default_factory=JEStat)
    hunger:JEStat=field(default_factory=JEStat)
    thirst:JEStat=field(default_factory=JEStat)
    species:str=None
    balance:int=None

@dataclass
class Coord:
    utc_timestamp:int
    coordinates:tuple[float, float]

@dataclass
class Client:
    coordinates:deque[Coord]=field(default_factory=lambda: deque(maxlen=16))
    last_coordinate_utc_ts:int=0
    pin_position:tuple[float, float]=field(default_factory=tuple)
    alias:str='Unknown Client'
    color:str='#ff0000'
    je:JurassicEchoes=None
    last_heartbeat_utc_ts:int=field(
        default_factory=lambda: int(dt.now(tz=tz.utc).timestamp()))

def deserialize_client(client_data:dict) -> Client:
    """
    **Deserialize a serialized client object.**
    
    *Parameters*:
    - `client_data` (dict): The serialized client object.
    
    *Returns*:
    - (Client): The deserialized client object.
    """
    jurassic_echoes:JurassicEchoes = None
    je:dict = client_data.get('je')
    if je:
        jurassic_echoes = JurassicEchoes(
            cookie='HIDDEN', user_agent='HIDDEN', fetching_client='HIDDEN',
            invalid_cookie=je.get('invalid_cookie', False),
            website_down=je.get('website_down', False),
            health=JEStat(**je.get('health', {})),
            growth=JEStat(**je.get('growth', {})),
            hunger=JEStat(**je.get('hunger', {})),
            thirst=JEStat(**je.get('thirst', {})),
            species=je.get('species'), balance=je.get('balance')
        )

    return Client(
        alias=client_data.get('alias'), color=client_data.get('color'),
        last_coordinate_utc_ts=client_data.get('last_coordinate_utc_ts'),
        pin_position=client_data.get('pin_position'),
        je=jurassic_echoes,
    )

def serialize_client(client:Client) -> dict:
    """
    **Serialize dataclasses to make them safe for SIO travel.**

    Doesn't serialize sensitive information and coordinates.
    
    *Parameters*:
    - `client` (Client): The client dataclass instance to serialize.
    
    *Returns*:
    - (dict): The serialized client.
    """
    data = asdict(client)

    del data['coordinates']
    del data['last_heartbeat_utc_ts']

    if data.get('je'):
        del data['je']['cookie']
        del data['je']['user_agent']
        del data['je']['fetching_client']

    return data