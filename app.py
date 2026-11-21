import math
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title='Dip Hunter', page_icon='📉', layout='wide', initial_sidebar_state='expanded')
st.title('📉 Dip Hunter')
st.markdown('''<style>
@media(max-width: 768px) {
 .block-container {padding-top: 1rem; padding-left: .8rem; padding-right: .8rem;}
 div[data-testid="stMetric"] {background: rgba(128,128,128,.07); padding: .6rem; border-radius: .7rem;}
 div[data-testid="stDataFrame"] {max-width: 100%;}
 button {min-height: 44px;}
}
</style>''', unsafe_allow_html=True)
st.caption('Aandelenscanner • Amerika + Europa • dagkoersen, geen realtime handelsfeed')

US = 'AAPL MSFT NVDA AMD INTC TSLA META AMZN GOOGL NFLX PLTR PYPL SQ COIN HOOD ROKU SHOP UBER ABNB DIS BA NKE PFE MRNA BNTX ENPH FSLR SMCI MU ARM RIVN LCID SOFI SNAP PINS DKNG CRWD PANW ZS MDB SNOW NET DDOG CELH LULU TGT WMT'.split()
EU = 'ASML.AS ADYEN.AS PHIA.AS INGA.AS ABN.AS HEIA.AS PRX.AS RAND.AS WKL.AS ASM.AS BESI.AS KPN.AS AKZA.AS NN.AS AALB.AS UNA.AS SHELL.AS MT.AS RWE.DE SAP.DE SIE.DE BAS.DE BMW.DE VOW3.DE ADS.DE DTE.DE IFX.DE BAYN.DE ALV.DE DBK.DE AIR.PA OR.PA MC.PA TTE.PA SAN.PA BNP.PA CAP.PA STMPA.PA DG.PA SU.PA KER.PA VIE.PA NOKIA.HE NESTE.HE NOVO-B.CO MAERSK-B.CO'.split()

# Names are resolved from Yahoo metadata when available; unknown values remain explicit.
@st.cache_data(ttl=86400, show_spinner=False)
def get_identity(ticker):
    try:
        info = yf.Ticker(ticker).get_info()
        return (info.get('shortName') or info.get('longName') or 'Naam onbekend',
                info.get('fullExchangeName') or info.get('exchange') or 'Beurs onbekend')
    except Exception:
        return 'Naam onbekend', 'Beurs onbekend'

@st.cache_data(ttl=600, show_spinner=False)
def get_market_status():
    # S&P 500 as market thermometer; a 20-day drawdown is a heuristic, not an official crash definition.
    try:
        data = yf.download('^GSPC', period='4mo', interval='1d', auto_adjust=True, progress=False, timeout=20)
        if data is None or data.empty:
            raise ValueError('geen indexgegevens')
        close = data['Close']
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        close = close.dropna()
        if len(close) < 21: raise ValueError('te weinig indexgegevens')
        drawdown = (float(close.iloc[-1])/float(close.tail(21).max())-1)*100
        ma20 = float(close.tail(20).mean())
        last = float(close.iloc[-1])
        if drawdown <= -10: status = 'Crash'
        elif drawdown <= -5 or last < ma20: status = 'Correctie'
        else: status = 'Normaal'
        return {'status': status, 'drawdown': round(drawdown,2), 'date': str(pd.Timestamp(close.index[-1]).date()), 'error': None}
    except Exception as exc:
        return {'status': 'Onbekend', 'drawdown': None, 'date': None, 'error': str(exc)[:120]}

def trade_advice(row, market_status, drop):
    # Screening label, not a personalized recommendation or guarantee.
    if market_status in ('Crash', 'Onbekend'):
        return 'WACHTEN'
    if row['Daling 5d %'] > -drop or row['Herstel /100'] < 75 or row['Risico /100'] > 40:
        return 'WACHTEN'
    if market_status == 'Correctie' and row['Herstel /100'] < 100:
        return 'WACHTEN'
    return 'KOPEN (signaal)'

