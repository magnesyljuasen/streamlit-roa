import streamlit as st
import streamlit_authenticator as stauth
import pymongo
import pandas as pd
import numpy as np
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import yaml
import base64
from PIL import Image
from datetime import datetime, timedelta
import requests

class Dashboard:
    def __init__(self):
        pass

    def streamlit_settings(self):
        st.set_page_config(
            page_title = "Røa Dashboard", 
            layout = "wide", 
            page_icon = "src/data/img/AsplanViak_Favicon_32x32.png", 
            initial_sidebar_state = "expanded"
            )
        with open("src/styles/main.css") as f:
            st.markdown("<style>{}</style>".format(f.read()), unsafe_allow_html=True)
            st.markdown('''<style>button[title="View fullscreen"]{visibility: hidden;}</style>''', unsafe_allow_html=True) # hide fullscreen
            #st.markdown("""<style>[data-testid="collapsedControl"] {display: none}</style>""", unsafe_allow_html=True) # ingen sidebar
            #st.markdown("""<style>div[data-testid="stSidebarNav"] {display: none;}</style>""", unsafe_allow_html=True) # litt av sidebar
            #st.markdown("""<style>.block-container {padding-top: 1rem;padding-bottom: 0rem;padding-left: 5rem;padding-right: 5rem;}</style>""", unsafe_allow_html=True)

    def streamlit_login(self):
        with open('src/login/config.yaml') as file:
            config = yaml.load(file, Loader=stauth.SafeLoader)
            authenticator = stauth.Authenticate(config['credentials'],config['cookie']['name'],config['cookie']['key'],config['cookie']['expiry_days'])
            name, authentication_status, username = authenticator.login(fields = {'Form name' : 'Logg inn', 'Username' : 'Brukernavn', 'Password' : 'Passord', 'Login' : 'Logg inn'})

        return name, authentication_status, username, authenticator

    def streamlit_login_page(self, name, authentication_status, username, authenticator):
        if authentication_status == False: # ugyldig passord
            st.error('Ugyldig brukernavn/passord')
            st.stop()
        elif authentication_status == None: # ingen input
