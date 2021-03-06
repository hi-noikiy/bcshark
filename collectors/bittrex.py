import json
import requests
import re

from zlib import decompress, MAX_WBITS
from base64 import b64decode
from requests import Session
from signalr import Connection
from model.market_tick import  market_tick
from .collector import collector
from .utility import *

class collector_bittrex(collector):
    @property
    def market_name(this):
        return "bittrex"

    def __init__(this, settings, market_settings):
        super(collector_bittrex, this).__init__(settings, market_settings)

    def translate_tick(this, ts, obj):
        ret = dict(obj)

        ret['time'] = ts
        ret['timezone_offset'] = this.timezone_offset

        return ret

    def on_open(this, websocket_client):
        this.logger.info('bittrex websocket connection established')

    def on_message(this, raw_message):
        try:
            raw_message = decompress(b64decode(raw_message), -MAX_WBITS)
        except SyntaxError:
            raw_message = decompress(b64decode(raw_message))

        #this.logger.info('receive message from bittrex websocket: %s', raw_message)
        this.logger.info('receive message from bittrex websocket: (hide)')
        message_json = json.loads(raw_message)

        for tick in message_json['D']:
            if tick['M'] in this.symbols_market:
                symbol_name = tick['M']
                this.save_trade(this.get_generic_symbol_name(symbol_name), this.translate_tick(time.time(), tick))

    def collect_ws(this):
        with Session() as session:
            connection = Connection(this.WS_URL, session = session)
            hub = connection.register_hub('c2')
            connection.start()

            hub.client.on('uS', this.on_message)
            hub.server.invoke('SubscribeToSummaryDeltas')

            connection.wait()

    def collect_rest(this):
        pass
