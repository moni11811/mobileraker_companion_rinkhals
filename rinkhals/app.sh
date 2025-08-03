#!/bin/sh

. /useremain/rinkhals/.current/tools.sh

APP_ROOT=$(dirname $(realpath $0))


version() {
    grep -o '"version" *: *"[^"]*"' "$APP_ROOT/app.json" | cut -d '"' -f4
}


status() {
    PIDS=$(get_by_name mobileraker.py)
    if [ "$PIDS" = "" ]; then
        report_status $APP_STATUS_STOPPED
    else
        report_status $APP_STATUS_STARTED "$PIDS"
    fi
}

start() {
    stop
    cd $APP_ROOT

    mkdir -p $RINKHALS_HOME/mobileraker/logs
    mkdir -p $RINKHALS_HOME/printer_data/config
    rm -f $RINKHALS_HOME/printer_data/config/moonraker.conf
    ln -s $RINKHALS_HOME/printer_data/config/moonraker.generated.conf $RINKHALS_HOME/printer_data/config/moonraker.conf

    CONFIG_FILE="$RINKHALS_HOME/Mobileraker.conf"
    if [ ! -f "$CONFIG_FILE" ]; then
        cat > "$CONFIG_FILE" <<CFG
[printer _Default]
moonraker_uri = ws://127.0.0.1:7125/websocket
CFG
    fi

    export PYTHONPATH="$APP_ROOT:$APP_ROOT/lib/python3.11/site-packages"
    python mobileraker.py -c "$CONFIG_FILE" >> $RINKHALS_ROOT/logs/app-mobileraker.log 2>&1 &
    assert_by_name mobileraker.py
}

debug() {
    stop
    cd $APP_ROOT
    export PYTHONPATH="$APP_ROOT:$APP_ROOT/lib/python3.11/site-packages"
    python mobileraker.py -c "$RINKHALS_HOME/Mobileraker.conf" "$@"
}

stop() {
    kill_by_name mobileraker.py
}

case "$1" in
    status)
        status
        ;;
    start)
        start
        ;;
    debug)
        shift
        debug "$@"
        ;;
    version)
        version
        ;;

    stop)
        stop
        ;;
    *)
        echo "Usage: $0 {status|start|stop|debug|version}" >&2

        exit 1
        ;;
esac