#            st.image(Image.open('src/data/img/kolbotn_sesongvarmelager.jpg'), use_column_width=True)
            st.stop()
        elif authentication_status: # app start
            with st.sidebar:
                # st.image(Image.open('src/data/img/av_logo.png'), caption="Løsningen er laget av Asplan Viak for Røa IL") # logo
                # authenticator.logout('Logg ut')
                # st.caption(f"*Velkommen, {name}!*")
                # st.markdown("---")
                pass

    def database_to_df(self, mycollection, substring):
        query = {"Name": {"$regex": f".*{substring}.*"}}
        cursor = mycollection.find(query)
        data = []
        for document in cursor:
            data.append(document)
        df = pd.DataFrame(data)
        columns_to_exclude = ['_id']
        df = df.drop(columns=columns_to_exclude)
        df = df.drop_duplicates()
        df = df.drop(columns="Name")
        df.replace('', np.nan, inplace=True)
        df.replace(' ', np.nan, inplace=True)
        df = df.dropna(how='all')
        df = df.dropna(axis = 1, thresh=1)
        return df

    def get_names(self, df, substring):
        if substring == "TREND1":
            column_names = ["ID", "Date", "Time", "Utetemperatur", "RT401", "RT501", "RT402", "RT502", "RT403", "RT503", "RP401", "RP501", "RP402"]
        elif substring == "TREND2":
            column_names = ["ID", "Date", "Time", "Snø_1", "Snø_2", "RET_VARME", "RET_LADING", "STRØM_KWH"]
        df.columns = column_names
        return df

    def convert_to_float(self, value):
        return float(str(value).replace(',', '.'))

    def get_full_dataframe(self, normalize):
        #client = pymongo.MongoClient(**st.secrets["mongo"])
        client = pymongo.MongoClient("mongodb+srv://magnesyljuasen:jau0IMk5OKJWJ3Xl@cluster0.dlyj4y2.mongodb.net/")
        mydatabase = client["Røa"]
        mycollection = mydatabase["Driftsdata"]
        #--
        substring = "TREND1"
        df = self.database_to_df(mycollection = mycollection, substring = substring)
        df1 = self.get_names(df = df, substring = substring)
        #--
        substring = "TREND2"
        df = self.database_to_df(mycollection = mycollection, substring = substring)
        df2 = self.get_names(df = df, substring = substring)
        #--
        merged_df = pd.merge(df1, df2, on='ID')
        merged_df = merged_df.T.drop_duplicates().T
        merged_df['Tid'] = merged_df['Date_x'] + ' ' + merged_df['Time_x']
        merged_df = merged_df.drop(['Date_x', 'Time_x', 'ID'], axis=1)
        time_df = merged_df["Tid"]
        merged_df = merged_df.drop(["Tid"], axis = 1)
        merged_df = merged_df.applymap(self.convert_to_float)
        merged_df["Tid"] = time_df
        merged_df['Tid'] = pd.to_datetime(merged_df['Tid'], format='%d.%m.%y %H:%M:%S')
        merged_df = merged_df.sort_values('Tid')
        merged_df = merged_df.reset_index(drop = True)
        #
        merged_df['RET_VARME'] = (merged_df['RET_VARME'])*1000
        merged_df['RET_LADING'] = (merged_df['RET_LADING'])*1000
        merged_df['STRØM_KWH'] = (merged_df['STRØM_KWH'])*1000
        merged_df['COP'] = merged_df['RET_VARME'] / merged_df['STRØM_KWH']
        merged_df['ΔT over varmepumpen (°C)'] = merged_df['RT402'] - merged_df['RT502']
        #
        merged_df['RET_VARME_INCREMENT'] = merged_df['RET_VARME'].diff()
        merged_df['RET_LADING_INCREMENT'] = merged_df['RET_LADING'].diff()
        merged_df['STRØM_KWH_INCREMENT'] = merged_df['STRØM_KWH'].diff()
        #
        if normalize:
            merged_df['RET_VARME'] = merged_df['RET_VARME'] - merged_df['RET_VARME'][0]
            merged_df['RET_LADING'] = merged_df['RET_LADING'] - merged_df['RET_LADING'][0]
            merged_df['STRØM_KWH'] = merged_df['STRØM_KWH'] - merged_df['STRØM_KWH'][0]
        #
        merged_df = merged_df.rename(columns={
            "RT401" : "Temperatur ned i brønner (°C)",
            "RT501" : "Temperatur opp fra brønner (°C)",
            "RT402" : "Temperatur ut fra varmepumpe (°C)",
            "RT502" : "Temperatur inn til varmepumpe (°C)",
            "RT403" : "Temperatur til bane (°C)",
            "RT503" : "Temperatur fra bane (°C)", #?
            "RP401" : "Trykkmåler opp fra brønner (bar)",
            "RP501" : "Trykkmåler inn til varmepumpe (bar)",
            "RP402" : "Trykkmåler ut til bane? (bar)",
            "Snø_1" : "Snø 1",
            "Snø_2" : "Snø 2",
            "RET_LADING" : "Energi til brønner (kWh)",
            "RET_VARME" : "Energi til banen (kWh)",
            "STRØM_KWH" : "Strømforbruk (kWh)",
            "RET_LADING_INCREMENT" : "Effekt til brønner (kW)",
            "RET_VARME_INCREMENT" : "Effekt til banen (kW)",
            "STRØM_KWH_INCREMENT" : "Effektforbruk strøm (kW)",
            })

        return merged_df

    def download_csv(self, dataframe):
        csv_file = dataframe.to_csv(index=False)
        b64 = base64.b64encode(csv_file.encode()).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="data.csv">Trykk her for å laste ned data</a>'
        return href

    def energy_effect_plot(self, df, series, series_label, average = False, separator = False, min_value = None, max_value = None, chart_type = "Line"):
        if chart_type == "Line":
            fig = px.line(df, x=df['Tidsverdier'], y=series, labels={'Value': series, 'Timestamp': 'Tid'}, color_discrete_sequence=["rgba(29, 60, 52, 0.75)"])
        elif chart_type == "Bar":
            fig = px.bar(df, x=df['Tidsverdier'], y=series, labels={'Value': series, 'Timestamp': 'Tid'}, color_discrete_sequence=["rgba(29, 60, 52, 0.75)"])
        fig.update_xaxes(
            title='',
            type='category',
            gridwidth=0.3,
            tickmode='auto',
            nticks=4,  
            tickangle=30)
        fig.update_yaxes(
            title=f"Temperatur (ºC)",
            tickformat=",",
            ticks="outside",
            gridcolor="lightgrey",
            gridwidth=0.3,
        )
        if average == True:
            average = df[series].mean()
            delta_average = average * 0.98
            fig.update_layout(yaxis=dict(range=[average - delta_average, average + delta_average]))
        if separator == True:
            fig.update_layout(separators="* .*")
            
        fig.update_layout(
                #xaxis=dict(showticklabels=False),
                showlegend=False,
                margin=dict(l=20,r=20,b=20,t=20,pad=0),
                yaxis_title=series_label,
                yaxis=dict(range=[min_value, max_value]),
                xaxis_title="",
                height = 300
                )
        st.plotly_chart(fig, use_container_width=True, config = {'displayModeBar': False, 'staticPlot': False})

    def temperature_plot(self, df, series, min_value = 0, max_value = 10):
        fig = px.line(df, x=df['Tidsverdier'], y=series, labels={'Value': series, 'Timestamp': 'Tid'}, color_discrete_sequence=[f"rgba(29, 60, 52, 0.75)"])
        fig.update_xaxes(type='category')
        fig.update_xaxes(
            title='',
            type='category',
            gridwidth=0.3,
            tickmode='auto',
            nticks=4,  
            tickangle=30)
        fig.update_yaxes(
            title=f"Temperatur (ºC)",
            tickformat=",",
            ticks="outside",
            gridcolor="lightgrey",
            gridwidth=0.3,
        )
        fig.update_layout(
            #xaxis=dict(showticklabels=False),
            showlegend=False,
            yaxis=dict(range=[min_value, max_value]),
            margin=dict(l=20,r=20,b=20,t=20,pad=0),
            #separators="* .*",
            #yaxis_title=f"Temperatur {series_name.lower()} (ºC)",
            xaxis_title="",
            height = 300,
            )
        st.plotly_chart(fig, use_container_width=True, config = {'displayModeBar': False, 'staticPlot': False})

    def temperature_plot_two_series(self, df, series_1, series_2, min_value = 0, max_value = 10):
        fig1 = px.line(df, x=df['Tidsverdier'], y=series_1, labels={'Value': series_1, 'Timestamp': 'Tid'}, color_discrete_sequence=[f"rgba(29, 60, 52, 0.5)"])
        fig2 = px.line(df, x=df['Tidsverdier'], y=series_2, labels={'Value': series_2, 'Timestamp': 'Tid'}, color_discrete_sequence=[f"rgba(29, 60, 52, 0.5)"])
        fig = fig1
        fig.add_traces(fig2.data)
        fig.update_xaxes(
            title='',
            type='category',
            gridwidth=0.3,
            tickmode='auto',
            nticks=4,  
            tickangle=30)
        fig.update_yaxes(
            title=f"Temperatur (ºC)",
            tickformat=",",
            ticks="outside",
            gridcolor="lightgrey",
            gridwidth=0.3,
        )
        fig.update_layout(
            #xaxis=dict(showticklabels=False),
            showlegend=False,
            yaxis=dict(range=[min_value, max_value]),
            margin=dict(l=20,r=20,b=20,t=20,pad=0),
            #separators="* .*",
            height = 300,
            )
        st.plotly_chart(fig, use_container_width=True, config = {'displayModeBar': False, 'staticPlot': False})

    def embed_url_in_iframe(self, url):
        html = f'<div style="display: flex; justify-content: center;"><iframe src="{url}" width="800" height="600"></iframe></div>'
        st.components.v1.html(html, height = 600)

    def show_weather_statistics(self):
        url_pent = "https://pent.no/59.9428111,10.6324331"
        self.embed_url_in_iframe(url = url_pent)

    def show_webcam(self):
        url_webcam = "https://xn--vindn-qra.no/webkamera/oslo/oslo/r150-ullev%c3%a5l-(retning-t%c3%a5sen)-d3f197"
        self.embed_url_in_iframe(url = url_webcam)

    def get_date_string(self, date):
        datestring = str(date).split("-")
        day = int(datestring[2].split(" ")[0])
        year = datestring[0]
        month = int(datestring[1])
        month_map = {
            1 : 'jan',
            2 : 'feb',
            3 : 'mar',
            4 : 'apr',
            5 : 'mai',
            6 : 'jun',
            7 : 'jul',
            8 : 'aug',
            9 : 'sep',
            10 : 'okt',
            11 : 'nov',
            12 : 'des'
        }
        month = month_map[month]
        datestring = f"{day}. {month}, {year}"
        return datestring

    def date_picker(self, df):
        end_date = df["Tid"][len(df["Tid"]) - 1].to_pydatetime() + timedelta(days=1)
        date_range = st.date_input("Velg tidsintervall", (df["Tid"][0].to_pydatetime(), end_date), format = "DD/MM-YYYY")
        if len(date_range) == 1:
            st.error("Du må velge et tidsintervall")
            st.stop()
        filtered_df = df[(df['Tid'] >= pd.Timestamp(date_range[0])) & (df['Tid'] <= pd.Timestamp(date_range[1]))]
        filtered_df = filtered_df.reset_index(drop = True)
        if len(filtered_df) == 0:
            st.error("Ingen data i tidsintervall")
            st.stop()
        start_date = filtered_df['Tid'][0]
        end_date = filtered_df['Tid'][len(filtered_df)-1]
        return filtered_df, start_date, end_date
    
    def column_to_metric(self, df, metric_name, unit, rounding = -1):
        metric = f"{round(int(df[metric_name].to_numpy()[-1]), rounding):,} {unit}".replace(",", " ")
        return metric
    
    def column_to_delta(self, df, metric_name, unit, last_value, last_value_text, rounding = -2):
        delta = f"Forrige {last_value_text}: {round(int(df[metric_name].to_numpy()[-1] - df[metric_name].to_numpy()[last_value]), rounding):,} {unit}".replace(",", " ")
        return delta
    
    def get_temperature_series(self):
        client_id = "248d45de-6fc1-4e3b-a4b0-e2932420605e"
        endpoint = f"https://frost.met.no/observations/v0.jsonld?"
        parameters = {
            'sources' : 'SN17820',
            'referencetime' : f"2023-11-01/{datetime.date.today()}",
            'elements' : 'mean(air_temperature P1D)',
            'timeoffsets': 'PT0H',
            'timeresolutions' : 'P1D'
            }
        r = requests.get(endpoint, parameters, auth=(client_id,""))
        json = r.json()["data"]
        temperature_array, time_array = [], []
        for i in range(0, len(json)):
            reference_time = pd.to_datetime(json[i]["referenceTime"])
            formatted_date = reference_time.strftime("%d/%m-%y, %H:01")
            temperature = float(json[i]["observations"][0]["value"])
            temperature_array.append(temperature)
            time_array.append(formatted_date)
        
        self.df_temperature = pd.DataFrame({
            "Tidsverdier" : time_array,
            "Temperatur" : temperature_array
            })
    
    def default_kpi(self, df):
        days = len(df)/23
        value_1 = round(int(df['Tilført effekt - Bane 1'].sum()), -2)
        value_3 = round(int(df['Strømforbruk'].sum()), -2)
        value_2 = round(int(self.total_energyuse), -2)
        value_4 = round(int(self.total_poweruse), -2)
        unit = "kWh"
        #####
        kpi1, kpi2 = st.columns(2)
        with kpi1:
            st.markdown(f"**Mellom {self.start_date} og {self.end_date}**")
        kpi1.metric(
            label = f"Energi til bane 1",
            value = f"{value_1:,} {unit}".replace(",", " "),
            #delta = f"{round(value_1/days):,} {unit} per dag".replace(",", " "),
            help="Dette er energi tilført bane 1 i tidsintervallet."
            )
        #####
        kpi1.metric(
            label = f"Strømforbruk",
            value = f"{value_3:,} {unit}".replace(",", " "),
            #delta = f"{round(value_3/days):,} {unit} per dag".replace(",", " "),
            help="Dette er strømforbruk i tidsintervallet."
            )
        #####
        value_diff_1 = value_1 - value_3
        kpi1.metric(
            label = f"Besparelse",
            value = f"{value_diff_1:,} {unit}".replace(",", " "),
            #delta = f"{round(value_diff_1/days):,} {unit} per dag".replace(",", " "),
            help="Dette er besparelsen i tidsintervallet."
            )
        #####   
        value_5 = round(value_1/value_3, 1)
        kpi1.metric(
            label = f"Gjennomsnittlig COP",
            value = f"{value_5:,}".replace(".", ","),
            help="""Koeffisienten for ytelse (COP) er et viktig begrep innenfor 
            termodynamikk og energieffektivitet, spesielt for varmepumper og 
            kjølesystemer. COP måler hvor effektivt et system kan produsere 
            ønsket termisk effekt (som oppvarming eller nedkjøling) i forhold til 
            energien som brukes til å drive systemet."""
            )
        #####
        with kpi2:
            st.write("**Totalt**")
        kpi2.metric(
            label = "Energi til bane 1",
            value = f"{value_2:,} kWh".replace(",", " "),
            #delta = f"{round(value_2/self.total_days):,} kWh per dag".replace(",", " "),
            help="Totalt tilført energi bane 1."
        )
        #####
        kpi2.metric(
            label = "Strømforbruk",
            value = f"{value_4:,} kWh".replace(",", " "),
            #delta = f"{round(value_4/self.total_days):,} kWh per dag".replace(",", " "),
            help="Totalt strømforbruk."
        )
        #####
        value_diff_2 = value_2 - value_4
        kpi2.metric(
            label = "Besparelse",
            value = f"{value_diff_2:,} kWh".replace(",", " "),
            #delta = f"{round(value_diff_2/self.total_days):,} kWh per dag".replace(",", " "),
            help="Total besparelse."
        )
        #####
        value_6 = round(value_2/value_4, 1)
        kpi2.metric(
            label = "Gjennomsnittlig COP",
            value = f"{value_6:,}".replace(".", ","),
            help= 
            """ Koeffisienten for ytelse (COP) er et viktig begrep innenfor 
            termodynamikk og energieffektivitet, spesielt for varmepumper og 
            kjølesystemer. COP måler hvor effektivt et system kan produsere 
            ønsket termisk effekt (som oppvarming eller nedkjøling) i forhold til 
            energien som brukes til å drive systemet. """
        )

