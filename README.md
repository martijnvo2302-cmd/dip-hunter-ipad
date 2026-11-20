# Dip Hunter — iPad-webapp

Dit is de webversie van de bestaande Dip Hunter v1, gebouwd met Streamlit. De scanner gebruikt Yahoo Finance via `yfinance` voor historische dagkoersen. Het is geen realtime koersfeed en geen handelsplatform.

## Online zetten met Streamlit Community Cloud

Benodigd: gratis GitHub-account en toegang tot Streamlit Community Cloud. Gratis hosting is afhankelijk van de actuele voorwaarden van de aanbieder.

1. Download de ZIP en pak hem uit op een computer (of gebruik op de iPad de Bestanden-app).
2. Maak op https://github.com/new een nieuwe repository, bijvoorbeeld `dip-hunter-ipad`. Kies **Private** als je de broncode niet publiek wilt delen. Let op: de app-URL en toegangsregels van Streamlit Cloud zijn apart van de repository-privacy.
3. Upload **de inhoud** van de uitgepakte map naar de root van de repository: `app.py`, `requirements.txt`, `README.md` en de map `.streamlit` met `config.toml`. De `.streamlit`-map is optioneel; de app werkt ook zonder deze map.
4. Open https://share.streamlit.io/ en meld je aan met GitHub. Kies **Create app** / **Deploy an app**, selecteer je repository en branch (meestal `main`), en zet **Main file path** op `app.py`. Klik op **Deploy**.
5. Wacht tot de installatie klaar is. Open de URL van je app in Safari op je iPad. Bij fouten: bekijk de app-logs in Streamlit Cloud.
6. Tik in Safari op het **Deel**-symbool (vierkant met pijl omhoog) en kies **Zet op beginscherm** / **Add to Home Screen**. Tik op **Voeg toe**. De exacte benaming verschilt per iPadOS-versie.

**Let op:** Streamlit Cloud-apps kunnen in slaapstand gaan. De eerste scan na het ontwaken duurt langer. Publieke apps zijn toegankelijk voor anderen met de URL. Zet geen brokergegevens, wachtwoorden of API-sleutels in de repository.

## Gebruik

- Open het menu linksboven en laat standaardinstellingen staan: `ALL`, `15%` daling in 5 handelsdagen, `10%` winstdoel, `5%` stop-loss, `€200` budget.
- Tik op **Scan nu**. De scan haalt een vaste lijst Amerikaanse en Europese aandelen op, geen volledige beurs.
- Bekijk de tabel, grafiek en exporteer CSV.
- Geen kandidaten betekent dat geen aandeel aan de filters voldeed of dat de databron onvoldoende gegevens leverde. Bekijk de databronwaarschuwingen.

## Belangrijke beperkingen

- Dagkoersen kunnen vertraagd, onvolledig of gecorrigeerd zijn. De datum in de tabel is de datum van de laatst beschikbare dagbar, niet een realtime quote.
- Scores zijn technische heuristieken en geen kansberekeningen. De tool controleert niet op nieuws, winstcijfers of faillissementsrisico.
- Voor USD wordt een indicatieve EUR/USD-dagkoers gebruikt. Voor DKK wordt geen aandelen-aantal berekend; wisselkoersen en kosten kunnen afwijken.
- De stop-loss is alleen een getoonde prijs; er worden geen orders geplaatst en een daadwerkelijke stoporder kan slechter worden uitgevoerd.
- Gebruik vóór een order de actuele bied-/laatprijs van je broker. De strategie kan verlies opleveren en +10% winst is niet gegarandeerd.

## Lokaal testen (optioneel)

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Privacy en betrouwbaarheid

Er worden geen accounts of transacties opgeslagen door deze app. De hostingprovider en de externe koersdatabron kunnen wel technische gegevens verwerken. Yahoo Finance kan verzoeken beperken of blokkeren; voor productiegebruik is een gelicentieerde marktdata-API beter.
