import requests
import json

from websocket import WebSocketApp
from struct import pack_into, unpack_from

from model.market_tick import market_tick
from .utility import *

class collector(object):
    DEFAULT_TIMEOUT_IN_SECONDS = 10

    def __init__(this, settings, market_settings):
        this.settings = settings
        this.market_settings = market_settings
        this.logger = settings['logger']
        this.db_adapter = settings['db_adapter']
        this.cache_manager = settings['cache_manager']
        this.symbols = settings['symbols']
        this.symbols_default = this.symbols["default"]
        this.timezone_offset = settings['timezone_offset']
        this.websocket_client = None

    @property
    def REST_URL(this):
        if this.market_settings.has_key('api') and this.market_settings['api'].has_key('rest'):
            return this.market_settings['api']['rest']
        return None

    @property
    def WS_URL(this):
        if this.market_settings.has_key('api') and this.market_settings['api'].has_key('ws'):
            return this.market_settings['api']['ws']
        return None

    @property
    def symbols_market(this):
        return this.symbols[this.market_name]

    @property
    def symbols_all_market(this):
        return this.symbols

    @property
    def table_market_trades(this):
        return '%s_trades' % this.market_name

    @property
    def table_market_ticks(this):
        return '%s_ticks' % this.market_name

    @property
    def table_market_ticks_usd(this):
        return '%s_ticks_usd' % this.market_name

    def on_raw_close(this, websocket_client):
        print 'on close'

    def on_raw_open(this, websocket_client):
        if this.on_open:
            this.on_open(websocket_client)

    def on_raw_message(this, websocket_client, raw_message):
        if this.on_message:
            this.on_message(websocket_client, raw_message)

    def on_raw_error(this, websocket_client, error):
        print 'on error'
        print error

    def send_ws_message_json(this, json_obj):
        message = json.dumps(json_obj)
        this.send_ws_message(message)

    def send_ws_message(this, message):
        if this.websocket_client:
            this.websocket_client.send(message)

    def http_request_json(this, url, headers, cookies = None):
        this.logger.info('Requesting \033[0;32;40m%s\033[0m rest interface, url: \033[0;32;40m%s\033[0m' % (this.market_name, url))

        try:
            res = requests.get(url, headers = headers, cookies = cookies, timeout = this.DEFAULT_TIMEOUT_IN_SECONDS, allow_redirects = True)

            return res.json()
        except Exception, e:
            print e
            return None

    def start_listen_websocket(this, url, listener):
        if not this.websocket_client:
            this.stop_listen_websocket()

        this.logger.info('Connecting to \033[0;32;40m%s\033[0m websocket interface, url: \033[0;32;40m%s\033[0m' % (this.market_name, url))
        this.websocket_client = WebSocketApp(url, on_open = listener.on_raw_open, on_close = listener.on_raw_close, on_message = listener.on_raw_message, on_error = listener.on_raw_error)
        this.websocket_client.run_forever()

    def stop_listen_websocket(this):
        if this.websocket_client:
            this.websocket_client.close()

    def is_usd_price(this, symbol_name):
        return symbol_name == this.symbols_default[0] or symbol_name.endswith('usd') or symbol_name.endswith('usdt')

    def save_trade(this, symbol_name, trade):
        this.db_adapter.save_trade(this.table_market_trades, this.market_name, symbol_name, trade)

    def save_tick(this, symbol_name, tick):
        if symbol_name == this.symbols_default[0]:
            this.update_cache(symbol_name, tick)

        this.db_adapter.save_tick(this.table_market_ticks, this.market_name, symbol_name, tick)

        # calculate usd prices except btc-usd pair
        if not this.is_usd_price(symbol_name):
            tick = this.calculate_usd_prices(tick)

        if tick:
            this.db_adapter.save_tick(this.table_market_ticks_usd, this.market_name, symbol_name, tick)
            this.db_adapter.save_tick('market_ticks', this.market_name, symbol_name, tick)

    def bulk_save_ticks(this, symbol_name, ticks):
        sql = "select time, market, symbol, high, low, open, close from %s where market = '%s' and symbol = '%s' group by market, symbol order by time desc limit 1" % (this.table_market_ticks, this.market_name, symbol_name)
        ret = this.db_adapter.query(sql, epoch = 's')
        if ret and ret.has_key('series'):
            latest_timestamp = ret['series'][0]['values'][0][0]
            #print('-----before lambda filter: ', len(ticks), '  --- latest timestamp:', latest_timestamp)
            ticks = filter(lambda x: x.time + x.timezone_offset >= latest_timestamp, ticks)
            #print('-----after lambda filter: ', len(ticks))

        for tick in ticks:
            this.save_tick(symbol_name, tick)
        #this.db_adapter.bulk_save_ticks(this.market_name, symbol_name, ticks)

    def save_k10_index(this, k10_index):
        this.db_adapter.save_k10_index(k10_index)

    def save_k10_daily_rank(this, rank):
        symbol_name = rank.symbol
        sql = "select time, rank from %s where symbol = '%s' order by time desc limit 1" % (this.market_name, symbol_name)
        this.logger.debug(sql)
        ret = this.db_adapter.query(sql, epoch = 's')
        if ret and ret.has_key('series'):
            latest_timestamp = ret['series'][0]['values'][0][0]
            if long(rank.time) + this.timezone_offset <= long(latest_timestamp):
                return
        this.db_adapter.save_k10_daily_rank(this.market_name, rank)

    def query_k10_daily_rank(this, start_second):
        sql = "select time, symbol, market_cap_usd, rank from k10_daily_rank where time <= %s group by symbol order by time desc limit 1" % (start_second * 1000000000)
        this.logger.debug(sql)
        result = this.db_adapter.query(sql, epoch = 's')
        #print('++++++++++', result['series'][0]['values'][0])
        if len(result) == 0 or not result.has_key('series'):
            return None
        return result['series']

    def query_previous_min_price(this, symbol_name_usdt, symbol_name_btc, start_second):
        sql = "select time, market, symbol, high, low, open, close, volume from market_ticks where (symbol = '%s' or symbol = '%s') and time >= %s and time < %s  group by market, symbol order by time desc limit 1" % (symbol_name_usdt, symbol_name_btc, start_second*1000000000, start_second*1000000000+60000000000)
        this.logger.debug(sql)
        result = this.db_adapter.query(sql, epoch = 's')
        if len(result) == 0 or not result.has_key('series') or result['series'][0]['values'][0][1] == None:
            this.logger.warn('k10 calc Warning - All exchanges miss previous minute price for this symbol: %s , %s ', symbol_name_usdt, symbol_name_btc)
            return None
        return result['series']

    def query_latest_price_exist(this, symbol_name_usdt, symbol_name_btc, market, start_second):
        sql = "select time, market, symbol, high, low, open, close, volume from market_ticks where (symbol = '%s' or symbol = '%s') and market = '%s' and time < %s order by time desc limit 1" % (symbol_name_usdt, symbol_name_btc, market, start_second*1000000000)
        this.logger.debug(sql)
        result = this.db_adapter.query(sql, epoch = 's')
        if len(result) == 0 or not result.has_key('series') or result['series'][0]['values'][0][1] == None:
            this.logger.error('k10 calc Error - Exchange has no price for symbol: %s , %s, %s ', market, symbol_name_usdt, symbol_name_btc)
            return None
        return result['series']

    def query_market_ticks_for_validation(this, endSecond, validatePeriod):
        start = endSecond * 1000000000 - 60 * validatePeriod * 1000000000
        end = endSecond * 1000000000
        sql = "select time, market, symbol, high, low, open, close, volume, period, timezone_offset from market_ticks where time >= %s and time <= %s" % (start, end)
        print sql
        result = this.db_adapter.query(sql, epoch = 's')
        print result
        if len(result) == 0 or not result.has_key('series'):
            this.logger.error('validation Error - market_ticks table has price for time range: %s , %s ', start, end)
            return None
        return result['series']

    def get_generic_symbol_name(this, symbol_name):
        for symbol_index in range(len(this.symbols_market)):
            if this.symbols_market[symbol_index] == symbol_name:
                return this.symbols_default[symbol_index]

        return None
    
    def calculate_usd_prices(this, tick):
        if (not isinstance(tick, market_tick)) and (not isinstance(tick, dict)):
            return None

        if this.cache_manager:
            cached_prices = this.cache_manager.load_market_symbol_tick(this.market_name, this.symbols_default[0])

            if cached_prices:
                if isinstance(tick, market_tick):
                    tick.open = float(tick.open) * float(cached_prices[1])
                    tick.close = float(tick.close) * float(cached_prices[2])
                    tick.high = float(tick.high) * float(cached_prices[3])
                    tick.low = float(tick.low) * float(cached_prices[4])
                    return tick
                elif isinstance(tick, dict):
                    tick['open'] = float(tick['open']) * float(cached_prices[1])
                    tick['close'] = float(tick['close']) * float(cached_prices[2])
                    tick['high'] = float(tick['high']) * float(cached_prices[3])
                    tick['low'] = float(tick['low']) * float(cached_prices[4])
                    return tick

        return None

    def update_cache(this, symbol_name, tick):
        if this.cache_manager:
            tick_to_save = None

            if isinstance(tick, market_tick):
                tick_to_save = (long(tick.time), float(tick.open), float(tick.close), float(tick.high), float(tick.low))
            elif isinstance(tick, dict):
                tick_to_save = (long(tick['time']), float(tick['open']), float(tick['close']), float(tick['high']), float(tick['low']))

            this.cache_manager.save_market_symbol_tick(this.market_name, symbol_name, tick_to_save)
