#!/bin/sh
echo "exporting customers"
sqlite3 data/customers.db "select * from customers"