with st.sidebar:
    st.header('Scannerinstellingen')
    market = st.selectbox('Markt', ['ALL', 'US', 'EU'])
    drop = st.slider('Minimale daling in 5 handelsdagen (%)', 5, 40, 15)
    target = st.slider('Winstdoel (%)', 1, 30, 10)
    stop = st.slider('Stop-loss (%)', 1, 20, 5)
    budget = st.number_input('Budget per aandeel (€)', min_value=1.0, value=200.0, step=25.0)
    min_vol = st.number_input('Minimale gemiddelde dagomzet (in lokale valuta)', value=1000000, step=500000)
    extra = st.text_area('Extra tickers (komma of spatie gescheiden)', placeholder='AAPL, ASML.AS, SAP.DE')
    only_matches = st.checkbox('Alleen aandelen met daling ≥ grens', value=True)
    run = st.button('🔎 Scan nu', type='primary', use_container_width=True)

@st.dialog('ℹ️ Informatie over Dip Hunter')
def show_information():
    st.info('📱 iPad: tik linksboven op het menu om de scaninstellingen te openen. Veeg horizontaal in de resultatentabel voor meer kolommen.\n\nKoersen: Yahoo Finance via yfinance. Dit zijn dagelijkse OHLCV-koersen, niet gegarandeerd live; vertraging verschilt per beurs. Datum per aandeel staat in de resultaten. Controleer de actuele bied-/laatprijs bij je broker vóór een order.')

if st.button('❔', help='Open informatie over de scanner', key='help_info'):
    show_information()

@st.cache_data(ttl=600, show_spinner=False)
def get_data(tickers):
    # Download batches separately so failures do not invalidate the whole scan.
    output = {}
    errors = []
    for start in range(0, len(tickers), 20):
        chunk = tickers[start:start+20]
        try:
            data = yf.download(chunk, period='4mo', interval='1d', auto_adjust=True, progress=False, threads=True, group_by='ticker', timeout=20)
            if data is None or data.empty:
                errors.append('Geen gegevens voor batch: '+', '.join(chunk))
                continue
            for ticker in chunk:
                try:
                    df = data[ticker].copy() if isinstance(data.columns, pd.MultiIndex) else data.copy()
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(-1)
                    df = df.dropna(subset=['Close', 'Volume'])
                    if len(df) >= 25:
                        output[ticker] = df
                    else:
                        errors.append(f'{ticker}: onvoldoende historie')
                except Exception:
                    errors.append(f'{ticker}: ontbrekende koersgegevens')
        except Exception as exc:
            errors.append('Databronfout: '+str(exc)[:140])
    return output, errors

@st.cache_data(ttl=3600, show_spinner=False)
def get_fx():
    try:
        df = yf.download('EURUSD=X', period='5d', interval='1d', progress=False, auto_adjust=True)
        if not df.empty:
            val = float(df['Close'].iloc[-1].iloc[0] if isinstance(df['Close'], pd.DataFrame) else df['Close'].iloc[-1])
            return val if val > 0 else None
    except Exception:
        pass
    return None

def rsi(close, period=14):
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    if down.iloc[-1] == 0:
        return 100.0 if up.iloc[-1] > 0 else 50.0
    return float(100 - 100/(1+up.iloc[-1]/down.iloc[-1]))