#        kpi2.metric(
#            label = "Energi tilført bane 2 ",
#            value = self.column_to_metric(df = df, metric_name = "Tilført energi - Bane 2", unit = "kWh"),
#            delta = self.column_to_delta(df = df, metric_name = "Tilført energi - Bane 2", unit = "kWh", last_value = last_value, last_value_text = last_value_text)
#        )
#        kpi3.metric(
#            label="Energi levert fra varmepumpe ",
#            value = self.column_to_metric(df = df, metric_name = "Energi levert fra varmepumpe", unit = "kWh"),
#            delta = self.column_to_delta(df = df, metric_name = "Energi levert fra varmepumpe", unit = "kWh", last_value = last_value, last_value_text = last_value_text)
#        )

    ## Åsmund fyll inn her
    def new_charts(self, df):
        def subplot(df, y_label, y_label_temperature = "Temperatur (ºC)"):
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.2, 0.1, 0.1])

            fig.add_trace(go.Bar(x=df['Tidsverdier'], y=df['Tilført effekt - Bane 1'], name='Tilført energi - Bane 1'), row=1, col=1)
            fig.add_trace(go.Bar(x=df['Tidsverdier'], y=df['Strømforbruk'], name='Strømforbruk'), row=1, col=1)
            fig.add_trace(go.Scatter(x=df['Tidsverdier'], y=df['COP'], mode='markers', name='COP'), row=2, col=1)
            fig.add_trace(go.Scatter(x=df['Tidsverdier'], y=df['Utetemperatur'], mode='lines+markers', name='Utetemperatur'), row=3, col=1)

            fig.update_traces(marker_color=f"rgba(29, 60, 52, 0.75)", row=1, col=1, selector=dict(name='Tilført energi - Bane 1'))
            fig.update_traces(marker_color=f"rgba(72, 162, 63, 0.75)", row=1, col=1, selector=dict(name='Strømforbruk'))
            fig.update_traces(marker=dict(color=f"rgba(51, 111, 58, 0.75)", size=5), row=2, col=1, selector=dict(name='COP'))
            fig.update_traces(line_color=f"rgba(255, 195, 88, 0.75)",row=3, col=1, selector=dict(name='Utetemperatur'))

            fig.update_xaxes(type='category')
            fig.update_xaxes(title='', type='category', gridwidth=0.3, tickmode='auto', nticks=4, tickangle=30)

            fig.update_yaxes(title_text=y_label, tickformat=" ", row=1, col=1)
            fig.update_yaxes(title_text="COP", row=2, col=1)
            fig.update_yaxes(title_text=y_label_temperature, row=3, col=1)

            fig.update_layout(height=600, width=300)
            fig.update_layout(legend=dict(orientation="h", yanchor="top", y=10), margin=dict(l=20,r=20,b=20,t=20,pad=0))
            st.plotly_chart(fig, use_container_width=True, config = {'displayModeBar': False, 'staticPlot': False})
        
        numeric_columns = df.select_dtypes(include=[float, int]).columns.tolist()
        columns_to_sum = [
            'Energi levert fra varmepumpe', 
            'Tilført energi - Bane 1', 
            'Tilført energi - Bane 2', 
            'CO2', 
            'Strømforbruk', 
            'Tilført effekt - Bane 1', 
            'Tilført effekt - Bane 2', 
            'Tilført effekt - Varmepumpe'
            ] # flere kolonner som skal summeres i stedet for å gjennomsnitt-es?

        aggregations = {col: np.sum if col in columns_to_sum else np.nanmean for col in numeric_columns}
        df_day = df.groupby(pd.Grouper(key='Tid', freq="D", offset='0S'))[numeric_columns].agg(aggregations).reset_index()
        df_day["Tidsverdier"] = df_day['Tid'].dt.strftime("%d/%m-%y, %H:01").tolist()

        df_week = df.groupby(pd.Grouper(key='Tid', freq="W", offset='0S'))[numeric_columns].agg(aggregations).reset_index()
        df_week["Tidsverdier"] = df_week['Tid'].dt.strftime("%d/%m-%y, %H:01").tolist()

        tab1, tab2, tab3 = st.tabs(["Dagsoppløsning", "Ukesoppløsning", "Timesoppløsning"])
        with tab1:
            st.caption("**Sammenstilling (energi per dag, strømforbruk og utetemperatur)**")
            subplot(df=df_day, y_label = "Energi (kWh)", y_label_temperature = "Gj.snittlig temperatur (ºC)")
        with tab2:
            if len(df)/23 >= 6:
                st.caption("**Sammenstilling (energi per uke, strømforbruk og utetemperatur)**")
                subplot(df=df_week, y_label = "Energi (kWh)", y_label_temperature = "Gj.snittlig temperatur (ºC)")
            else:
                st.warning("Det er valgt færre enn 7 dager (1 uke) i tidsintervallet.")
        with tab3:
            st.caption("**Sammenstilling (energi per time, strømforbruk og utetemperatur)**")
            st.caption("*NB! Merk at strømdata ikke er med timesoppløsning - derav jevn fordeling per døgn.*")
            subplot(df=df, y_label = "Timesmidlet effekt (kWh/h)")
            
       
        
        
        st.markdown("---")
    ## Slutt på Åsmund fyll inn her

    def default_charts(self, df):
        #options = ["Fra bane 1", "Turtemperatur VP (varm side)", "Utetemperatur", "Temperatur ned i 40 brønner", "Temperatur opp fra 40 brønner"]
        #columns = st.multiselect("velg", options = options)
        #new_df = df[columns]
        #st.line_chart(new_df)
        c1, c2 = st.columns(2)
        with c1:
            st.caption("**Temperatur fra bane 1**")
            self.temperature_plot(df = df, series = 'Fra bane 1', min_value = -10, max_value = 5)
