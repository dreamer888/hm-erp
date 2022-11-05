title init db GreenOdoo14 x64 fast - www.dreammm.net
rd /s/q .\odoofile
md odoofile
echo dreamm.net > .\odoofile\dreammm.net
cd runtime\pgsql\bin
rd /s/q ..\data
initdb.exe -D ..\data -E UTF8
pg_ctl -D ..\data -l logfile start
echo create user: all input 'odoo'
createuser --createdb --no-createrole --no-superuser --pwprompt odoo
cd ..\..\..