def evaluate(ticker, df, usd_per_eur, budget, target, stop):
    close = df['Close'].astype(float)
    volume = df['Volume'].astype(float)
    price = float(close.iloc[-1]); prev5 = float(close.iloc[-6])
    if price <= 0 or prev5 <= 0:
        return None
    decline = (price/prev5-1)*100
    ret1 = (price/float(close.iloc[-2])-1)*100
    r = rsi(close)
    ma5 = float(close.tail(5).mean())
    ma20 = float(close.tail(20).mean())
    avgvol = float(volume.iloc[-21:-1].mean())
    volratio = float(volume.iloc[-1]/avgvol) if avgvol > 0 else 0
    turnover = float((close.iloc[-21:-1]*volume.iloc[-21:-1]).mean())
    rebound = int(ret1 > 0) * 25 + int(price > ma5) * 25 + int(r >= 30 and r <= 55) * 25 + int(volratio >= 1.5 and ret1 > 0) * 25
    # Heuristic risk score, not a probability of loss or fundamental assessment.
    volatility = float(close.pct_change().tail(20).std()*math.sqrt(252)*100)
    risk = min(100, round(max(0, -decline-15)*1.5 + max(0,volatility-35)*0.65 + (25 if r < 25 else 0) + (20 if turnover < 1e6 else 0) + (15 if ret1 < -7 else 0)))
    currency = 'USD' if '.' not in ticker else ('GBp' if ticker.endswith('.L') else 'EUR' if ticker.endswith(('.AS','.DE','.PA','.HE','.BR','.MI')) else 'DKK' if ticker.endswith('.CO') else 'onbekend')
    if currency == 'USD':
        local_budget = budget * usd_per_eur if usd_per_eur else None
    elif currency == 'EUR':
        local_budget = budget
    else:
        local_budget = None
    shares = math.floor(local_budget/price) if local_budget is not None else None
    return {'Ticker':ticker, 'Datum koers':str(pd.Timestamp(df.index[-1]).date()), 'Valuta':currency,
            'Koers':round(price,3), 'Daling 5d %':round(decline,2), 'Herstel /100':rebound,
            'Risico /100':risk, 'RSI 14':round(r,1), 'Volume x':round(volratio,2),
            'Dagomzet':round(turnover), 'Volatiliteit %':round(volatility,1),
            'Doelkoers':round(price*(1+target/100),3), 'Stopkoers':round(price*(1-stop/100),3),
            'Aantal hele aandelen':shares, 'Kosten lokaal':round(shares*price,2) if shares is not None else None}