#        with c2:
#            st.caption("**Temperatur fra bane 2**")
#            self.temperature_plot(df = df, series = 'Fra bane 2', min_value = 0, max_value = 15)
        with c2:
            st.caption("**Turtemperatur varmepumpe (varm side)**")
            self.temperature_plot(df = df, series = 'Turtemperatur VP (varm side)', min_value = 10, max_value = 40)
        with c1:
            st.caption("**Temperatur ned i 20 og 40 brønner**")
            self.temperature_plot_two_series(df = df, series_1 = 'Temperatur ned i 40 brønner', series_2 = 'Temperatur ned i 20 brønner', min_value = -5, max_value = 15)
        with c2:
            st.caption("**Temperatur opp fra 20 og 40 brønner**")
            self.temperature_plot_two_series(df = df, series_1 = 'Temperatur opp fra 40 brønner', series_2 = 'Temperatur opp fra 20 brønner', min_value = -5, max_value = 15)
        with c1:
            st.caption("**Temperaturføler i brønn (ytre og midten)**")
            self.temperature_plot_two_series(df = df, series_1 = 'Temperaturføler i brønn (ytre)', series_2 = 'Temperaturføler i brønn (midten)', min_value = -5, max_value = 15)
        with c2:
            st.caption("**Energi tilført bane 1 (akkumulert)**")
            self.energy_effect_plot(df = df, series = "Tilført energi - Bane 1", series_label = "Energi (kWh)", separator = True, chart_type = "Bar", min_value=0, max_value = 800000)
        with c1:
            st.caption("**Utetemperatur**")
            self.energy_effect_plot(df = df, series = "Utetemperatur", series_label = "Utetemperatur (°C)", separator = True, chart_type = "Line", min_value=-30, max_value = 30)
        with c2:
            st.caption("**Effekt tilført bane 1**")
            self.energy_effect_plot(df = df, series = "Tilført effekt - Bane 1", series_label = "Effekt (kW)", separator = True, chart_type = "Bar", min_value=0, max_value = 500)
        st.markdown("---")
        st.caption("**Strømforbruk per dag**")
        self.energy_effect_plot(df = self.df_el, series = "Strømforbruk", series_label = "Effekt (kW)", separator = True, chart_type = "Bar", min_value=0, max_value = 2000)
        



