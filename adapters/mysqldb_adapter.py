import MySQLdb

from .database_adapter import database_adapter
from .utility import *

class mysqldb_adapter(database_adapter):
    def __init__(this, settings):
        super(mysqldb_adapter, this).__init__(settings)

        this.client = None

    def open(this):
        if not this.client:
            this.client = MySQLdb.connect(host = this.host, port = this.port, db = this.database, user = this.username, passwd = this.password)

        return this.client

    def close(this):
        if this.client:
            this.client.close()
            this.client = None

    def bulk_save_ticks(this, market_name, symbol_name, ticks):
        cursor = this.client.cursor()

        try:
            values = [
                "(%s, %s, %s, %s, %s, %s, %s, %s, '%s', '%s', '%s')" % (
                    tick.time + tick.timezone_offset,
                    tick.open,
                    tick.close,
                    tick.high,
                    tick.low,
                    tick.amount,
                    tick.volume,
                    tick.count,
                    market_name,
                    symbol_name,
                    tick.period
                )
                for tick in ticks         
            ]
            seperator = ","

            cursor.execute("insert into market_ticks(time, open, close, high, low, amount, volume, count, market, symbol, period) values %s" % seperator.join(values))
            this.client.commit()
        finally:
            cursor.close()

    def query(this, sql):
        cursor = this.client.cursor()

        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
            ticks = [
                list(row) for row in rows             
            ]

            ticks.sort(lambda x, y: int(x[0] - y[0]))
            result = {
                'series': [
                    {
                        'columns': [ 'time', 'open', 'close', 'low', 'high' ],
                        'values': ticks
                    }
                ]
            }

            return result
        finally:
            cursor.close()