if run:
    custom = [t.strip().upper() for t in extra.replace(',', ' ').split() if t.strip()]
    tickers = list(dict.fromkeys((US if market in ('ALL','US') else []) + (EU if market in ('ALL','EU') else []) + custom))
    with st.spinner(f'{len(tickers)} tickers ophalen en analyseren…'):
        history, errors = get_data(tuple(tickers))
        fx = get_fx()
        results = []
        for ticker, df in history.items():
            try:
                row = evaluate(ticker, df, fx, budget, target, stop)
                if row and row['Dagomzet'] >= min_vol:
                    results.append(row)
            except Exception as exc:
                errors.append(f'{ticker}: analysefout {str(exc)[:80]}')
    st.session_state['history'] = history
    st.session_state['results'] = results
    st.session_state['errors'] = errors
    st.session_state['count'] = len(tickers)
    st.session_state['scan_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    st.session_state['market_status'] = get_market_status()

if 'results' in st.session_state:
    rows = st.session_state['results']
    matches = [x for x in rows if x['Daling 5d %'] <= -drop]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric('Tickers in universum',st.session_state['count'])
    c2.metric('Met bruikbare data + liquiditeit',len(rows))
    c3.metric('Dips die voldoen',len(matches))
    c4.metric('Scan uitgevoerd',st.session_state['scan_at'])
    shown = matches if only_matches else rows
    shown = sorted(shown, key=lambda x:(-x['Herstel /100'],x['Risico /100'],x['Daling 5d %']))
    ms = st.session_state.get('market_status', {'status':'Onbekend','drawdown':None,'date':None})
    st.subheader('🌍 Marktstatus — S&P 500')
    st.write(f"**{ms['status']}** · 20-daagse terugval vanaf hoogste slotkoers: {str(ms['drawdown']) + '%' if ms['drawdown'] is not None else 'onbekend'} · Laatste indexkoersdatum: {ms['date'] or 'onbekend'}")
    st.caption('Heuristiek: Crash bij ≤ −10% vanaf hoogste slotkoers van de laatste 21 handelsdagen; Correctie bij ≤ −5% of onder het 20-daags gemiddelde; anders Normaal. Dit is geen officiële beursclassificatie. De S&P 500 is een Amerikaanse marktindicator, geen volledige weergave van Europa.')
    if ms.get('error'): st.warning('Marktstatus niet beschikbaar: '+ms['error'])
    if shown:
        st.caption('Tip: tik op een rij en veeg in de tabel horizontaal om alle gegevens te bekijken.')
        # Enrich only visible rows to limit metadata calls and provider throttling.
        with st.spinner('Namen en beurzen van zichtbare aandelen ophalen…'):
            enriched = []
            for row in shown:
                name, exchange = get_identity(row['Ticker'])
                enriched.append({'Ticker':row['Ticker'], 'Naam':name, 'Beurs':exchange,
                                 'Marktstatus':ms['status'], 'Advies':trade_advice(row,ms['status'],drop), **{k:v for k,v in row.items() if k != 'Ticker'}})
        table = pd.DataFrame(enriched)
        st.dataframe(table, hide_index=True, use_container_width=True)

        st.download_button('⬇️ Download resultaten als CSV',table.to_csv(index=False).encode('utf-8-sig'),'dip_hunter_resultaten.csv','text/csv')
        selected = st.selectbox('Bekijk koersgrafiek', [r['Ticker'] for r in shown])
        st.line_chart(st.session_state['history'][selected]['Close'].rename('Aangepaste slotkoers')) if selected in st.session_state.get('history', {}) else st.caption('Geen koersgrafiek beschikbaar.')
        st.markdown('''**Interpretatie van de kolommen**
- **Ticker:** unieke beurscode van het aandeel.
- **Naam:** bedrijfsnaam volgens de databron; onbekend als die niet beschikbaar is.
- **Beurs:** handelsbeurs volgens de databron; onbekend als die niet beschikbaar is.
- **Marktstatus:** Normaal, Correctie, Crash of Onbekend, gebaseerd op de S&P 500.
- **Advies:** **KOPEN (signaal)** alleen als de koersdaling voldoet, herstelscore ≥ 75, risico ≤ 40 en de marktfilter dit toestaat; anders **WACHTEN**. Geen persoonlijk beleggingsadvies.
- **Datum koers:** datum van de laatste beschikbare dagkoers, niet noodzakelijk vandaag.
- **Valuta / Koers:** handelsvaluta en laatst beschikbare aangepaste slotkoers.
- **Daling 5d %:** procentuele koersverandering over vijf handelsdagen; negatief betekent daling.
- **Herstel /100:** technische herstelsignalen, hoger betekent meer signalen; **geen kanspercentage**.
- **Risico /100:** ruwe waarschuwing op basis van volatiliteit, daling en handelsactiviteit; hoger betekent meer risico.
- **RSI 14:** momentumindicator; lage waarden kunnen wijzen op sterke verkoopdruk.
- **Volume x:** handelsvolume laatste dag gedeeld door gemiddeld volume; boven 1 betekent meer activiteit.
- **Dagomzet:** gemiddelde geschatte dagomzet in lokale valuta.
- **Volatiliteit %:** geannualiseerde historische koersschommeling; hoger betekent beweeglijker.
- **Doelkoers / Stopkoers:** berekende niveaus bij respectievelijk +10% en −5% (of jouw instellingen); uitvoering niet gegarandeerd.
- **Aantal hele aandelen / Kosten lokaal:** indicatief aantal binnen het eurobudget en bijbehorende kosten in handelsvaluta, zonder transactiekosten of valutamarge.

**Datakwaliteit:** Yahoo Finance-dagkoersen kunnen vertraagd of onvolledig zijn. Controleer actuele prijzen en bedrijfsnieuws bij je broker. Geen automatische orders.''')
    else:
        st.warning('Geen kandidaten met deze filters. Dit is een geldig resultaat; de scanner verzint geen signalen. Probeer eventueel de grens of het liquiditeitsfilter aan te passen.')
    if st.session_state.get('errors'):
        with st.expander(f'Waarschuwingen databron ({len(st.session_state["errors"])})'):
            st.write('\n'.join(st.session_state['errors'][:100]))
else:
    st.write('Klik links op **Scan nu** om de ingestelde aandelen te analyseren.')

st.divider()
st.markdown('**Algemene toelichting:** Herstelscore 0–100 is een eenvoudige technische score, geen kansberekening. Risicoscore 0–100 is een ruwe waarschuwing op basis van koersbeweging, volatiliteit en liquiditeit; geen fundamentele of nieuwscontrole. De scanner scant een vooraf ingestelde selectie aandelen, niet de volledige Amerikaanse en Europese beurzen. Aantal aandelen is een indicatie zonder kosten of valutamarge. **Geen automatische orders.**')
