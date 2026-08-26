# Harmonogram wywozu śmieci

Dodatek pobiera harmonogram wywozu odpadów ze strony ZGK Sułkowice
(`zgksulkowice.pl`) dla wskazanej ulicy i raz na tydzień dodaje terminy jako
całodniowe wydarzenia do dwóch kalendarzy Home Assistant — osobno dla
"pojemników" i "segregacji". Jeśli na stronie podany jest zakres dat
(np. `9-10 IX`), do kalendarza trafia każdy dzień z tego zakresu osobno.

## 1. Wymagane kalendarze

Dodatek nie tworzy kalendarzy sam — trzeba je najpierw założyć (integracja
**Lokalny kalendarz** wbudowana w Home Assistant):

1. **Ustawienia → Urządzenia i usługi → Dodaj integrację → Lokalny kalendarz**
2. Utwórz dwie osobne instancje, np.:
   - nazwa `Wywóz pojemniki` → encja `calendar.wywoz_pojemniki`
   - nazwa `Wywóz segregacja` → encja `calendar.wywoz_segregacja`
3. Zapamiętaj dokładne `entity_id` obu kalendarzy — będą potrzebne w
   konfiguracji dodatku.

## 2. Instalacja dodatku

Ten katalog to gotowy lokalny dodatek. Umieść go w katalogu `addons` na
Home Assistant OS (np. przez Samba/SSH), a następnie:

**Ustawienia → Dodatki → Sklep z dodatkami → (⋮) Odśwież**, po czym
zainstaluj widoczny dodatek "Harmonogram wywozu śmieci".

## 3. Konfiguracja

Zakładka **Konfiguracja** dodatku:

| Opcja | Opis | Domyślnie |
|---|---|---|
| `schedule_url` | Adres strony z harmonogramem | link do ZGK Sułkowice |
| `street` | Fragment nagłówka ulicy na stronie (WIELKIMI LITERAMI, np. `STARCÓWKA`) | `STARCÓWKA` |
| `calendar_pojemniki` | `entity_id` kalendarza na terminy pojemników | `calendar.wywoz_pojemniki` |
| `calendar_segregacja` | `entity_id` kalendarza na terminy segregacji | `calendar.wywoz_segregacja` |
| `event_summary_pojemniki` | Tytuł wydarzenia dla pojemników | `Wywóz - pojemniki` |
| `event_summary_segregacja` | Tytuł wydarzenia dla segregacji | `Wywóz - segregacja` |
| `check_interval_days` | Co ile dni sprawdzać stronę ponownie | `7` |

Uzupełnij `entity_id` kalendarzy pod nazwy, które nadałeś w kroku 1, i
uruchom dodatek.

## Jak to działa

- Przy starcie i następnie co `check_interval_days` dni dodatek pobiera
  stronę, znajduje sekcję z nagłówkiem zawierającym `street` i wyciąga z niej
  wiersze `Pojemnik:` oraz `Segregacja:`.
- Rok harmonogramu jest odczytywany automatycznie z nagłówka strony
  (np. "IV-X 2026").
- Pojedyncze daty (`10 IV`) trafiają do kalendarza wprost. Dla zakresu dat
  (`9-10 IX`, także zakresu przechodzącego przez granicę miesiąca, np.
  `30 IV-4 V`) do kalendarza dodawany jest tylko pierwszy dzień zakresu.
- Przed dodaniem wydarzenia dodatek sprawdza, czy w kalendarzu nie ma już
  wpisu na dany dzień — ponowne uruchomienie nie tworzy duplikatów.
- Terminy, które już minęły, są pomijane.

## 4. Powiadomienie na telefon dzień wcześniej o 19:00

To robi zwykła automatyzacja Home Assistant (nie dodatek) — wyzwalacz
`calendar` ze startem wydarzenia i przesunięciem o -5h daje dokładnie
19:00 dnia poprzedniego (bo wydarzenie całodniowe zaczyna się o 00:00).

**Ustawienia → Automatyzacje i sceny → Utwórz automatyzację → Edytuj w YAML**:

```yaml
alias: "Przypomnienie: wywóz śmieci"
trigger:
  - platform: calendar
    entity_id: calendar.wywoz_pojemniki
    event: start
    offset: "-05:00:00"
    id: pojemniki
  - platform: calendar
    entity_id: calendar.wywoz_segregacja
    event: start
    offset: "-05:00:00"
    id: segregacja
action:
  - service: notify.notify
    data:
      title: "Wywóz śmieci jutro!"
      message: >-
        {% if trigger.id == 'pojemniki' %}
        Jutro wywóz pojemników 🗑️
        {% else %}
        Jutro wywóz segregacji ♻️
        {% endif %}
mode: parallel
```

`notify.notify` w Twojej instalacji już wysyła do wszystkich telefonów, więc
nie trzeba wymieniać ich osobno.

### Własna grupa odbiorców (jeśli chcesz inny zestaw telefonów niż `notify.notify`)

Jeśli zamiast "wszystkich" chcesz mieć oddzielną, nazwaną grupę (np. tylko
Ty + żona, bez reszty domowników), Home Assistant ma do tego wbudowaną
integrację **Notify Group**. Dodaje się ją w `configuration.yaml` (nie z
poziomu UI):

```yaml
notify:
  - platform: group
    name: wywoz_smieci
    services:
      - service: mobile_app_telefon_1
      - service: mobile_app_telefon_2
```

Po dodaniu i **restarcie Home Assistant** pojawi się serwis
`notify.wywoz_smieci`, którego możesz użyć w automatyzacji zamiast
`notify.notify`. Konkretne nazwy `mobile_app_...` znajdziesz w
**Narzędzia deweloperskie → Akcje**, wpisując `notify`.

## Logi

W razie problemów (np. nie znaleziono ulicy) sprawdź zakładkę **Log**
dodatku — w błędzie wypisywana jest lista nagłówków ulic znalezionych na
stronie, co pomaga poprawić wartość `street`.
