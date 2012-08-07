LOG_LVL=$1

./benchmark.py 10 10 block $LOG_LVL
./benchmark.py 10 1000 block $LOG_LVL
./benchmark.py 10 2000 block $LOG_LVL
./benchmark.py 10 10 async $LOG_LVL
./benchmark.py 10 1000 async $LOG_LVL