#        with c2:
#            st.caption("**Energi tilført bane 2**")
#            self.energy_effect_plot(df = df, series = "Tilført energi - Bane 2", series_label = "Energi (kWh)", chart_type = "Bar")
#        with c2:
#            st.caption("**Energi levert fra varmepumpe (akkumulert)**")
#            self.energy_effect_plot(df = df, series = "Energi levert fra varmepumpe", series_label = "Energi (kWh)", separator = True, chart_type = "Bar", min_value=0, max_value = 1000000)
        #--
#        c1, c2 = st.columns(2)
#        with c1:
#            st.caption("**CO2 tilført bane 1**")
#            self.energy_effect_plot(df = df, series = "CO2", series_label = "tonn CO2", separator = True, chart_type = "Bar")
#        with c2:
#            st.caption("**Energi tilført bane 2**")
#            self.energy_effect_plot(df = df, series = "Tilført energi - Bane 2", series_label = "Energi (kWh)", chart_type = "Bar")
#        with c2:
#            pass
        #--
#        c1, c2 = st.columns(2)
#        with c1:
#            st.caption("**Effekt tilført bane 1**")
#            self.energy_effect_plot(df = df, series = "Tilført effekt - Bane 1", series_label = "Timesmidlet effekt (kWh/h)", average = True, chart_type = "Bar", min_value = 0, max_value = 400)
#        with c2:
#            st.caption("**Effekt tilført bane 2**")
#            self.energy_effect_plot(df = df, series = "Tilført effekt - Bane 2", series_label = "Timesmidlet effekt (kWh/h)", average = True, min_value = 0, max_value = 400)
#        with c2:
#            st.caption("**Effekt levert fra varmepumpe**")
#            self.energy_effect_plot(df = df, series = "Tilført effekt - Varmepumpe", series_label = "Timesmidlet effekt (kWh/h)", average = True, chart_type = "Bar", min_value = 0, max_value = 400, separator = False)
 
