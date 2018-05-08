import re

class kline_service(object):
    def __init__(this, client, settings):
        this.client = client
        this.settings = settings

    def get_kline_by_time_range(this, start, end):
        result_set = this.client.query('select * from market_ticks')
        return result_set.raw

    def get_influx_timegroup_by_resolution(this, resolution):
        match = re.search(r'^([0-9]+)$', resolution)

        if match:
            sql_time_group = '%sm' % match.group(1)
        elif resolution == 'D':
            sql_time_group = "1d"
        else:
            sql_time_group = "1d"

        return sql_time_group

    def get_tvkline_by_market_symbol(this, symbol, from_time, to_time, resolution, size):
        #sql = "select time, first(open) as open, last(close) as close, min(low) as low, max(high) as high from k10_index where time >= %d and time <= %d group by time(%s) order by time desc limit %d" % (from_time * 1e9, to_time * 1e9, this.get_influx_timegroup_by_resolution(resolution), size)

        #NOTE: ignore limits as tradingview will alwasy send from_time and to_time in a reasonable range
        sql = "select time, first(open) as open, last(close) as close, min(low) as low, max(high) as high from k10_index where time >= %d and time <= %d group by time(%s) order by time desc" % (from_time * 1e9, to_time * 1e9, this.get_influx_timegroup_by_resolution(resolution))
        rows = this.client.query(sql, epoch = 's')
        print "%d, %d rows: %d" % (from_time, to_time, len(rows))
        return rows 

    def get_kline_by_market_symbol(this, market, symbol, resolution, size):
        if market == 'market_index':
            sql = "select time, first(open) as open, last(close) as close, min(low) as low, max(high) as high from k10_index group by time(%s) order by time desc limit %d" % (this.get_influx_timegroup_by_resolution(resolution), size)
        else:
            sql = "select time, first(open) as open, last(close) as close, min(low) as low, max(high) as high from %s_ticks where market = '%s' and symbol = '%s' group by time(%s) order by time desc limit %d" % (market, market, symbol, this.get_influx_timegroup_by_resolution(resolution), size)
        rows = this.client.query(sql, epoch = 's')

        return rows 
