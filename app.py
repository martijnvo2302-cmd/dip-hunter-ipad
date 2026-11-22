import math
import textwrap
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title='PD Hunter', page_icon='📈', layout='wide', initial_sidebar_state='expanded')
st.title('📈 PD Hunter')
st.markdown('''<style>
@media(max-width: 768px) {
 .block-container {padding-top: 1rem; padding-left: .8rem; padding-right: .8rem;}
 div[data-testid="stMetric"] {background: rgba(128,128,128,.07); padding: .6rem; border-radius: .7rem;}
 div[data-testid="stDataFrame"] {max-width: 100%;}
 button {min-height: 44px;}
}
</style>''', unsafe_allow_html=True)
st.caption('Dip Hunter + Peak Hunter • VS en Europa • vertraagde/dagkoersen, geen realtime handelsfeed')

US = 'AAPL MSFT NVDA AMD INTC TSLA META AMZN GOOGL NFLX PLTR PYPL SQ COIN HOOD ROKU SHOP UBER ABNB DIS BA NKE PFE MRNA BNTX ENPH FSLR SMCI MU ARM RIVN LCID SOFI SNAP PINS DKNG CRWD PANW ZS MDB SNOW NET DDOG CELH LULU TGT WMT'.split()
EU = 'ASML.AS ADYEN.AS PHIA.AS INGA.AS ABN.AS HEIA.AS PRX.AS RAND.AS WKL.AS ASM.AS BESI.AS KPN.AS AKZA.AS NN.AS AALB.AS UNA.AS SHELL.AS MT.AS RWE.DE SAP.DE SIE.DE BAS.DE BMW.DE VOW3.DE ADS.DE DTE.DE IFX.DE BAYN.DE ALV.DE DBK.DE AIR.PA OR.PA MC.PA TTE.PA SAN.PA BNP.PA CAP.PA STMPA.PA DG.PA SU.PA KER.PA VIE.PA NOKIA.HE NESTE.HE NOVO-B.CO MAERSK-B.CO'.split()

# Names are resolved from Yahoo metadata when available; unknown values remain explicit.
@st.cache_data(ttl=86400, show_spinner=False)
def get_identity(ticker):
    try:
        info = yf.Ticker(ticker).get_info() or {}
        return (info.get('shortName') or info.get('longName') or 'Naam onbekend',
                info.get('fullExchangeName') or info.get('exchange') or 'Beurs onbekend')
    except Exception:
        return 'Naam onbekend', 'Beurs onbekend'

@st.cache_data(ttl=21600, show_spinner=False)
def get_fundamentals(ticker):
    try:
        info = yf.Ticker(ticker).get_info() or {}
        return {key: info.get(key) for key in ('revenueGrowth','earningsGrowth','forwardPE','trailingPE','targetMeanPrice','numberOfAnalystOpinions','longBusinessSummary','shortName','fullExchangeName','currency')}
    except Exception:
        return {}