#        st.markdown("---")
#        st.caption("**Strømforbruk**")
#        self.energy_effect_plot(df = self.df_el, series = "kWh", series_label = "Strøm (kWh)", separator = True, chart_type = "Bar")
#        st.caption("**Utetemperatur fra nærmeste værstasjon**")
#        self.energy_effect_plot(df = self.df_temperature, series = "Temperatur", series_label = "Utetemperatur", separator = True, chart_type = "Line")
#        self.energy_effect_plot(df = df, series = "Utetemperatur", series_label = "Energi (kWh)", separator = True, chart_type = "Line")   

    def show_weather_stats(self):
        c1, c2 = st.columns(2)
        with c1:
            with st.expander("Vær", expanded = False):
                self.show_weather_statistics()
        with c2:
            with st.expander("Webkamera", expanded = False):
                self.show_webcam()

    def add_columns_to_df(self, df):
        window_size = 3
        df['Tilført effekt - Bane 1'] = df["Tilført energi - Bane 1"].diff().rolling(window=window_size).mean()
        df['Tilført effekt - Bane 2'] = df["Tilført energi - Bane 2"].diff().rolling(window=window_size).mean()
        df['Tilført effekt - Varmepumpe'] = df["Energi levert fra varmepumpe"].diff().rolling(window=window_size).mean()
        return df
    
    def resolution_picker(self, df):
        selected_option = st.selectbox("Velg oppløsning", options = ["Rådata", "Timer", "Daglig", "Ukentlig", "Månedlig", "År"])
        resolution_mapping = {
           "Rådata" : "Rådata",
           "Timer" : "H",
            "Daglig": "D",
            "Ukentlig": "W",
            "Månedlig": "M",
            "År" : "Y"
        }
        self.selected_resolution = resolution_mapping[selected_option]
        #self.selected_resolution = "Rådata"
        if self.selected_resolution != "Rådata":
            numeric_columns = df.select_dtypes(include=[float, int]).columns.tolist()
            df = df.groupby(pd.Grouper(key='Tid', freq="D", offset='0S'))[numeric_columns].mean().reset_index()
        df["Tidsverdier"] = df['Tid'].dt.strftime("%d/%m-%y, %H:01").tolist()
        return df

    def get_electric_df(self):
        df_el = pd.read_excel("src/data/elforbruk/data.xlsx")
        df_el['dato'] = pd.to_datetime(df_el['dato'], format='%d.%m.%Y')
        df_el['Tidsverdier'] = df_el['dato'].dt.strftime('%d/%m-%y, %H:01')
        df_el['Tid'] = df_el['dato'].dt.strftime('%Y-%m-%d 01:01')
        df_el = df_el.drop("dato", axis = 1)
        df_el.rename(columns = {'kWh' : 'Strømforbruk'}, inplace = True)
        self.df_el = df_el

    def electric_column_to_hours(self, df):
        for index, row in df.iterrows():
            daily_sum = row['Strømforbruk']
            if daily_sum > 0:
                hourly_sum = daily_sum/23
            #if row['Til bane 1'] > -50:
            if row['Tilført energi - Bane 1'] > 0:
                df.at[index, 'Strømforbruk'] = hourly_sum
            else:
                df.at[index, 'Strømforbruk'] = None
        return df

    def remove_outliers(self, df, series):
        Q1 = df[series].quantile(0.1)
        Q3 = df[series].quantile(0.9)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        df.loc[(df[series] < lower_bound) | (df[series] > upper_bound), series] = np.nan
        return df
    
    def find_missing_time_data(self, df):
        df['Tid'] = pd.to_datetime(df['Tid'])
        date_range = pd.date_range(start=df['Tid'].min(), end=df['Tid'].max(), freq='H')
        df_date_range = pd.DataFrame(date_range, columns=['Tid'])
        merged_df = pd.merge(df_date_range, df, on='Tid', how='left')
        merged_df.sort_values(by='Tid', inplace=True)
        merged_df.reset_index(drop=True, inplace=True)
        return merged_df

    def main(self):
        self.streamlit_settings()
        name, authentication_status, username, authenticator = self.streamlit_login()
        self.streamlit_login_page(name, authentication_status, username, authenticator)
        st.title("Røa kunstgressbane - Livedata") # page title
        with st.sidebar:
            NORMALIZE = st.toggle('Normaliser energidata?', value=True)
            NUMBER_OF_COLUMNS = st.selectbox('Antall kolonner i visning?', options=[4,3,2,1])
        df = self.get_full_dataframe(normalize=NORMALIZE) # get dataframe
        
