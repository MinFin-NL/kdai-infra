#!/bin/sh
# PIPELINE OVERRIDE: start PHP's built-in web server DIRECTLY so it inherits the full Container
# App environment. `php artisan serve` spawns the server as a subprocess with a curated
# $passthroughVariables allow-list that DROPS app env vars (ATTS_HEALTH_URL, START/STOP_
# TRANSCRIPTION_URL, TCS_URL, STREAM_*) which the transcription service reads via getenv() at
# request time. Running php -S directly fixes that. Falls back to `artisan serve` only if the
# Laravel server.php router can't be found, so a path change can never take the API offline.
ROUTER=/app/vendor/laravel/framework/src/Illuminate/Foundation/resources/server.php
if [ -f "$ROUTER" ]; then
  exec php -S 0.0.0.0:8000 -t /app/public "$ROUTER"
else
  echo "##[warning] server.php router not found at $ROUTER; falling back to 'artisan serve'" >&2
  exec php /app/artisan serve --host=0.0.0.0 --port=8000
fi