def safe_number(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (ValueError, TypeError):
        return None

def peak_evaluate(ticker, df, days, minimum, maximum):
    close = df['Close'].astype(float).dropna()
    if len(close) < max(days + 1, 51):
        return None
    last = float(close.iloc[-1]); previous = float(close.iloc[-days-1])
    if last <= 0 or previous <= 0:
        return None
    gain = (last/previous-1)*100
    if not minimum <= gain <= maximum:
        return None
    ma20 = float(close.tail(20).mean())
    ma50 = float(close.tail(50).mean())
    r = rsi(close)
    if last <= ma20 or ma20 <= ma50 or r >= 80:
        return None
    return {'Ticker':ticker,'Datum koers':str(pd.Timestamp(df.index[-1]).date()),
            'Koers':round(last,3),'Groei %':round(gain,2),'RSI 14':round(r,1),
            'Trend /100':25*int(last>ma20)+25*int(ma20>ma50)+25*int(45<=r<=70)+25*int(float(close.iloc[-1])>float(close.iloc[-6]))}

def peak_enrich(row):
    info = get_fundamentals(row['Ticker'])
    price = row['Koers']; rev = safe_number(info.get('revenueGrowth'))
    earnings = safe_number(info.get('earningsGrowth'))
    fpe = safe_number(info.get('forwardPE'))
    target = safe_number(info.get('targetMeanPrice'))
    upside = (target/price-1)*100 if target and target>0 and price>0 else None
    analysts = safe_number(info.get('numberOfAnalystOpinions'))
    # Evidence-based screen; strategy quality is NOT automatically verified.
    growth = 25*int(rev is not None and rev>=.10)+25*int(earnings is not None and earnings>=.10)
    valuation = 25*int(fpe is not None and 0<fpe<=30)+25*int(upside is not None and upside>=15 and analysts is not None and analysts>=3)
    evidence = int(rev is not None)+int(earnings is not None)+int(fpe is not None)+int(upside is not None and analysts is not None and analysts>=3)
    if evidence < 2:
        verdict = 'ONVOLDOENDE DATA'
    elif row['RSI 14']>=75 or (fpe is not None and fpe>60):
        verdict = 'WACHTEN'
    elif growth+valuation>=75 and row['Trend /100']>=75:
        verdict = 'VERDER ONDERZOEKEN'
    else:
        verdict = 'WACHTEN'
    return {'Ticker':row['Ticker'], 'Naam':info.get('shortName') or get_identity(row['Ticker'])[0],
            'Beurs':info.get('fullExchangeName') or get_identity(row['Ticker'])[1],
            'Datum koers':row['Datum koers'], 'Koers':price, 'Groei %':row['Groei %'],
            'Trend /100':row['Trend /100'], 'RSI 14':row['RSI 14'],
            'Omzetgroei %':round(rev*100,1) if rev is not None else None,
            'Winstgroei %':round(earnings*100,1) if earnings is not None else None,
            'Forward P/E':round(fpe,1) if fpe is not None else None,
            'Analistenruimte %':round(upside,1) if upside is not None else None,
            'Groei/waardering /100':growth+valuation, 'Signaal':verdict}


# Yahoo Finance index symbols. Availability depends on Yahoo's feed.
BENCHMARKS = {
    'S&P 500 (VS)': '^GSPC',
    'STOXX Europe 600 (Europa)': '^STOXX',
}

def default_benchmark(ticker):
    ticker = ticker.upper()
    if region_for_ticker(ticker) == 'Europa': return 'STOXX Europe 600 (Europa)'
    return 'S&P 500 (VS)'

@st.cache_data(ttl=900, show_spinner=False)
def get_index_history(symbol):
    """Adjusted daily closes, not a real-time quote."""
    try:
        data = yf.download(symbol, period='1y', interval='1d', auto_adjust=True,
                           progress=False, timeout=20)
        if data is None or data.empty:
            return pd.Series(dtype=float)
        close = data['Close']
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close = pd.to_numeric(close, errors='coerce').dropna()
        close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
        return close[~close.index.duplicated(keep='last')].sort_index()
    except Exception:
        return pd.Series(dtype=float)


def comparison_chart(ticker, history, chart_key):
    """Use the same chart UI for Dip and Peak Hunter."""
    if ticker not in history:
        st.info('Geen koershistorie voor dit aandeel beschikbaar.')
        return
    days = st.select_slider('Grafiekperiode (handelsdagen)',
                            options=[5, 10, 20, 40, 90], value=40,
                            key=f'{chart_key}_days')
    label = default_benchmark(ticker)
    st.caption(f'Automatische indexvergelijking: {label}')
    stock = pd.to_numeric(history[ticker]['Close'], errors='coerce').dropna()
    stock.index = pd.to_datetime(stock.index).tz_localize(None).normalize()
    stock = stock[~stock.index.duplicated(keep='last')].sort_index()
    index_series = get_index_history(BENCHMARKS[label])
    if index_series.empty:
        st.warning(f'Geen indexgegevens voor {label}. Alleen het aandeel wordt getoond.')
        aligned = pd.DataFrame({'Aandeel': stock}).tail(days + 1)
    else:
        aligned = pd.concat([stock.rename('Aandeel'), index_series.rename(label)],
                            axis=1, join='inner').dropna().tail(days + 1)
    if len(aligned) < 2 or (aligned.iloc[0] <= 0).any():
        st.info('Onvoldoende overlappende dag-slotkoersen voor de grafiek.')
        return
    relative = (aligned / aligned.iloc[0] - 1) * 100
    st.line_chart(relative, y_label='Verandering sinds start (%)',
                  x_label='Handelsdatum', use_container_width=True)
    st.caption(f'Genormaliseerd op 0% van {aligned.index[0].date()} t/m '
               f'{aligned.index[-1].date()}; alleen gezamenlijke handelsdagen. '
               'Aangepaste dag-slotkoersen, niet realtime. '
               'Valuta-effecten zijn NIET omgerekend: vergelijkingen tussen '
               'verschillende valuta zijn indicatief. Historische prestaties '
               'voorspellen geen toekomstige resultaten.')


@st.cache_data(ttl=600, show_spinner=False)
def get_market_status(symbol):
    """Market-regime heuristic using adjusted daily index closes, not live prices."""
    try:
        close = get_index_history(symbol)
        if len(close) < 21:
            raise ValueError('te weinig indexgegevens')
        close = close.tail(90)
        drawdown = (float(close.iloc[-1]) / float(close.tail(21).max()) - 1) * 100
        ma20 = float(close.tail(20).mean())
        last = float(close.iloc[-1])
        if drawdown <= -10: status = 'Crash'
        elif drawdown <= -5 or last < ma20: status = 'Correctie'
        else: status = 'Normaal'
        return {'status': status, 'drawdown': round(drawdown, 2),
                'date': str(pd.Timestamp(close.index[-1]).date()), 'error': None}
    except Exception as exc:
        return {'status': 'Onbekend', 'drawdown': None, 'date': None,
                'error': str(exc)[:120]}


def region_for_ticker(ticker):
    """Exchange suffix determines US vs Europe; custom unrecognized tickers default US."""
    return 'Europa' if ticker.upper().endswith(('.AS', '.DE', '.PA', '.HE', '.CO', '.L', '.SW', '.MI', '.MC', '.BR', '.OL', '.ST')) else 'VS'


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
    peak_days = st.select_slider('Peak Hunter: groeiperiode (handelsdagen)', options=[5,10,20,40], value=20)
    peak_min = st.slider('Peak Hunter: minimale groei (%)', 1, 30, 5)
    peak_max = st.slider('Peak Hunter: maximale groei (%)', 10, 100, 40)
    run = st.button('🔎 Scan nu', type='primary', use_container_width=True)

@st.dialog('ℹ️ Informatie over PD Hunter')
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

DIP_EXPLANATIONS = [
    ('Ticker / Naam / Beurs','Beurscode, bedrijfsnaam en handelsbeurs volgens Yahoo Finance.'),
    ('Marktstatus','Normaal, Correctie, Crash of Onbekend: S&P 500 voor VS-aandelen, STOXX Europe 600 voor Europese aandelen; gebaseerd op dagkoersen.'),
    ('Advies','KOPEN (signaal) of WACHTEN volgens technische filters; geen garantie of persoonlijk advies.'),
    ('Datum koers / Valuta / Koers','Laatste beschikbare aangepaste dagslotkoers en handelsvaluta.'),
    ('Daling 5d %','Koersverandering over vijf handelsdagen; negatief is daling.'),
    ('Herstel /100','Technische herstelsignalen; geen kans op winst.'),
    ('Risico /100','Indicatieve technische risicowaarschuwing; hoger is ongunstiger.'),
    ('RSI 14 / Volume x','Momentumindicator en volume ten opzichte van het gebruikelijke volume.'),
    ('Dagomzet / Volatiliteit %','Indicatieve handelsactiviteit en historische beweeglijkheid.'),
    ('Doelkoers / Stopkoers','Rekenprijzen bij je winstdoel en stop-loss; geen orders.'),
    ('Aantal hele aandelen / Kosten lokaal','Aantal binnen budget en geschatte kosten in handelsvaluta, exclusief kosten.'),
]

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
    st.session_state['market_statuses'] = {'VS': get_market_status('^GSPC'), 'Europa': get_market_status('^STOXX')}
    st.session_state['peak_days'] = peak_days
    st.session_state['peak_min'] = peak_min
    st.session_state['peak_max'] = peak_max

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
    market_statuses = st.session_state.get('market_statuses', {})
    st.subheader('🌍 Marktstatus — VS en Europa')
    for region, label in [('VS', 'S&P 500'), ('Europa', 'STOXX Europe 600')]:
        ms = market_statuses.get(region, {'status':'Onbekend','drawdown':None,'date':None,'error':'geen data'})
        drawdown_text = f"{ms['drawdown']}%" if ms.get('drawdown') is not None else 'onbekend'
        st.write(f"**{label}: {ms['status']}** · 21-daagse terugval: {drawdown_text} · Laatste indexdatum: {ms.get('date') or 'onbekend'}")
        if ms.get('error'):
            st.warning(f'{label}: indexgegevens niet beschikbaar ({ms["error"]}). Advies voor deze regio wordt WACHTEN.')
    st.caption('Marktstatus is een heuristiek op vertraagde dagkoersen: Crash bij ≤ −10% vanaf de hoogste slotkoers in 21 handelsdagen; Correctie bij ≤ −5% of onder het 20-daags gemiddelde; anders Normaal. Geen officiële beursclassificatie. Advies per aandeel gebruikt de eigen regio.')
    if shown:
        st.caption('Tip: tik op een rij en veeg in de tabel horizontaal om alle gegevens te bekijken.')
        # Enrich only visible rows to limit metadata calls and provider throttling.
        with st.spinner('Namen en beurzen van zichtbare aandelen ophalen…'):
            enriched = []
            for row in shown:
                name, exchange = get_identity(row['Ticker'])
                region = region_for_ticker(row['Ticker'])
                status = market_statuses.get(region, {}).get('status', 'Onbekend')
                enriched.append({'Ticker':row['Ticker'], 'Naam':name, 'Beurs':exchange,
                                 'Marktstatus':status, 'Advies':trade_advice(row,status,drop), **{k:v for k,v in row.items() if k != 'Ticker'}})
        table = pd.DataFrame(enriched)
        # Colour only the advice column; CSV retains the original plain-text values.
        def advice_style(value):
            if value == 'WACHTEN':
                return 'color: #b91c1c; background-color: #fee2e2; font-weight: bold'
            if value == 'KOPEN (signaal)':
                return 'color: #166534; background-color: #dcfce7; font-weight: bold'
            return ''

        styled_table = table.style.map(advice_style, subset=['Advies'])
        st.dataframe(styled_table, hide_index=True, use_container_width=True)

        st.download_button('⬇️ Download resultaten als CSV',table.to_csv(index=False).encode('utf-8-sig'),'dip_hunter_resultaten.csv','text/csv')
        selected = st.selectbox('Bekijk koersgrafiek', [r['Ticker'] for r in shown])
        st.subheader('📊 Dip Hunter — koersgrafiek en indexvergelijking')
        comparison_chart(selected, st.session_state.get('history', {}), 'dip_chart')
        with st.expander('📖 Interpretatie Dip Hunter-kolommen', expanded=True):
            for title, description in DIP_EXPLANATIONS:
                st.write(f'• **{title}:** {description}')
    else:
        st.warning('Geen kandidaten met deze filters. Dit is een geldig resultaat; de scanner verzint geen signalen. Probeer eventueel de grens of het liquiditeitsfilter aan te passen.')
    if st.session_state.get('errors'):
        with st.expander(f'Waarschuwingen databron ({len(st.session_state["errors"])})'):
            st.write('\n'.join(st.session_state['errors'][:100]))
else:
    st.write('Klik links op **Scan nu** om de ingestelde aandelen te analyseren.')

st.divider()
st.header('📈 Peak Hunter — groeikandidaten')
st.caption('Zoekt stijgende aandelen met een positieve technische trend en controleert beschikbare groeicijfers en waardering. Of een strategie veelbelovend is of groei nog niet is ingeprijsd, kan niet betrouwbaar automatisch worden vastgesteld.')
if 'history' in st.session_state:
    history = st.session_state['history']
    days = st.session_state.get('peak_days',20)
    minimum = st.session_state.get('peak_min',5)
    maximum = st.session_state.get('peak_max',40)
    candidates = []
    for ticker, df in history.items():
        try:
            result = peak_evaluate(ticker,df,days,minimum,maximum)
            if result is not None:
                candidates.append(result)
        except Exception:
            continue
    candidates.sort(key=lambda row:(-row['Trend /100'],-row['Groei %']))
    st.write(f'**{len(candidates)} technische kandidaten** over {days} handelsdagen; {minimum}% tot {maximum}% groei. Fundamentele beoordeling voor maximaal 15 kandidaten om dataverzoeken te beperken.')
    if candidates:
        with st.spinner('Groei- en waarderingsgegevens ophalen…'):
            peak_rows = [peak_enrich(row) for row in candidates[:15]]
        peak_table = pd.DataFrame(peak_rows)
        def peak_style(value):
            if value == 'VERDER ONDERZOEKEN':
                return 'color: #166534; background-color: #dcfce7; font-weight: bold'
            if value == 'WACHTEN':
                return 'color: #b91c1c; background-color: #fee2e2; font-weight: bold'
            return 'font-weight: bold'
        st.dataframe(peak_table.style.map(peak_style,subset=['Signaal']),hide_index=True,use_container_width=True)
        st.download_button('⬇️ Download Peak Hunter als CSV',peak_table.to_csv(index=False).encode('utf-8-sig'),'peak_hunter_resultaten.csv','text/csv')
        st.subheader('📊 Peak Hunter — koersgrafiek en indexvergelijking')
        peak_ticker = st.selectbox('Kies een Peak Hunter-aandeel', peak_table['Ticker'].tolist(), key='peak_chart_ticker')
        comparison_chart(peak_ticker, history, 'peak_chart')

        st.caption('Analistenruimte = gemiddeld koersdoel versus laatste slotkoers; geen voorspelling. Ontbrekende data blijven leeg. De score toetst groeicijfers en waarderingsindicaties, niet de kwaliteit van de bedrijfsstrategie.')
    else:
        st.info('Geen Peak Hunter-kandidaten binnen deze instellingen. Pas eventueel de groeigrenzen aan.')
    with st.expander('📖 Interpretatie Peak Hunter-kolommen', expanded=True):
        for title, description in [
            ('Groei %','Koersstijging over de gekozen periode.'),
            ('Trend /100','Technische trendsterkte; hoger betekent meer positieve signalen.'),
            ('RSI 14','Momentum; een zeer hoge waarde kan oververhitting signaleren.'),
            ('Omzetgroei % / Winstgroei %','Recent gerapporteerde groeipercentages uit Yahoo-metadata; periode en actualiteit kunnen verschillen.'),
            ('Forward P/E','Verwachte koers-winstverhouding volgens de databron; laag is niet automatisch goedkoop.'),
            ('Analistenruimte %','Verschil tussen gemiddeld analistenkoersdoel en laatste koers, geen zekerheid.'),
            ('Groei/waardering /100','Eenvoudige indicator op basis van beschikbare groei- en waarderingsdata; geen kanspercentage.'),
            ('Signaal','VERDER ONDERZOEKEN, WACHTEN of ONVOLDOENDE DATA; geen automatisch koopadvies.'),
        ]:
            st.write(f'• **{title}:** {description}')
else:
    st.info('Voer eerst een scan uit om ook Peak Hunter-resultaten te zien.')

st.divider()
st.markdown('**Algemene toelichting:** Herstelscore 0–100 is een eenvoudige technische score, geen kansberekening. Risicoscore 0–100 is een ruwe waarschuwing op basis van koersbeweging, volatiliteit en liquiditeit; geen fundamentele of nieuwscontrole. De scanner scant een vooraf ingestelde selectie aandelen, niet de volledige Amerikaanse en Europese beurzen. Aantal aandelen is een indicatie zonder kosten of valutamarge. **Geen automatische orders.**')