#        self.get_electric_df()
#        self.get_temperature_series()
        
#        df_el = self.df_el
#        df_el['Tid'] = pd.to_datetime(df_el['Tid'])
        df['Tid'] = pd.to_datetime(df['Tid'])
#        df = pd.merge(df, df_el, on='Tid', how='outer')
#        df['Strømforbruk'] = df['Strømforbruk'].astype(float)
#        df = self.electric_column_to_hours(df = df)
#        df = self.add_columns_to_df(df)
#        df['COP'] = df['Tilført effekt - Bane 1']/df['Strømforbruk']
#        df['COP'].astype(float)
#        df = df.mask(df == 0, None)
#        df['Tilført effekt - Bane 1'] = df['Tilført effekt - Bane 1'].round()

#        df['Strømforbruk'] = df['Strømforbruk'].round()
#        df['Strømforbruk_akkumulert'] = df['Strømforbruk'].cumsum()
#        self.total_poweruse = df['Strømforbruk_akkumulert'].max()
#        self.total_energyuse = df['Tilført energi - Bane 1'].max()
        self.total_days = len(df)/23
        ####
#        df = self.remove_outliers(df, "Tilført effekt - Bane 1")
#        df = self.remove_outliers(df, "Tilført energi - Bane 1")
#        df = self.remove_outliers(df, "COP")
#        df = self.find_missing_time_data(df)
        df["Tidsverdier"] = df['Tid'].dt.strftime("%d/%m-%y, %H:01").tolist()
        ####
        with st.sidebar:
            df, start_date, end_date = self.date_picker(df = df) # top level filter
        self.start_date = self.get_date_string(date = start_date)
        self.end_date = self.get_date_string(date = end_date)
        ####
        st.caption(f"Siste registrerte data {self.end_date} | Dagens dato: {self.get_date_string(datetime.today())}")
        ####
        df.set_index("Tid", inplace=True)
        df.drop(columns=['Tidsverdier'], inplace=True)

        # Determine number of subplots
        num_plots = len(df.columns)
        num_cols = NUMBER_OF_COLUMNS
        num_rows = (num_plots - 1) // num_cols + 1

        fig = make_subplots(
            rows=num_rows,
            cols=num_cols,
            subplot_titles=df.columns[0:],
            shared_xaxes=True
        )

        # Add traces
        row = 1
        col = 1
        for i, column in enumerate(df.columns):  # Use all columns
            fig.add_trace(
                go.Scatter(x=df.index, y=df[column], mode='lines', name=column),
                row=row, col=col
            )
            col += 1
            if col > num_cols:
                col = 1
                row += 1

        # Ensure x-axis tick labels are shown for all subplots
        for r in range(1, num_rows + 1):
            for c in range(1, num_cols + 1):
                idx = (r - 1) * num_cols + c
                if idx > num_plots:
                    continue  # skip empty cells
                axis_name = f'xaxis{idx}' if idx > 1 else 'xaxis'
                fig.update_layout({axis_name: dict(showticklabels=True)})

        # Final layout
        fig.update_layout(
            showlegend=False,
            margin=dict(l=40, r=40, t=80, b=40),
            height=300 * num_rows,  # adjust based on number of rows
        )

        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        
        st.dataframe(
            data = df, 
            height = 300, 
            use_container_width = True,
            ) # data table
        st.markdown(self.download_csv(df), unsafe_allow_html=True) # download button
        self.show_weather_stats()

if __name__ == "__main__":
    dashboard = Dashboard()
    dashboard.main()