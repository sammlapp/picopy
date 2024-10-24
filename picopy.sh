#! /bin/sh

### BEGIN INIT INFO
# Provides:          picopy.py
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
### END INIT INFO

# If you want a command to always run, put it here

# Carry out specific functions when asked to by the system
case "$1" in
  start)
    echo "Starting picopy.py"
    /usr/local/bin/picopy.py &
    ;;
  stop)
    echo "Stopping picopy.py"
    pkill -f /usr/local/bin/picopy.py
    ;;
  *)
    echo "Usage: /etc/init.d/picopy.sh {start|stop}"
    exit 1
    ;;
esac

exit 0