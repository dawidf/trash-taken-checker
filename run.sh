#!/usr/bin/with-contenv bashio

export SCHEDULE_URL
export STREET
export CAL_POJEMNIKI
export CAL_SEGREGACJA
export SUMMARY_POJEMNIKI
export SUMMARY_SEGREGACJA
export SUPERVISOR_TOKEN

SCHEDULE_URL=$(bashio::config 'schedule_url')
STREET=$(bashio::config 'street')
CAL_POJEMNIKI=$(bashio::config 'calendar_pojemniki')
CAL_SEGREGACJA=$(bashio::config 'calendar_segregacja')
SUMMARY_POJEMNIKI=$(bashio::config 'event_summary_pojemniki')
SUMMARY_SEGREGACJA=$(bashio::config 'event_summary_segregacja')
INTERVAL_DAYS=$(bashio::config 'check_interval_days')

while true; do
    bashio::log.info "Pobieram harmonogram wywozu odpadów dla ulicy: ${STREET}"
    if python3 /trash_checker.py; then
        bashio::log.info "Zakończono aktualizację kalendarzy."
    else
        bashio::log.error "Aktualizacja harmonogramu nie powiodła się, spróbuję ponownie przy następnym cyklu."
    fi
    bashio::log.info "Następne sprawdzenie za ${INTERVAL_DAYS} dni."
    sleep "$((INTERVAL_DAYS * 86400))"
done
